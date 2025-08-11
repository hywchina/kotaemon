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

# 启动应用 (使用绝对路径避免路径依赖)
echo "[INFO] 正在启动应用..."
python "$(dirname "$0")/app.py"  # 自动获取脚本所在目录的app.py

# 状态反馈
echo "[INFO] 应用已启动"