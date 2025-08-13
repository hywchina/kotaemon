from fastapi import FastAPI, Request
from FlagEmbedding import FlagReranker

app = FastAPI()

# 加载本地模型
reranker = FlagReranker(
    '/home/huyanwei/projects/llm_cache/ms/model/bge-reranker-v2-m3',
    use_fp16=True
)

@app.post("/v1/rerank")
async def cohere_rerank(request: Request):
    data = await request.json()
    query = data["query"]
    documents = data["documents"]

    # 兼容文档是 dict 或 str 的情况
    if isinstance(documents[0], dict) and "text" in documents[0]:
        documents = [doc["text"] for doc in documents]

    query_passage_pairs = [[query, passage] for passage in documents]
    scores = reranker.compute_score(query_passage_pairs, normalize=True)

    results = [
        {"index": i, "relevance_score": float(score)}
        for i, score in enumerate(scores)
    ]
    # 按分数降序
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return {"results": results}

if __name__ == "__main__":
    """
            curl -X POST "http://127.0.0.1:8000/v1/rerank" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer dummy" \
        -d '{
            "model": "rerank-multilingual-v2.0",
            "query": "太阳系中最大的行星是什么？",
            "documents": [
            {"text": "木星是太阳系中最大的行星。"},
            {"text": "地球是人类居住的行星。"},
            {"text": "火星是红色的行星。"}
            ]
        }'
        uvicorn fake_cohere:app --host 0.0.0.0 --port 8000

            
    """
    pass 