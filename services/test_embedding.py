import requests
import sys

__test__ = False

# 默认 Ollama / vLLM OpenAI 兼容 API 地址
BASE_URL = "http://127.0.0.1:11434/v1"  # Ollama 默认 11434，vLLM 常用 8000
API_KEY = "EMPTY"  # 本地部署通常不需要
MODEL_NAME = "bge-m3:latest"  # 你部署的 embedding 模型名


def check_service():
    """检测服务是否启动"""
    try:
        r = requests.get(f"{BASE_URL}/models", timeout=3)
        if r.status_code == 200:
            models = r.json()
            print("✅ 服务已启动，支持的模型：")
            for m in models.get("data", []):
                print(" -", m.get("id"))
            return True
    except requests.exceptions.RequestException:
        return False
    return False


def test_embedding():
    """测试 Embedding 接口"""
    payload = {
        "model": MODEL_NAME,
        "input": ["人工智能正在改变世界。", "量子计算和机器学习的结合很有前景。"],
    }
    try:
        r = requests.post(
            f"{BASE_URL}/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=15,
        )
        if r.status_code == 200:
            result = r.json()
            print("✅ Embedding API 返回结果：")
            for i, emb in enumerate(result["data"]):
                print(f" 文本 {i}: 向量维度 = {len(emb['embedding'])}")
        else:
            print(f"❌ API 请求失败，状态码: {r.status_code}, 内容: {r.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求出错: {e}")


if __name__ == "__main__":
    if check_service():
        print("\n🚀 开始测试 Embedding 模型...\n")
        test_embedding()
    else:
        print("❌ 服务未运行，请先启动 ollama 或 vLLM。")
        sys.exit(1)
