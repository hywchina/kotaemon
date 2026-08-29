"""
Locust 压力测试脚本 - 测试 Kotaemon AI 辅助诊断系统
模拟多个用户同时使用 /chat_fn 接口进行对话

此版本增加：
- 将每次调用结果保存到 CSV：`chat_fn_results.csv`（包含 user_id、用户输入、系统回答、回答时长（秒）、速度 tokens/s）
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
RESULTS_FILE = os.path.join(OUTPUT_DIR, "chat_fn_results.csv")
_results_lock = threading.Lock()
_stats = {"count": 0, "sum_duration": 0.0, "sum_speed": 0.0}


def _ensure_results_file():
    # 如果不存在，写入表头
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["user_id", "user_input", "response", "duration_s", "tokens_per_s"]
            )


def _record_result(user_id, user_input, response_text, duration_s, tokens_per_s):
    # 将一条记录追加到 CSV，并更新统计
    _ensure_results_file()
    with _results_lock:
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    user_id,
                    user_input,
                    response_text,
                    f"{duration_s:.3f}",
                    f"{tokens_per_s:.3f}",
                ]
            )
        _stats["count"] += 1
        _stats["sum_duration"] += duration_s
        _stats["sum_speed"] += tokens_per_s


class GradioUser(User):
    """模拟 Gradio 应用用户"""

    # 用户任务之间的等待时间（秒）
    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.user_id = None

    def on_start(self):
        """每个用户启动时执行一次 - 初始化 Gradio Client"""
        try:
            self.user_id = f"user_{random.randint(1000, 9999)}"
            self.client = Client(BASE_URL)
            logger.info(f"用户 {self.user_id} 初始化成功")
        except Exception as e:
            logger.error(f"用户 {self.user_id} 初始化失败: {str(e)}")
            raise

    def _extract_reply(self, result):
        # 尝试从 predict 的返回结构中提取回复文本，回退到 str(result)
        try:
            if isinstance(result, (list, tuple)) and result:
                first = result[0]
                if isinstance(first, (list, tuple)) and first:
                    last = first[-1]
                    if isinstance(last, (list, tuple)) and len(last) >= 2:
                        return last[1]
            return str(result)
        except Exception:
            return str(result)

    @task(3)
    def chat_simple_question(self):
        """任务1: 发送简单问题并获取回复（权重3）"""
        test_questions = [
            "你好，请介绍一下你的功能。",
            "你能帮我做什么？",
            "请简单介绍一下你自己。",
            "你有哪些主要功能？",
            "如何使用这个系统？",
        ]

        question = random.choice(test_questions)
        chat_history = [(question, None)]

        start_time = time.time()
        try:
            result = self.client.predict(
                chat_history=chat_history,
                llm_type="",  # 使用默认模型
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn",
            )

            # 计算响应时间（秒）
            duration_s = time.time() - start_time
            response_text = self._extract_reply(result)
            tokens = len(str(response_text).split())
            tokens_per_s = tokens / duration_s if duration_s > 0 else 0.0

            # 记录到 Locust 事件
            events.request.fire(
                request_type="gradio",
                name="/chat_fn_simple",
                response_time=duration_s * 1000,
                response_length=len(str(result)),
                exception=None,
                context={},
            )

            # 将结果写入 CSV
            _record_result(
                self.user_id, question, response_text, duration_s, tokens_per_s
            )

            logger.info(
                f"用户 {self.user_id} 简单问题成功，响应时间: {duration_s * 1000:.2f}ms, tokens/s: {tokens_per_s:.2f}"
            )

        except Exception as e:
            duration_s = time.time() - start_time
            events.request.fire(
                request_type="gradio",
                name="/chat_fn_simple",
                response_time=duration_s * 1000,
                response_length=0,
                exception=e,
                context={},
            )
            logger.error(f"用户 {self.user_id} 简单问题失败: {str(e)}")

    @task(2)
    def chat_with_context(self):
        """任务2: 带上下文的多轮对话（权重2）"""
        conversation_templates = [
            [
                ("患者男性，65岁，主诉胸闷3天。", "请问有其他症状吗？"),
                ("伴有气促，活动后加重。", None),
            ],
            [
                ("患者女性，45岁，血压180/100mmHg。", "高血压的情况，请继续。"),
                ("既往有高血压病史10年，服药不规律。", None),
            ],
            [
                ("患者咳嗽2周，伴发热。", "体温多少？有痰吗？"),
                ("体温38.5°C，有黄痰。", None),
            ],
        ]

        chat_history = random.choice(conversation_templates)
        # For CSV, represent the user input as the last user message in the history
        last_user_input = (
            chat_history[-1][0]
            if chat_history and isinstance(chat_history[-1], (list, tuple))
            else ""
        )

        start_time = time.time()
        try:
            result = self.client.predict(
                chat_history=chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn",
            )

            duration_s = time.time() - start_time
            response_text = self._extract_reply(result)
            tokens = len(str(response_text).split())
            tokens_per_s = tokens / duration_s if duration_s > 0 else 0.0

            events.request.fire(
                request_type="gradio",
                name="/chat_fn_context",
                response_time=duration_s * 1000,
                response_length=len(str(result)),
                exception=None,
                context={},
            )

            _record_result(
                self.user_id, last_user_input, response_text, duration_s, tokens_per_s
            )

            logger.info(
                f"用户 {self.user_id} 上下文对话成功，响应时间: {duration_s * 1000:.2f}ms, tokens/s: {tokens_per_s:.2f}"
            )

        except Exception as e:
            duration_s = time.time() - start_time
            events.request.fire(
                request_type="gradio",
                name="/chat_fn_context",
                response_time=duration_s * 1000,
                response_length=0,
                exception=e,
                context={},
            )
            logger.error(f"用户 {self.user_id} 上下文对话失败: {str(e)}")

    def on_stop(self):
        """每个用户停止时执行一次"""
        logger.info(f"用户 {self.user_id} 测试结束")


# 在测试结束时写入平均值行并打印到 stdout
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    with _results_lock:
        count = _stats.get("count", 0)
        if count > 0:
            avg_duration = _stats["sum_duration"] / count
            avg_speed = _stats["sum_speed"] / count
        else:
            avg_duration = 0.0
            avg_speed = 0.0

        # 写入平均值到 CSV
        _ensure_results_file()
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["AVERAGE", "", "", f"{avg_duration:.3f}", f"{avg_speed:.3f}"]
            )

    print(
        f"Locust test finished. Samples={count}, avg_duration_s={avg_duration:.3f}, avg_tokens_per_s={avg_speed:.3f}"
    )
