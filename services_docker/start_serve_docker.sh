# 构建镜像 原始的 dockerfile（三个版本，lite、full、ollama）
docker build --target lite -t my-app-lite -f Dockerfile .
docker build --target full -t chifeng-ai-diagnosis:v0.1 -f Dockerfile .
docker build --target ollama -t my-app-ollama -f Dockerfile .

# 新的 单独 dockerfile
docker build -t chifeng-ai-diagnosis:v0.1 -f Dockerfile.ai-diagnosis .

# 创建容器
docker run -itd \
-e GRADIO_SERVER_NAME=0.0.0.0 \
-e GRADIO_SERVER_PORT=7860 \
-v ./ktem_app_data:/app/ktem_app_data \
-v ./logs-1:/app/logs \
-p 7860:7860  \
chifeng-ai-diagnosis:v0.1 bash 
