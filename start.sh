#!/bin/bash

# 安装依赖
# pip install graphrag future


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