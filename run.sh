#!/usr/bin/env bash

# `sh run.sh ...` ignores the shebang. Re-enter with Bash because this script
# uses arrays and `[[ ... ]]`; both macOS Bash 3.2 and newer Bash are supported.
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$APP_DIR/logs/runtime"
APP_PID_FILE="$RUNTIME_DIR/app.pid"
RERANK_PID_FILE="$RUNTIME_DIR/rerank.pid"
APP_LOG_FILE="$RUNTIME_DIR/app.log"
RERANK_LOG_FILE="$RUNTIME_DIR/rerank.log"
COMMAND="${1:-start}"
PORT="${2:-${GRADIO_SERVER_PORT:-7860}}"

mkdir -p "$RUNTIME_DIR"

has_app_runtime() {
    local python_bin="$1"
    [[ -x "$python_bin" ]] && \
        "$python_bin" -c 'import gradio, ktem, theflow' >/dev/null 2>&1
}

if has_app_runtime "$APP_DIR/.venv/bin/python"; then
    PYTHON_CMD=("$APP_DIR/.venv/bin/python")
elif has_app_runtime "$APP_DIR/venv/bin/python"; then
    PYTHON_CMD=("$APP_DIR/venv/bin/python")
elif command -v uv >/dev/null 2>&1; then
    PYTHON_CMD=(uv run python)
else
    PYTHON_CMD=(python)
fi

is_running() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null
}

is_true() {
    case "${1:-}" in
        1|true|TRUE|True|yes|YES|Yes|on|ON|On) return 0 ;;
        *) return 1 ;;
    esac
}

start_rerank() {
    if ! is_true "${KH_START_LOCAL_RERANK:-false}"; then
        return 0
    fi
    if is_running "$RERANK_PID_FILE"; then
        echo "[INFO] 本地重排服务已运行 (PID: $(<"$RERANK_PID_FILE"))"
        return 0
    fi

    echo "[INFO] 启动本地重排服务"
    nohup "${PYTHON_CMD[@]}" -m uvicorn services.local_rerank_server:app \
        --host "${KH_LOCAL_RERANK_HOST:-127.0.0.1}" \
        --port "${KH_LOCAL_RERANK_PORT:-8001}" \
        >>"$RERANK_LOG_FILE" 2>&1 &
    echo "$!" >"$RERANK_PID_FILE"
    sleep 2
    if ! is_running "$RERANK_PID_FILE"; then
        echo "[ERROR] 本地重排服务启动失败，请查看 $RERANK_LOG_FILE"
        return 1
    fi
}

start_app() {
    if is_running "$APP_PID_FILE"; then
        echo "[INFO] 应用已运行 (PID: $(<"$APP_PID_FILE"))"
        return 0
    fi
    if command -v lsof >/dev/null 2>&1 && \
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "[ERROR] 端口 $PORT 已被其他进程占用；未终止该进程。"
        return 1
    fi

    start_rerank
    echo "[INFO] 启动应用，端口 $PORT"
    nohup env \
        GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}" \
        GRADIO_SERVER_PORT="$PORT" \
        "${PYTHON_CMD[@]}" "$APP_DIR/app.py" \
        >>"$APP_LOG_FILE" 2>&1 &
    echo "$!" >"$APP_PID_FILE"
    sleep 2
    if ! is_running "$APP_PID_FILE"; then
        echo "[ERROR] 应用启动失败，请查看 $APP_LOG_FILE"
        return 1
    fi
    echo "[INFO] 应用已启动 (PID: $(<"$APP_PID_FILE"))"
}

stop_pid() {
    local name="$1"
    local pid_file="$2"
    if ! is_running "$pid_file"; then
        rm -f "$pid_file"
        echo "[INFO] $name 未运行"
        return 0
    fi

    local pid
    pid="$(<"$pid_file")"
    kill "$pid"
    for _ in {1..20}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$pid_file"
            echo "[INFO] $name 已停止"
            return 0
        fi
        sleep 0.25
    done
    echo "[ERROR] $name 未在 5 秒内退出 (PID: $pid)"
    return 1
}

stop_all() {
    stop_pid "应用" "$APP_PID_FILE"
    stop_pid "本地重排服务" "$RERANK_PID_FILE"
}

show_status() {
    if is_running "$APP_PID_FILE"; then
        echo "应用: running (PID: $(<"$APP_PID_FILE"))"
    else
        echo "应用: stopped"
    fi
    if is_running "$RERANK_PID_FILE"; then
        echo "本地重排服务: running (PID: $(<"$RERANK_PID_FILE"))"
    else
        echo "本地重排服务: stopped"
    fi
}

case "$COMMAND" in
    start|--start)
        start_app
        ;;
    foreground)
        start_rerank
        export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
        export GRADIO_SERVER_PORT="$PORT"
        exec "${PYTHON_CMD[@]}" "$APP_DIR/app.py"
        ;;
    stop|--stop)
        stop_all
        ;;
    restart|--restart)
        stop_all
        start_app
        ;;
    status|--status)
        show_status
        ;;
    logs|--logs)
        touch "$APP_LOG_FILE" "$RERANK_LOG_FILE"
        tail -n 100 -f "$APP_LOG_FILE" "$RERANK_LOG_FILE"
        ;;
    help|--help|-h)
        echo "Usage: ./run.sh {start|foreground|stop|restart|status|logs} [port]"
        echo "Set KH_START_LOCAL_RERANK=true to start the optional rerank service."
        ;;
    *)
        echo "Unknown command: $COMMAND" >&2
        exit 2
        ;;
esac
