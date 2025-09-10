#!/bin/bash
# ========= 重置虚拟环境 =========
# 删除现有的虚拟环境    

deactivate \
    && rm -rf ./venv \
    && virtualenv -p python3.10 venv \
    && source venv/bin/activate \
    && pip install --upgrade pip setuptools wheel build 

# ========= 安装依赖 =========
# # 安装依赖 方式1
# virtualenv -p python3.10 venv && source venv/bin/activate && python -m pip install --upgrade pip setuptools wheel build 
# pip install -e "libs/kotaemon[all]"
# pip install -e "libs/ktem"
# pip install nano-graphrag
# pip install git+https://github.com/HKUDS/LightRAG.git
# pip install umap-learn==0.5.5
# pip install graspologic==3.3.0
# pip uninstall -y hnswlib chroma-hnswlib && pip install chroma-hnswlib

# 安装依赖 方式2
# pip install -r requirements.txt
# tips: kotaemon 和 ktem 是安装之前制作 requriements.txt 时 github 上的版本：pip freeze > requirements.txt；需要重新安装 ketm 和 ketaemon[all]，以确保是最新版本
# pip install -e "libs/kotaemon[all]"   
# pip install -e "libs/ktem"

# 检查冲突
# pip check

# ========= 重启服务 =========
bash stop_serve.sh && rm -rf ktem_app_data && bash start_serve.sh