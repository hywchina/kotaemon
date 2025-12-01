"""
快速测试更新后的 locustfile 是否可以正常工作
"""
from gradio_client import Client
import time
import random

def test_locust_tasks():
    client = Client("http://localhost:7860/")
    user_id = f"user_{random.randint(1000, 9999)}"
    
    print("="*60)
    print("测试任务 1: 简单问题")
    print("="*60)
    
    test_questions = [
        "你好，请介绍一下你的功能。",
        "你能帮我做什么？",
    ]
    
    question = random.choice(test_questions)
    chat_history = [(question, None)]
    
    start_time = time.time()
    try:
        result = client.predict(
            chat_history=chat_history,
            llm_type="",
            use_citation="highlight",
            language="zh",
            param_11="disabled",
            param_12=[],
            api_name="/chat_fn"
        )
        response_time = (time.time() - start_time) * 1000
        print(f"✓ 成功! 响应时间: {response_time:.2f}ms")
        print(f"  回复: {result[0][-1][1][:100]}...")
    except Exception as e:
        print(f"✗ 失败: {e}")
        return False
    
    print("\n" + "="*60)
    print("测试任务 2: 上下文对话")
    print("="*60)
    
    chat_history = [
        ("患者男性，65岁，主诉胸闷3天。", "请问有其他症状吗？"),
        ("伴有气促，活动后加重。", None)
    ]
    
    start_time = time.time()
    try:
        result = client.predict(
            chat_history=chat_history,
            llm_type="",
            use_citation="highlight",
            language="zh",
            param_11="disabled",
            param_12=[],
            api_name="/chat_fn"
        )
        response_time = (time.time() - start_time) * 1000
        print(f"✓ 成功! 响应时间: {response_time:.2f}ms")
        print(f"  回复: {result[0][-1][1][:100]}...")
    except Exception as e:
        print(f"✗ 失败: {e}")
        return False
    
    print("\n" + "="*60)
    print("✓ 所有测试通过！Locust 脚本可以正常运行。")
    print("="*60)
    return True

if __name__ == "__main__":
    test_locust_tasks()
