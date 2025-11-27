# 构建镜像 原始的 dockerfile（三个版本，lite、full、ollama）
docker build --target lite -t my-app-lite -f Dockerfile .
docker build --target full -t ai-diagnosis-service:v0.1 -f Dockerfile .
docker build --target ollama -t my-app-ollama -f Dockerfile .

# 新的 单独 dockerfile
rm -rf ktem_app_data logs venv # 删除旧数据
docker build -t ai-diagnosis-service:v1.0.0 -f Dockerfile.ai_diagnosis.v1.0.0 .

# 创建容器
docker run -itd \
-e GRADIO_SERVER_NAME=0.0.0.0 \
-e GRADIO_SERVER_PORT=7860 \
-v ./ktem_app_data:/app/ktem_app_data \
-v ./logs:/app/logs \
-v ./models:/app/models \
-p 7860:7860  \
--name ai-diagnosis-service \
ai-diagnosis-service:v1.0.0

# 容器--》镜像--》离线压缩包--》加载离线压缩包
docker commit <容器ID或容器名> <新镜像名>:<tag>
docker save -o <保存路径/文件名.tar> <镜像名>:<tag>
docker load -i <文件名.tar>
