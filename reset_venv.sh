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
# tips: kotaemon 和 ktem 是安装之前制作 requriements.txt 时 github 上的版本：pip freeze > requirements.txt


# 检查冲突
# pip check

