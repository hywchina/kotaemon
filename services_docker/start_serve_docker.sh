# 构建镜像
docker build --target lite -t my-app-lite -f Dockerfile.ai-diagnosis .
docker build --target full -t chifeng-ai-diagnosis:v0.1 -f Dockerfile.ai-diagnosis .
docker build --target ollama -t my-app-ollama -f Dockerfile.ai-diagnosis .


# 创建容器
docker run -it \
-e GRADIO_SERVER_NAME=0.0.0.0 \
-e GRADIO_SERVER_PORT=7860 \
-v ./ktem_app_data:/app/ktem_app_data \
-v ./logs:/app/logs \
-p 7860:7860  \
chifeng-ai-diagnosis:v0.1 /bin/bash



# 进入容器
docker exec -it $(docker ps -q --filter ancestor=ghcr.io/cinnamon/k