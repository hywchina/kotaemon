#!/bin/bash


# ========= 安装依赖 =========
# # 安装依赖 方式1
# pip install -e "libs/kotaemon[all]"
# pip install -e "libs/ktem"
# # pip uninstall hnswlib chroma-hnswlib && pip install chroma-hnswlib
# pip install nano-graphrag
# pip install git+https://github.com/HKUDS/LightRAG.git
# pip install umap-learn==0.5.5
# pip install graspologic==3.3.0
# pip uninstall -y hnswlib chroma-hnswlib && pip install chroma-hnswlib

# 安装依赖 方式2
# pip install -r requirements.txt
# tips: kotaemon 和 ktem 是安装之前制作 requriements.txt 时 github 上的版本：pip freeze > requirements.txt

# ========= 启动脚本 =========
set -euo pipefail

# ========= 环境变量 =========
# export USE_NANO_GRAPHRAG=true
export USE_LIGHTRAG=true

BASE_LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$BASE_LOG_DIR"

# ========= 杀死占用 7860 端口的进程 =========
if lsof -i:7860 | grep python >/dev/null 2>&1; then
    echo "[INFO] 杀死占用 7860 端口的进程..."
    lsof -i:7860 | grep python | awk '{print $2}' | xargs kill -9
else
    echo "[INFO] 端口 7860 没有被占用"
fi

# ========= 当前日志文件变量 =========
current_log_dir=""
current_log_file=""

# ========= 日志切换函数 =========
rotate_log() {
    # 每天一个目录
    log_dir="${BASE_LOG_DIR}/$(date '+%Y%m%d')"
    mkdir -p "$log_dir"

    # 每小时一个文件
    log_file="${log_dir}/$(date '+%H').log"

    current_log_dir="$log_dir"
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

        # 计算到下一个整点的秒数
        current_minute=$(date +%M)
        current_second=$(date +%S)
        sleep_seconds=$(( (60 - 10#$current_minute - 1)*60 + (60 - 10#$current_second) ))
        sleep $sleep_seconds

        kill $cat_pid >/dev/null 2>&1 || true
    done
) >> "${BASE_LOG_DIR}/start_serve.log" 2>&1 &


# ========= 启动应用（后台）=========
nohup python "$(dirname "$0")/app.py" > "$PIPE_FILE" 2>&1 &

echo "[INFO] 服务已启动，日志记录在 ${BASE_LOG_DIR}/start_serve.log"
echo "[INFO] 可用命令查看后台进程: ps -ef | grep app.py"
