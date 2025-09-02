# 拉取镜像
docker  run -itd \
-e GRADIO_SERVER_NAME=0.0.0.0 \
-e GRADIO_SERVER_PORT=7861 \
-v ./ktem_app_data:/app/ktem_app_data \
-p 7861:7861 -it --rm \
ghcr.io/cinnamon/kotaemon:main-full /bin/bash


# 进入容器
docker exec -it $(docker ps -q --filter ancestor=ghcr.io/cinnamon/k