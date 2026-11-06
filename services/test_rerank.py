import requests
import sys

BASE_URL = "http://127.0.0.1:8001"  # 排序服务地址

def check_service():
    try:
        r = requests.get(f"{BASE_URL}/docs", timeout=3)
        if r.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        return False
    return False

def test_rerank():
    payload = {
        "query": "人工智能的应用有哪些？",
        "texts": [
            "人工智能在医疗中的应用包括疾病预测和诊断。",
            "天气很好，适合出去散步。",
            "人工智能被广泛应用于自动驾驶和推荐系统。"
        ]
    }
    try:
        r = requests.post(f"{BASE_URL}/rerank", json=payload, timeout=5)
        if r.status_code == 200:
            print("✅ Rerank API 返回结果：")
            for item in r.json():
                print(item)
        else:
            print(f"❌ API 请求失败，状态码: {r.status_code}, 内容: {r.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求出错: {e}")

if __name__ == "__main__":
    if check_service():
        print("✅ 排序服务已启动，开始测试...")
        test_rerank()
    else:
        print("❌ 排序服务未运行，请先启动 uvicorn。")
        sys.exit(1)
