from typing import List
from pydantic import BaseModel
from fastapi import FastAPI
from sentence_transformers import CrossEncoder
import torch
import json
import os

"""
从 conf/rerank_models.json 加载默认重排模型配置。
JSON 结构示例：
{
  "models": [
    {"name": "bge-reranker-v2-m3", "model_name": "/app/models/bge-reranker-v2-m3", "batch_size": 32, "max_length": 512, "default": true},
    {"name": "bge-reranker-v2-base", "model_name": "/app/models/bge-reranker-v2-base", "batch_size": 16, "max_length": 512, "default": false}
  ]
}
仅加载 default=true 的模型。
"""

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 解析配置文件路径（相对项目根目录）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONF_PATH = os.path.join(PROJECT_ROOT, "conf", "rerank_models.json")

def _load_default_rerank_config(conf_path: str):
    if not os.path.exists(conf_path):
        raise FileNotFoundError(f"Rerank config not found: {conf_path}")
    with open(conf_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    models = data.get("models", [])
    defaults = [m for m in models if m.get("default") is True]
    if len(defaults) == 0:
        raise ValueError("No default rerank model defined in config.")
    if len(defaults) > 1:
        raise ValueError("Multiple default rerank models found; please set only one.")
    m = defaults[0]
    model_name = m.get("model_name")
    batch_size = int(m.get("batch_size", 32))
    max_length = int(m.get("max_length", 512))
    if not model_name:
        raise ValueError("Default rerank model missing 'model_name'.")
    # 展开 ~ 为实际用户主目录路径
    model_name = os.path.expanduser(model_name)
    return model_name, batch_size, max_length

MODEL_NAME, BATCH_SIZE, MAX_LENGTH = _load_default_rerank_config(CONF_PATH)

app = FastAPI()
model = CrossEncoder(MODEL_NAME, device=DEVICE, max_length=MAX_LENGTH)

class RerankIn(BaseModel):
    query: str
    texts: List[str]
    is_truncated: bool = True

class RerankOutItem(BaseModel):
    index: int
    score: float

@app.post("/rerank", response_model=List[RerankOutItem])
def rerank(payload: RerankIn):
    pairs = [[payload.query, t] for t in payload.texts]
    scores = model.predict(pairs, batch_size=BATCH_SIZE)
    # 降序排列并返回原始索引+分数（Kotaemon TEIFastRerank 预期的格式）
    ranked = sorted(
        [{"index": i, "score": float(s)} for i, s in enumerate(scores)],
        key=lambda x: x["score"],
        reverse=True,
    )
    return ranked

if __name__ == "__main__":
    import uvicorn

    # uvicorn services.local_rerank_server:app --host 0.0.0.0 --port 8001

    # uvicorn.run(app, host=0.0.0.0, port=8001)

