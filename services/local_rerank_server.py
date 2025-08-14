from typing import List
from pydantic import BaseModel
from fastapi import FastAPI
from sentence_transformers import CrossEncoder
import torch

# 选一个强悍且多语言的重排模型
MODEL_NAME = "/home/huyanwei/projects/llm_cache/ms/model/bge-reranker-v2-m3"  # 也可换成 -base/-large 等
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32
MAX_LENGTH = 512  # 截断上限

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

