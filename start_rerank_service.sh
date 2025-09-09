#!/usr/bin/env bash
set -euo pipefail

# ========= 配置 =========
SERVICE_NAME="rerank"
BASE_LOG_DIR="$(dirname "$0")/logs/services"
mkdir -p "$BASE_LOG_DIR"

# 日志文件名：服务名 + 启动时间
LOG_FILE="${BASE_LOG_DIR}/${SERVICE_NAME}_$(date '+%Y%m%d_%H%M%S').log"

# uvicorn 启动参数
HOST="0.0.0.0"
PORT="8001"
APP="services.local_rerank_server:app"

# ========= 启动前检查端口占用 =========
if lsof -i:${PORT} >/dev/null 2>&1; then
    echo "[INFO] 杀死占用 ${PORT} 端口的进程..."
    lsof -t -i:${PORT} | xargs kill -9
    sleep 2   # 给系统留点时间释放端口
else
    echo "[INFO] 端口 ${PORT} 没有被占用"
fi


# ========= 创建命名管道 =========
PIPE_FILE=$(mktemp -u)
mkfifo "$PIPE_FILE"

# ========= 日志写入器（后台运行）=========
(
    while IFS= read -r line; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
    done < "$PIPE_FILE" >> "$LOG_FILE"
) &

LOGGER_PID=$!

# ========= 启动服务 =========
echo "[INFO] 启动 ${SERVICE_NAME} 服务..."
nohup uvicorn "$APP" --host "$HOST" --port "$PORT" > "$PIPE_FILE" 2>&1 &

UVICORN_PID=$!

echo "[INFO] 服务已启动 (PID=$UVICORN_PID)"
echo "[INFO] 日志文件: $LOG_FILE"
echo "[INFO] 可用命令查看进程: ps -ef | grep $APP"
