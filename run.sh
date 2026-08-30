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

config_value() {
    local name="$1"
    local default_value="$2"
    local environment_value
    if environment_value="$(printenv "$name" 2>/dev/null)"; then
        printf '%s\n' "$environment_value"
        return 0
    fi

    (
        cd "$APP_DIR"
        "${PYTHON_CMD[@]}" - "$name" "$default_value" <<'PY'
import sys

from decouple import config

print(config(sys.argv[1], default=sys.argv[2]))
PY
    )
}

start_rerank() {
    local start_local_rerank
    start_local_rerank="$(config_value KH_START_LOCAL_RERANK false)"
    if ! is_true "$start_local_rerank"; then
        return 0
    fi
    if is_running "$RERANK_PID_FILE"; then
        echo "[INFO] 本地重排服务已运行 (PID: $(<"$RERANK_PID_FILE"))"
        return 0
    fi

    echo "[INFO] 启动本地重排服务"
    local rerank_host
    local rerank_port
    rerank_host="$(config_value KH_LOCAL_RERANK_HOST 127.0.0.1)"
    rerank_port="$(config_value KH_LOCAL_RERANK_PORT 8001)"
    nohup "${PYTHON_CMD[@]}" -m uvicorn services.local_rerank_server:app \
        --host "$rerank_host" \
        --port "$rerank_port" \
        >>"$RERANK_LOG_FILE" 2>&1 &
    echo "$!" >"$RERANK_PID_FILE"
    sleep 2
    if ! is_running "$RERANK_PID_FILE"; then
        echo "[ERROR] 本地重排服务启动失败，请查看 $RERANK_LOG_FILE"
        return 1
    fi
}

run_model_preflight() {
    cd "$APP_DIR"
    "${PYTHON_CMD[@]}" scripts/model_service_preflight.py
}

prepare_startup() {
    echo "[INFO] 检查医院部署配置"
    run_doctor
    prepare_model_services
}

prepare_model_services() {
    local rerank_was_running=false
    if is_running "$RERANK_PID_FILE"; then
        rerank_was_running=true
    fi

    start_rerank
    if run_model_preflight; then
        return 0
    fi

    if [[ "$rerank_was_running" == "false" ]] && is_running "$RERANK_PID_FILE"; then
        echo "[INFO] 模型预检失败，停止本次启动的本地重排服务"
        stop_pid "本地重排服务" "$RERANK_PID_FILE"
    fi
    return 1
}

app_http_ready() {
    "${PYTHON_CMD[@]}" - "$PORT" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

with urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/", timeout=1) as response:
    if response.status >= 500:
        raise RuntimeError(f"HTTP {response.status}")
PY
}

wait_for_app() {
    local timeout
    timeout="$(config_value KH_APP_START_TIMEOUT 90)"
    case "$timeout" in
        ''|*[!0-9]*)
            echo "[ERROR] KH_APP_START_TIMEOUT 必须是正整数秒数。"
            stop_pid "应用" "$APP_PID_FILE" || true
            return 1
            ;;
    esac
    if (( timeout < 1 )); then
        echo "[ERROR] KH_APP_START_TIMEOUT 必须大于 0。"
        stop_pid "应用" "$APP_PID_FILE" || true
        return 1
    fi

    local started_at=$SECONDS
    while (( SECONDS - started_at < timeout )); do
        if ! is_running "$APP_PID_FILE"; then
            rm -f "$APP_PID_FILE"
            echo "[ERROR] 应用进程在页面就绪前退出，请查看 $APP_LOG_FILE"
            return 1
        fi
        if app_http_ready; then
            echo "[INFO] 应用已启动并通过 HTTP 就绪检查 (PID: $(<"$APP_PID_FILE"))"
            return 0
        fi
        sleep 1
    done

    echo "[ERROR] 应用在 ${timeout} 秒内未就绪，请查看 $APP_LOG_FILE"
    stop_pid "应用" "$APP_PID_FILE" || true
    return 1
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

    prepare_startup
    echo "[INFO] 启动应用，端口 $PORT"
    nohup env \
        GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}" \
        GRADIO_SERVER_PORT="$PORT" \
        "${PYTHON_CMD[@]}" "$APP_DIR/app.py" \
        >>"$APP_LOG_FILE" 2>&1 &
    echo "$!" >"$APP_PID_FILE"
    wait_for_app
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
        rm -f "$APP_PID_FILE"
        echo "应用: stopped"
    fi
    if is_running "$RERANK_PID_FILE"; then
        echo "本地重排服务: running (PID: $(<"$RERANK_PID_FILE"))"
    else
        echo "本地重排服务: stopped"
    fi
}

run_doctor() {
    cd "$APP_DIR"
    "${PYTHON_CMD[@]}" scripts/hospital_preflight.py
}

case "$COMMAND" in
    start|--start)
        start_app
        ;;
    foreground)
        if is_running "$APP_PID_FILE"; then
            echo "[ERROR] 应用已运行 (PID: $(<"$APP_PID_FILE"))"
            exit 1
        fi
        if command -v lsof >/dev/null 2>&1 && \
            lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
            echo "[ERROR] 端口 $PORT 已被其他进程占用；未终止该进程。"
            exit 1
        fi
        prepare_startup
        export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
        export GRADIO_SERVER_PORT="$PORT"
        echo "$$" >"$APP_PID_FILE"
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
    doctor|--doctor)
        run_doctor
        ;;
    help|--help|-h)
        echo "用法: ./run.sh {start|foreground|stop|restart|status|logs|doctor} [端口]"
        echo "doctor 会检查医院部署配置、网络出口策略和离线资源。"
        echo "start、restart 和 foreground 会先执行 doctor，再测试 LLM、Embedding、Rerank 和 ASR。"
        echo "ASR 使用 Mock Provider 时自动跳过；任一必需模型失败都会阻止应用启动。"
        echo "后台启动仅在页面通过 HTTP 就绪检查后报告成功。"
        ;;
    *)
        echo "Unknown command: $COMMAND" >&2
        exit 2
        ;;
esac
