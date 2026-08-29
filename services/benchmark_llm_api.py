import asyncio
import aiohttp
import time
import numpy as np
from typing import List, Dict

# ===== 配置区 =====
API_BASE_URL = (
    "http://localhost:8000/v1"  # Ollama默认端口，vLLM通常为8000，LM Studio为1234
)
API_KEY = "EMPTY"  # 本地部署通常无需密钥
MODEL_NAME = "ms/model/Qwen2.5-1.5B-Instruct"  # 实际部署的模型名称
REQUEST_PAYLOAD = {
    "model": MODEL_NAME,
    "messages": [{"role": "user", "content": "用50字解释量子纠缠"}],
    "max_tokens": 100,
    "temperature": 0.7,
}
CONCURRENCY_LEVELS = [1, 5, 10]  # 测试的并发用户数
REQUESTS_PER_CLIENT = 20  # 每个客户端发送的请求数
# ==================


async def send_request(session: aiohttp.ClientSession, payload: Dict) -> Dict:
    """发送单次请求并记录延迟"""
    start_time = time.perf_counter()
    try:
        async with session.post(
            f"{API_BASE_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,
        ) as response:
            if response.status == 200:
                await response.read()
                latency = (time.perf_counter() - start_time) * 1000  # 毫秒
                return {"success": True, "latency": latency}
            return {"success": False, "error": f"HTTP {response.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def client_task(session: aiohttp.ClientSession, results: List, client_id: int):
    """单个客户端任务：发送多轮请求"""
    for _ in range(REQUESTS_PER_CLIENT):
        result = await send_request(session, REQUEST_PAYLOAD)
        results.append(result)


async def run_test(concurrency: int):
    """执行指定并发级别的测试"""
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(client_task(session, results, i))
            for i in range(concurrency)
        ]
        await asyncio.gather(*tasks)
    return results


def calculate_metrics(results: List, duration: float) -> Dict:
    """计算性能指标"""
    latencies = [r["latency"] for r in results if r.get("success")]
    errors = [r for r in results if not r["success"]]

    return {
        "total_requests": len(results),
        "success_rate": len(latencies) / len(results) * 100,
        "avg_latency_ms": np.mean(latencies) if latencies else 0,
        "p95_latency_ms": np.percentile(latencies, 95) if latencies else 0,
        "throughput_rps": len(latencies) / duration if duration > 0 else 0,
        "error_types": {
            e["error"]: sum(1 for r in errors if r["error"] == e["error"])
            for e in errors
        },
    }


async def main():
    """主测试流程"""
    print(f"🏁 开始性能测试 | 模型: {MODEL_NAME} | 接口: {API_BASE_URL}")
    print("-" * 65)

    for concurrency in CONCURRENCY_LEVELS:
        start_time = time.perf_counter()
        results = await run_test(concurrency)
        duration = time.perf_counter() - start_time
        metrics = calculate_metrics(results, duration)

        # 打印测试结果
        print(f" 并发 [{concurrency}] | 请求 [{metrics['total_requests']}]")
        print(f" 成功率: {metrics['success_rate']:.1f}%")
        print(f" 平均延迟: {metrics['avg_latency_ms']:.1f} ms")
        print(f" P95延迟: {metrics['p95_latency_ms']:.1f} ms")
        print(f" 吞吐量: {metrics['throughput_rps']:.1f} 请求/秒")

        if metrics["error_types"]:
            print(f"  ❌ 错误分布: {metrics['error_types']}")
        print("-" * 65)


if __name__ == "__main__":
    asyncio.run(main())
