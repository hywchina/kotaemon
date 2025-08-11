#!/bin/bash

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

# 严格模式: 脚本错误立即退出, 未定义变量报错
set -euo pipefail

# 环境变量配置
export USE_NANO_GRAPHRAG=true
export USE_LIGHTRAG=true

#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 重定向所有输出到日志函数
exec 1> >(while read -r line; do log "$line"; done)
exec 2>&1  # 合并错误流

log "[INFO] 正在启动应用..."
python "$(dirname "$0")/app.py"
log "[INFO] 应用已启动"