import requests
import sys

BASE_URL = "http://127.0.0.1:11434/v1"  # LLM 服务地址 ollama 端口11434，vLLM 通常为 8000，LM Studio 为 1234
API_KEY = "EMPTY"  # 本地部署通常不需要
MODEL_NAME = "qwen3:30b"  # 你的模型名

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

def test_llm():
    """测试一次 LLM ChatCompletion"""
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "用50字解释量子纠缠"}],
        "max_tokens": 100,
        "temperature": 0.7
    }
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=15
        )
        if r.status_code == 200:
            result = r.json()
            print("✅ LLM API 返回结果：")
            print(result["choices"][0]["message"]["content"])
        else:
            print(f"❌ API 请求失败，状态码: {r.status_code}, 内容: {r.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求出错: {e}")

if __name__ == "__main__":
    if check_service():
        print("\n🚀 开始测试 LLM 推理接口...\n")
        test_llm()
    else:
        print("❌ LLM 服务未运行，请先启动推理服务。")
        sys.exit(1)
