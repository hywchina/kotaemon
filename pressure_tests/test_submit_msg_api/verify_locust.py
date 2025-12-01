"""
验证 /submit_msg API 的限制
说明: 此 API 需要 Web UI 的会话状态，无法通过 API 调用正常工作
建议: 使用 test_chat_fn_api 中的测试方案
"""
from gradio_client import Client
import time

def test_submit_msg_limitation():
    """测试并说明 submit_msg 的限制"""
    client = Client("http://localhost:7860/")
    
    print("="*60)
    print("测试 /submit_msg API")
    print("="*60)
    
    try:
        result = client.predict(
            chat_input={"text": "你好", "files": []},
            chat_history=[],
            conv_name="test_conv",
            first_selector_choices=[],
            api_name="/submit_msg"
        )
        print("✓ 意外成功！API 可能已修复")
        return True
    except Exception as e:
        print(f"✗ 预期失败: {e}")
        print("\n" + "="*60)
        print("失败原因分析:")
        print("="*60)
        print("1. /submit_msg 需要会话状态（user_id, settings, conv_id）")
        print("2. 这些状态在 Web UI 中自动注入，但 API 调用无法提供")
        print("3. 服务端在缺少这些状态时会抛出异常")
        print("\n" + "="*60)
        print("✅ 推荐解决方案")
        print("="*60)
        print("使用 test_chat_fn_api 进行压力测试:")
        print("  cd ../test_chat_fn_api")
        print("  ./run_test.sh")
        print("\n/chat_fn API 已验证可正常工作，适合压力测试。")
        print("="*60)
        return False

if __name__ == "__main__":
    success = test_submit_msg_limitation()
    if not success:
        exit(1)
