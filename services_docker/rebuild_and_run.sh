#!/bin/bash
set -e

# === 配置部分 ===
# 基础镜像
BASE_IMAGE="ghcr.io/cinnamon/kotaemon:main-full"
# 新镜像名
NEW_IMAGE="chifeng-ai-diagnosis:latest"  # 或者你选其他名字
# 本地代码目录
LOCAL_CODE_DIR="/home/huyanwei/projects/kotaemon"
# 数据目录（运行时挂载）
DATA_DIR="$(pwd)/ktem_app_data"
# Dockerfile 名称
DOCKERFILE_NAME="Dockerfile.ai-diagnosis"  # 或者你选其他名字

# === 步骤 1: 生成 Dockerfile ===
echo "[1/3] 生成 Dockerfile..."
cat > "$DOCKERFILE_NAME" <<EOF
FROM $BASE_IMAGE

# 安装常用工具
RUN apt-get update && apt-get install -y \\
    net-tools \\
    curl \\
    vim \\
    iputils-ping \\
    less \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 清空原有代码
RUN rm -rf /app/*

# 拷贝本地代码到 /app
COPY . /app

# 如果需要安装依赖，可以取消下面注释
# RUN pip install -r requirements.txt --no-cache-dir

CMD ["bash"]
EOF

# === 步骤 2: 构建新镜像 ===
echo "[2/3] 构建新镜像..."
docker build -t "$NEW_IMAGE" -f "$DOCKERFILE_NAME" "$LOCAL_CODE_DIR"
# docker build -t "chifeng-ai-diagnosis:latest" -f Dockerfile . 

# === 步骤 3: 启动新容器 ===
echo "[3/3] 启动容器..."
docker run -itd \
    -e GRADIO_SERVER_NAME=0.0.0.0 \
    -e GRADIO_SERVER_PORT=7861 \
    -v "$DATA_DIR:/app/ktem_app_data" \
    -p 7861:7861 --rm \
    "$NEW_IMAGE"
