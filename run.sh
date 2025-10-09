#!/bin/bash
# ============================================
# 通用应用启动管理脚本
# 支持 start / stop / restart / status / log / help
# ============================================

set -euo pipefail

APP_NAME="app.py"
APP_DIR="$(dirname "$0")"
LOG_DIR="$APP_DIR/logs/system"
PID_FILE="$LOG_DIR/app.pid"
PIPE_FILE="$LOG_DIR/app.pipe"

DEFAULT_PORT=7860
PORT="${2:-$DEFAULT_PORT}"

# 环境变量配置
export USE_GLOBAL_GRAPHRAG=False
export USE_MS_GRAPHRAG=False
export USE_NANO_GRAPHRAG=False
export USE_LIGHTRAG=False

mkdir -p "$LOG_DIR"

# ========== 函数定义 ==========

rotate_log() {
    LOG_FILE="$LOG_DIR/$(date '+%Y%m%d').log"
    echo "$LOG_FILE"
}

start_service() {
    if [[ -f "$PID_FILE" ]] && ps -p "$(cat "$PID_FILE")" >/dev/null 2>&1; then
        echo "[WARN] 服务已在运行中 (PID: $(cat "$PID_FILE"))"
        exit 0
    fi

    # 杀掉占用端口的 python 进程
    if lsof -i:${PORT} | grep python >/dev/null 2>&1; then
        echo "[INFO] 杀死占用 ${PORT} 端口的进程..."
        lsof -i:${PORT} | grep python | awk '{print $2}' | xargs kill -9 || true
        sleep 1
    fi

    echo "[INFO] 启动服务 (端口: ${PORT}) ..."
    local LOG_FILE
    LOG_FILE=$(rotate_log)

    # 创建命名管道
    [[ -p "$PIPE_FILE" ]] || mkfifo "$PIPE_FILE"

    # 启动日志后台轮换进程
    (
        while true; do
            while IFS= read -r line; do
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
            done < "$PIPE_FILE" >> "$LOG_FILE" &
            cat_pid=$!

            now=$(date +%s)
            tomorrow=$(date -d "tomorrow 00:00:00" +%s)
            sleep_seconds=$(( tomorrow - now ))
            sleep $sleep_seconds

            kill $cat_pid >/dev/null 2>&1 || true
        done
    ) >> "$LOG_DIR/start_system.log" 2>&1 &

    # 启动应用
    nohup python "$APP_DIR/$APP_NAME" --port "$PORT" > "$PIPE_FILE" 2>&1 &
    APP_PID=$!
    echo $APP_PID > "$PID_FILE"

    echo "[INFO] 服务已启动 (PID: $APP_PID)"
    echo "[INFO] 日志文件: $LOG_FILE"
}

stop_service() {
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" >/dev/null 2>&1; then
            echo "[INFO] 停止服务 (PID: $PID)..."
            kill "$PID"
            sleep 1
            if ps -p "$PID" >/dev/null 2>&1; then
                echo "[WARN] 进程未退出，强制终止..."
                kill -9 "$PID" || true
            fi
            echo "[INFO] 服务已停止"
        else
            echo "[WARN] PID 文件存在但进程未运行，清理中..."
        fi
        rm -f "$PID_FILE"
    else
        echo "[INFO] 服务未运行"
    fi

    [[ -p "$PIPE_FILE" ]] && rm -f "$PIPE_FILE"
}

restart_service() {
    stop_service
    start_service
}

status_service() {
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" >/dev/null 2>&1; then
            echo "[INFO] 服务正在运行 (PID: $PID)"
            PORT_INFO=$(lsof -Pan -p "$PID" -i | grep LISTEN || true)
            [[ -n "$PORT_INFO" ]] && echo "[INFO] 监听端口: $(echo "$PORT_INFO" | awk '{print $9}')"
            echo "[INFO] 日志目录: $LOG_DIR"
            return
        fi
    fi
    echo "[INFO] 服务未运行"
}

show_log() {
    local LOG_FILE
    LOG_FILE=$(rotate_log)
    if [[ -f "$LOG_FILE" ]]; then
        tail -n 50 -f "$LOG_FILE"
    else
        echo "[INFO] 日志文件不存在: $LOG_FILE"
    fi
}

show_help() {
    cat <<EOF
用法: bash run.sh [命令] [可选参数]

可用命令:
  --start [port]     启动服务 (默认端口: $DEFAULT_PORT)
  --stop             停止服务
  --restart [port]   重启服务
  --status           查看服务状态
  --log              查看当前日志 (实时输出)
  --help             显示帮助信息
EOF
}

# ========== 主逻辑 ==========

case "${1:-}" in
    --start) start_service ;;
    --stop) stop_service ;;
    --restart) restart_service ;;
    --status) status_service ;;
    --log) show_log ;;
    --help|"") show_help ;;
    *)
        echo "[ERROR] 未知命令: $1"
        show_help
        exit 1
        ;;
esac
