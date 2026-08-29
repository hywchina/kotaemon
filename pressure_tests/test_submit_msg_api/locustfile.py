"""
Locust 压力测试脚本 - 测试 Kotaemon AI 辅助诊断系统 /submit_msg 接口
专门测试 submit_msg API 的异步消息提交功能

注意事项：
- 需要先登录才能访问 /submit_msg，凭据通过环境变量配置
- /submit_msg 是异步API，只测试消息提交速度，不等待 AI 生成回复
- 测试提交成功率和响应时间

此版本功能：
- 将每次调用结果保存到 CSV：`submit_msg_results.csv`
- 记录：user_id、用户输入、提交时长（秒）、状态
- 在测试结束时写入平均值行
"""

from locust import User, task, between, events
from gradio_client import Client
import time
import random
import logging
import threading
import csv
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 运行配置、结果文件与线程安全计数器
BASE_URL = os.getenv("KH_PRESSURE_TEST_BASE_URL", "http://localhost:7860/")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "pressure_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
RESULTS_FILE = os.path.join(OUTPUT_DIR, "submit_msg_results.csv")
_results_lock = threading.Lock()
_stats = {"count": 0, "sum_duration": 0.0, "success_count": 0, "failure_count": 0}

# 登录凭据
USERNAME = os.getenv("KH_PRESSURE_TEST_USERNAME", "admin")
PASSWORD = os.getenv("KH_PRESSURE_TEST_PASSWORD", "admin")


def _ensure_results_file():
    # 如果不存在，写入表头
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["user_id", "user_input", "submit_duration_s", "status", "note"]
            )


def _record_result(user_id, user_input, duration_s, status="success", note=""):
    # 将一条记录追加到 CSV，并更新统计
    _ensure_results_file()
    with _results_lock:
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [user_id, user_input[:100], f"{duration_s:.3f}", status, note]
            )
        _stats["count"] += 1
        _stats["sum_duration"] += duration_s
        if status == "success":
            _stats["success_count"] += 1
        else:
            _stats["failure_count"] += 1


class GradioUser(User):
    """模拟 Gradio 应用用户，测试 /submit_msg API"""

    # 用户任务之间的等待时间（秒）
    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.user_id = None
        self.conv_name = None
        self.conv_id = None
        self.logged_in = False

    def on_start(self):
        """每个用户启动时执行一次 - 初始化 Gradio Client 并登录"""
        try:
            self.user_id = f"user_{random.randint(1000, 9999)}"
            self.conv_name = f"conv_{self.user_id}_{int(time.time())}"
            self.client = Client(BASE_URL)

            # 登录
            self.client.predict(usn=USERNAME, pwd=PASSWORD, api_name="/login_1")
            self.logged_in = True

            logger.info(f"用户 {self.user_id} 初始化并登录成功")
        except Exception as e:
            logger.error(f"用户 {self.user_id} 初始化失败: {str(e)}")
            raise

    @task(3)
    def submit_simple_question(self):
        """任务1: 提交简单问题（权重3）- 测试单次提交"""
        if not self.logged_in:
            return

        test_questions = [
            "你好，请介绍一下你的功能。",
            "你能帮我做什么？",
            "请简单介绍一下你自己。",
            "你有哪些主要功能？",
            "如何使用这个系统？",
        ]

        question = random.choice(test_questions)
        chat_input = {"text": question, "files": []}

        start_time = time.time()
        status = "success"
        note = ""

        try:
            # 调用 /submit_msg API
            result = self.client.predict(
                chat_input=chat_input,
                chat_history=[],
                conv_name=self.conv_name,
                first_selector_choices=[],
                api_name="/submit_msg",
            )

            # 计算提交时间（秒）
            duration_s = time.time() - start_time

            # 解析返回结果，更新 conv_id
            if isinstance(result, (list, tuple)) and len(result) >= 3:
                self.conv_id = result[2]  # new_conv_id
                if len(result) >= 5:
                    self.conv_name = result[4]  # new_conv_name
                note = f"conv_id={self.conv_id}"

            # 记录到 Locust 事件
            events.request.fire(
                request_type="gradio",
                name="/submit_msg_simple",
                response_time=duration_s * 1000,
                response_length=len(str(result)),
                exception=None,
                context={},
            )

            # 将结果写入 CSV
            _record_result(self.user_id, question, duration_s, status, note)

            logger.info(
                f"用户 {self.user_id} 提交简单问题成功，提交时间: {duration_s * 1000:.2f}ms, conv_id: {self.conv_id}"
            )

        except Exception as e:
            duration_s = time.time() - start_time
            status = "failure"
            note = str(e)[:200]

            events.request.fire(
                request_type="gradio",
                name="/submit_msg_simple",
                response_time=duration_s * 1000,
                response_length=0,
                exception=e,
                context={},
            )

            _record_result(self.user_id, question, duration_s, status, note)
            logger.error(f"用户 {self.user_id} 提交简单问题失败: {str(e)}")

    @task(2)
    def submit_with_context(self):
        """任务2: 带上下文的多轮提交（权重2）- 测试会话持续性"""
        if not self.logged_in:
            return

        # 第一轮对话场景
        conversation_templates = [
            {
                "first": "患者男性，65岁，主诉胸闷3天。",
                "second": "伴有气促，活动后加重。",
            },
            {
                "first": "患者女性，45岁，血压180/100mmHg。",
                "second": "既往有高血压病史10年，服药不规律。",
            },
            {"first": "患者咳嗽2周，伴发热。", "second": "体温38.5°C，有黄痰。"},
        ]

        template = random.choice(conversation_templates)

        # 先发送第一条消息建立上下文
        try:
            first_result = self.client.predict(
                chat_input={"text": template["first"], "files": []},
                chat_history=[],
                conv_name=self.conv_name,
                first_selector_choices=[],
                api_name="/submit_msg",
            )

            # 获取会话信息
            if isinstance(first_result, (list, tuple)) and len(first_result) >= 3:
                chat_history = first_result[1] if len(first_result) >= 2 else []
                self.conv_id = first_result[2]
                if len(first_result) >= 5:
                    self.conv_name = first_result[4]
            else:
                chat_history = []

        except Exception as e:
            logger.error(f"用户 {self.user_id} 第一轮提交失败: {str(e)}")
            return

        # 发送第二条消息（带上下文）
        start_time = time.time()
        status = "success"
        note = ""

        try:
            result = self.client.predict(
                chat_input={"text": template["second"], "files": []},
                chat_history=chat_history,
                conv_name=self.conv_name,
                first_selector_choices=[],
                api_name="/submit_msg",
            )

            duration_s = time.time() - start_time
            note = f"conv_id={self.conv_id},context=yes"

            events.request.fire(
                request_type="gradio",
                name="/submit_msg_context",
                response_time=duration_s * 1000,
                response_length=len(str(result)),
                exception=None,
                context={},
            )

            _record_result(self.user_id, template["second"], duration_s, status, note)

            logger.info(
                f"用户 {self.user_id} 提交上下文对话成功，提交时间: {duration_s * 1000:.2f}ms"
            )

        except Exception as e:
            duration_s = time.time() - start_time
            status = "failure"
            note = str(e)[:200]

            events.request.fire(
                request_type="gradio",
                name="/submit_msg_context",
                response_time=duration_s * 1000,
                response_length=0,
                exception=e,
                context={},
            )

            _record_result(self.user_id, template["second"], duration_s, status, note)
            logger.error(f"用户 {self.user_id} 提交上下文对话失败: {str(e)}")

    def on_stop(self):
        """每个用户停止时执行一次"""
        logger.info(f"用户 {self.user_id} 测试结束")


# 在测试结束时写入平均值行并打印到 stdout
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    with _results_lock:
        count = _stats.get("count", 0)
        success_count = _stats.get("success_count", 0)
        failure_count = _stats.get("failure_count", 0)

        if count > 0:
            avg_duration = _stats["sum_duration"] / count
            success_rate = (success_count / count * 100) if count > 0 else 0
        else:
            avg_duration = 0.0
            success_rate = 0.0

        # 写入平均值到 CSV
        _ensure_results_file()
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "AVERAGE",
                    f"{count} samples",
                    f"{avg_duration:.3f}",
                    f"{success_count}✓/{failure_count}✗",
                    f"success_rate={success_rate:.1f}%",
                ]
            )

    print("Locust test finished.")
    print(f"Total samples: {count}")
    print(f"Success: {success_count}, Failure: {failure_count}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Avg submit duration: {avg_duration:.3f}s")
    print(
        "Note: /submit_msg is async - only measures submission time, not AI response generation"
    )
