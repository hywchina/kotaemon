#!/bin/bash

# ========= 启动脚本 =========
set -euo pipefail

PORT="${1:-7860}"   # 默认端口 7860，可通过 ./start_system.sh 8001 覆盖

# ========= 环境变量 =========
export USE_GLOBAL_GRAPHRAG=False
export USE_MS_GRAPHRAG=False
export USE_NANO_GRAPHRAG=True
export USE_LIGHTRAG=False

BASE_LOG_DIR="$(dirname "$0")/logs/system"
mkdir -p "$BASE_LOG_DIR"

# ========= 杀死占用 ${PORT} 端口的进程 =========
if lsof -i:${PORT} | grep python >/dev/null 2>&1; then
    echo "[INFO] 杀死占用 ${PORT} 端口的进程..."
    lsof -i:${PORT} | grep python | awk '{print $2}' | xargs kill -9
    sleep 2  # 等待端口释放
else
    echo "[INFO] 端口 ${PORT} 没有被占用"
fi

# ========= 当前日志文件变量 =========
current_log_file=""

# ========= 日志切换函数 =========
rotate_log() {
    # 每天一个文件，文件名为日期
    log_file="${BASE_LOG_DIR}/$(date '+%Y%m%d').log"
    current_log_file="$log_file"
}

# ========= 初始化日志 =========
rotate_log

# ========= 创建命名管道 =========
PIPE_FILE=$(mktemp -u)
mkfifo "$PIPE_FILE"

# ========= 启动日志轮换器（后台）=========
(
    while true; do
        rotate_log
        echo "[INFO] 日志切换到: $current_log_file"

        # 读取 PIPE_FILE，并给每行加上时间戳
        while IFS= read -r line; do
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
        done < "$PIPE_FILE" >> "$current_log_file" &

        cat_pid=$!

        # 计算到明天零点的秒数
        now=$(date +%s)
        tomorrow=$(date -d "tomorrow 00:00:00" +%s)
        sleep_seconds=$(( tomorrow - now ))
        sleep $sleep_seconds

        kill $cat_pid >/dev/null 2>&1 || true
    done
) >> "${BASE_LOG_DIR}/start_system.log" 2>&1 &

# ========= 启动应用（后台）=========
nohup python "$(dirname "$0")/app.py" > "$PIPE_FILE" 2>&1 &

echo "[INFO] 服务已启动，日志记录在 ${BASE_LOG_DIR}/start_system.log"
echo "[INFO] 可用命令查看后台进程: ps -ef | grep app.py"
