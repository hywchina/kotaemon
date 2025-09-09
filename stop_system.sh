#!/bin/bash

# 杀死占用 7860 端口的进程
if lsof -i:7860 | grep python >/dev/null 2>&1; then
    echo "[INFO] 杀死占用 7860 端口的进程..."
    lsof -i:7860 | grep python | awk '{print $2}' | xargs kill -9
else
    echo "[INFO] 端口 7860 没有被占用"
fi

ps -ef | grep '[s]tart_serve.sh' | awk '{print $2}' | xargs kill -9