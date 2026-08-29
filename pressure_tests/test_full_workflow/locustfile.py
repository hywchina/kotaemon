"""
Locust 压力测试脚本 - 完整用户流程测试
模拟真实用户使用 Kotaemon AI 辅助诊断系统的完整流程：
1. 提交问题 (submit_msg)
2. 等待 AI 生成回复 (chat_fn)
3. 获取完整响应结果

此测试真实反映用户体验，包括：
- 端到端响应时间
- AI 回复质量
- 数据持久化
- 前端可见的历史记录
"""

from locust import User, task, between, events
from gradio_client import Client
import time
import random
import logging
import threading
import csv
import os
import sys
from datetime import datetime

# 添加项目路径到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 运行配置
BASE_URL = os.getenv("KH_PRESSURE_TEST_BASE_URL", "http://localhost:7860/")
USE_KB = os.getenv("KH_PRESSURE_TEST_USE_KB", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
# 统一配置：问题模板（可按需修改）
SIMPLE_QUESTIONS = [
    "你好，请介绍一下你的功能。",
    "大体重减肥有哪些有效的方法？最好是无器械的",
    "装饰器在 Python 中是如何工作的？请举例说明。",
    "RL 学习有哪些分支，都有哪些经典算法，用通俗易懂的方式进行讲解",
    "小红书运营有哪些技巧和方法？有哪些好用的工具推荐？",
]

CONTEXT_TEMPLATES = [
    {
        "first": "患者男性，65岁，主诉胸闷3天。应该挂什么科室检查",
        "second": "伴有气促，活动后加重。需要注意什么",
    },
    {
        "first": "患者女性，45岁，血压180/100mmHg。血压在正常范围吗",
        "second": "既往有高血压病史10年，服药不规律。需要注意吗",
    },
    {
        "first": "患者咳嗽2周，伴发热。可能是什么疾病",
        "second": "体温38.5°C，有黄痰。需要做哪些检查",
    },
]

# 知识库场景下的基础问题（会自动带上 @"文件名"）
KB_SIMPLE_QUESTIONS = [
    "请根据该文档总结主要内容。",
    "文档中提到了什么重要信息？",
    "请分析文档的关键观点。",
    "这个文档的主题是什么？",
]

KB_CONTEXT_TEMPLATES = [
    {
        "first": "精神类疾病潜伏期大概多久",
        "second": "这个病人有家族史吗？",
    },
    {
        "first": "精神类疾病和神经类疾病有什么区别",
        "second": "这个病人是什么类型的疾病，通过哪些诊断手段诊断处理的",
    },
    {
        "first": "精神类疾病需要做哪些检查",
        "second": "这个人住院住了多久大概需要多少钱",
    },
]

# 导入数据库模型（延迟导入避免循环依赖）
try:
    from libs.ktem.ktem.db.models import engine, Conversation
    from sqlmodel import Session, select

    DB_AVAILABLE = True
    logger.info("✓ 数据库模块导入成功")
except Exception as e:
    logger.warning(f"✗ 无法导入数据库模型: {e}，将跳过数据持久化")
    DB_AVAILABLE = False


def _normalize_conv_id(conv_id_data):
    """统一解析 conv_id，无论是 dict/choices/str。

    返回字符串形式的 conv_id。
    """
    try:
        if isinstance(conv_id_data, dict):
            if "value" in conv_id_data and conv_id_data["value"]:
                return str(conv_id_data["value"])
            choices = conv_id_data.get("choices")
            if isinstance(choices, (list, tuple)) and len(choices) > 0:
                first = choices[0]
                # choices 可能是 [str] 或 [(label, value)]
                return str(first if isinstance(first, str) else first[1])
            return str(conv_id_data)
        if isinstance(conv_id_data, (str, int)):
            return str(conv_id_data)
        return str(conv_id_data)
    except Exception:
        return str(conv_id_data)


def _get_user_files(user_id="", index_id=1):
    """从数据库获取用户的知识库文件列表

    Args:
        user_id: 用户 ID（默认为空字符串，获取所有文件）
        index_id: 索引 ID（默认为 1）

    Returns:
        list: [(file_name, file_id), ...] 格式的文件列表
    """
    if not DB_AVAILABLE:
        return []

    try:
        from sqlalchemy import MetaData, select
        from sqlalchemy.orm import Session
        from ktem.db.engine import engine

        # 动态获取 Source 表
        metadata = MetaData()
        metadata.reflect(bind=engine)

        table_name = f"index__{index_id}__source"
        if table_name not in metadata.tables:
            logger.warning(f"表 {table_name} 不存在，无法获取文件列表")
            return []

        source_table = metadata.tables[table_name]

        with Session(engine) as session:
            if user_id:
                stmt = select(source_table).where(source_table.c.user == user_id)
            else:
                stmt = select(source_table)

            result = session.execute(stmt).fetchall()

            # 返回 (file_name, file_id) 格式
            files = [(row.name, row.id) for row in result]
            logger.info(f"✓ 获取到 {len(files)} 个文件")
            return files

    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return []


# 复制 selector choices，避免在 submit_msg 内部被原地修改
def _clone_selector_choices(file_choices):
    return list(file_choices) if file_choices else []


# 构造问题文本，按需附带知识库文件引用（@"filename" 语法）
def _prepare_question(base_question, file_choices, force=USE_KB):
    """返回 (question_text, selector_choices_copy, kb_file_name)

    force=True 时必定附带知识库；否则不附带。
    """
    if not file_choices:
        return base_question, [], None

    if not force:
        return base_question, [], None

    file_name, _ = random.choice(file_choices)
    kb_question = f'@"{file_name}" 请依据{file_name}内容回答：{base_question}'
    return kb_question, _clone_selector_choices(file_choices), file_name


# 结果文件与线程安全计数器（添加时间戳）
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# 添加创建路径的方法
output_dir = os.path.join(os.path.dirname(__file__), "pressure_output")
os.makedirs(output_dir, exist_ok=True)
RESULTS_FILE = os.path.join(
    output_dir, f"full_workflow_results_USE_KB_{USE_KB}_{timestamp}.csv"
)
_results_lock = threading.Lock()
_stats = {
    "count": 0,
    "sum_submit_duration": 0.0,
    "sum_total_duration": 0.0,
    "sum_tokens_per_s": 0.0,
    "success_count": 0,
    "failure_count": 0,
}

# 登录凭据
USERNAME = os.getenv("KH_PRESSURE_TEST_USERNAME", "admin")
PASSWORD = os.getenv("KH_PRESSURE_TEST_PASSWORD", "admin")


def _ensure_results_file():
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "user_id",
                    "user_input",
                    "ai_response",
                    "submit_duration_s",
                    "ai_duration_s",
                    "total_duration_s",
                    "tokens_per_s",
                    "status",
                    "note",
                    "USE_KB",
                    "task_name",
                ]
            )


def _record_result(
    user_id,
    user_input,
    ai_response,
    submit_duration,
    ai_duration,
    total_duration,
    tokens_per_s,
    status="success",
    note="",
):
    _ensure_results_file()
    with _results_lock:
        # 获取当前任务名（通过调用栈）
        import inspect

        stack = inspect.stack()
        task_name = None
        for frame in stack:
            if frame.function.startswith("complete_"):
                task_name = frame.function
                break
        if not task_name:
            task_name = "unknown"
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    user_id,
                    user_input.rstrip("\n")
                    if isinstance(user_input, str)
                    else str(user_input),
                    (ai_response.rstrip("\n") if isinstance(ai_response, str) else ""),
                    f"{submit_duration:.3f}",
                    f"{ai_duration:.3f}",
                    f"{total_duration:.3f}",
                    f"{tokens_per_s:.2f}",
                    status,
                    note,
                    str(USE_KB),
                    task_name,
                ]
            )
        _stats["count"] += 1
        _stats["sum_submit_duration"] += submit_duration
        _stats["sum_total_duration"] += total_duration
        # 准确累计 AI 耗时
        _stats.setdefault("sum_ai_duration", 0.0)
        _stats["sum_ai_duration"] += ai_duration
        _stats["sum_tokens_per_s"] += tokens_per_s
        if status == "success":
            _stats["success_count"] += 1
        else:
            _stats["failure_count"] += 1


def _extract_reply(result):
    """从 chat_fn 的返回值中提取 AI 回复内容"""
    try:
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            chat_history = result[0]  # 第一个是 chatbot (chat_history)
            if chat_history and len(chat_history) > 0:
                last_turn = chat_history[-1]
                if isinstance(last_turn, (list, tuple)) and len(last_turn) >= 2:
                    return last_turn[1]  # AI 的回复
    except Exception as e:
        logger.error(f"提取回复失败: {str(e)}")
    return None


def _persist_to_db(conv_id, chat_history, retrieval_msg=""):
    """手动保存对话到数据库"""
    if not DB_AVAILABLE:
        logger.warning("数据库不可用，跳过持久化")
        return False

    try:
        logger.info(f"开始保存对话 {conv_id}，消息数: {len(chat_history)}")

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conv_id)
            result = session.exec(statement).one_or_none()

            if not result:
                logger.warning(f"找不到对话 ID: {conv_id}")
                return False

            logger.info(
                f"找到对话记录，当前消息数: {len(result.data_source.get('messages', []))}"
            )

            # 更新 data_source
            data_source = result.data_source or {}
            data_source["messages"] = chat_history

            # 添加 retrieval_messages（如果有）
            if retrieval_msg:
                retrieval_history = data_source.get("retrieval_messages", [])
                retrieval_history.append(retrieval_msg)
                data_source["retrieval_messages"] = retrieval_history

            result.data_source = data_source
            session.add(result)
            session.commit()

            logger.info(f"✓ 成功保存对话 {conv_id}，新消息数: {len(chat_history)}")
            return True
    except Exception as e:
        logger.error(f"保存到数据库失败: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return False


class GradioUser(User):
    """模拟真实用户的完整操作流程"""

    wait_time = between(2, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.user_id = None
        self.logged_in = False
        self.file_choices = []  # 存储用户的知识库文件列表

    def on_start(self):
        """每个用户启动时执行 - 登录"""
        try:
            self.user_id = f"user_{random.randint(1000, 9999)}"
            self.client = Client(BASE_URL)

            # 登录
            login_result = self.client.predict(
                usn=USERNAME, pwd=PASSWORD, api_name="/login_1"
            )
            # 简单校验：返回非异常且不为空则认为成功（可按实际接口调整）
            self.logged_in = bool(login_result)
            if not self.logged_in:
                logger.error(f"✗ 用户 {self.user_id} 登录失败：返回值为空或无效")
                return

            # 获取用户的知识库文件列表
            try:
                # 获取文件列表（从数据库）
                self.file_choices = _get_user_files(user_id="", index_id=1)

                if self.file_choices:
                    logger.info(
                        f"✓ 用户 {self.user_id} 登录成功，知识库文件数: {len(self.file_choices)}"
                    )
                    logger.debug(f"文件列表示例: {self.file_choices[:3]}")
                else:
                    logger.info(
                        f"✓ 用户 {self.user_id} 登录成功，知识库文件数: 0（将跳过知识库测试）"
                    )
            except Exception as e:
                logger.warning(f"获取知识库文件列表失败: {e}")
                self.file_choices = []

        except Exception as e:
            logger.error(f"✗ 用户 {self.user_id} 登录失败: {str(e)}")
            raise

    @task(3)
    def complete_simple_chat(self):
        """任务1: 简单问答（不挂载知识库）"""
        if not self.logged_in:
            return

        if USE_KB:
            logger.debug("USE_KB=True，跳过不挂载知识库的简单问答任务")
            return

        base_question = random.choice(SIMPLE_QUESTIONS)
        question, selector_choices, kb_file = _prepare_question(
            base_question,
            [],
            force=False,  # 不挂载知识库
        )

        # 每个任务创建新的会话名称和 ID
        conv_name = f"压测_{self.user_id}_{int(time.time() * 1000)}"
        conv_id = None

        # 记录总开始时间
        total_start = time.time()
        submit_duration = 0
        ai_duration = 0
        status = "success"
        note = ""
        ai_response = ""

        try:
            # === 步骤1: 提交消息 (submit_msg) ===
            submit_start = time.time()
            submit_result = self.client.predict(
                chat_input={"text": question, "files": []},
                chat_history=[],
                conv_name=conv_name,
                first_selector_choices=selector_choices,
                api_name="/submit_msg",
            )
            submit_duration = time.time() - submit_start

            # 解析 submit_msg 的返回值
            # 返回格式: [input_box, chatbot, conv_id, conv_name, ...]
            if isinstance(submit_result, (list, tuple)) and len(submit_result) >= 3:
                chat_history = submit_result[1]  # 带问题的 chat_history
                conv_id_data = submit_result[2]  # conversation_id 数据
                conv_id = _normalize_conv_id(conv_id_data)

                note = f"conv_id={conv_id}"
                logger.debug(f"提交消息成功，conv_id: {conv_id}")
            else:
                chat_history = [(question, None)]
                logger.warning(
                    f"submit_result 格式异常: {type(submit_result)}, len={len(submit_result) if isinstance(submit_result, (list, tuple)) else 'N/A'}"
                )

            # === 步骤2: 调用 AI 生成回复 (chat_fn) ===
            ai_start = time.time()
            chat_result = self.client.predict(
                chat_history=chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn",
            )
            ai_duration = time.time() - ai_start

            # 提取 AI 回复
            ai_response = _extract_reply(chat_result)

            # === 步骤3: 保存到数据库 (persist_data_source) ===
            if (
                conv_id
                and isinstance(chat_result, (list, tuple))
                and len(chat_result) >= 1
            ):
                updated_chat_history = chat_result[0]  # 包含完整对话的 chat_history
                retrieval_msg = chat_result[1] if len(chat_result) > 1 else ""

                persist_success = _persist_to_db(
                    conv_id, updated_chat_history, retrieval_msg
                )
                if persist_success:
                    note += ",persisted=yes"
                else:
                    note += ",persisted=no"
            else:
                logger.warning(
                    f"跳过数据持久化: conv_id={conv_id}, chat_result 类型={type(chat_result)}"
                )
                note += ",persisted=skip"

            # 计算总时间和速度
            total_duration = time.time() - total_start

            # 估算 tokens/s
            if ai_response:
                chinese_chars = sum(1 for c in ai_response if "\u4e00" <= c <= "\u9fff")
                english_words = len([w for w in ai_response.split() if w.isascii()])
                estimated_tokens = chinese_chars * 1.5 + english_words
                tokens_per_s = estimated_tokens / ai_duration if ai_duration > 0 else 0
            else:
                tokens_per_s = 0

            # 记录到 Locust
            events.request.fire(
                request_type="gradio",
                name="/full_workflow_simple",
                response_time=total_duration * 1000,
                response_length=len(str(ai_response)),
                exception=None,
                context={},
            )

            # 记录到 CSV
            _record_result(
                self.user_id,
                question,
                ai_response,
                submit_duration,
                ai_duration,
                total_duration,
                tokens_per_s,
                status,
                note,
            )

            logger.info(
                f"✓ {self.user_id} 完成简单问答 | "
                f"提交:{submit_duration * 1000:.0f}ms + AI:{ai_duration:.2f}s = "
                f"总计:{total_duration:.2f}s | {tokens_per_s:.1f} tokens/s"
            )

        except Exception as e:
            total_duration = time.time() - total_start
            status = "failure"
            note = str(e)[:200]

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_simple",
                response_time=total_duration * 1000,
                response_length=0,
                exception=e,
                context={},
            )

            _record_result(
                self.user_id,
                question,
                "",
                submit_duration,
                ai_duration,
                total_duration,
                0,
                status,
                note,
            )

            logger.error(f"✗ {self.user_id} 简单问答失败: {str(e)}")

    @task(2)
    def complete_context_chat(self):
        """任务2: 多轮对话（不挂载知识库）"""
        if not self.logged_in:
            return

        if USE_KB:
            logger.debug("USE_KB=True，跳过不挂载知识库的多轮对话任务")
            return

        base_second = random.choice(CONTEXT_TEMPLATES)
        second_question, selector_choices_second, kb_file = _prepare_question(
            base_second["second"],
            [],
            force=False,  # 不挂载知识库
        )

        template = base_second

        # 每个任务创建新的会话名称和 ID
        conv_name = f"压测_{self.user_id}_上下文_{int(time.time() * 1000)}"
        conv_id = None

        # === 第一轮对话 ===
        try:
            # 提交第一条消息
            first_submit_result = self.client.predict(
                chat_input={"text": template["first"], "files": []},
                chat_history=[],
                conv_name=conv_name,
                first_selector_choices=_clone_selector_choices(self.file_choices),
                api_name="/submit_msg",
            )

            # 解析结果
            if (
                isinstance(first_submit_result, (list, tuple))
                and len(first_submit_result) >= 3
            ):
                first_chat_history = first_submit_result[1]
                conv_id_data = first_submit_result[2]
                conv_id = _normalize_conv_id(conv_id_data)

                logger.debug(f"第一轮提交成功，conv_id: {conv_id}")
            else:
                first_chat_history = [(template["first"], None)]

            # 获取第一轮 AI 回复
            first_chat_result = self.client.predict(
                chat_history=first_chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn",
            )

            # 提取第一轮对话历史（包含AI回复）
            if (
                isinstance(first_chat_result, (list, tuple))
                and len(first_chat_result) >= 1
            ):
                updated_chat_history = first_chat_result[0]

                # === 保存第一轮对话到数据库 ===
                if conv_id:
                    retrieval_msg_1 = (
                        first_chat_result[1] if len(first_chat_result) > 1 else ""
                    )
                    persist_success_1 = _persist_to_db(
                        conv_id, updated_chat_history, retrieval_msg_1
                    )
                    if persist_success_1:
                        logger.debug("✓ 第一轮对话已保存到数据库")
                    else:
                        logger.warning("✗ 第一轮对话保存失败")
            else:
                logger.error("第一轮对话失败")
                return

        except Exception as e:
            logger.error(f"✗ {self.user_id} 第一轮对话失败: {str(e)}")
            # 记录失败，避免成功率被高估
            events.request.fire(
                request_type="gradio",
                name="/full_workflow_context_round1",
                response_time=0,
                response_length=0,
                exception=e,
                context={},
            )
            _record_result(
                self.user_id,
                template.get("first", ""),
                "",
                0,
                0,
                0,
                0,
                "failure",
                "context_round1_error",
            )
            return

        # === 第二轮对话（带上下文）===
        total_start = time.time()
        submit_duration = 0
        ai_duration = 0
        status = "success"
        note = "context=yes"
        ai_response = ""

        try:
            # 提交第二条消息（带历史）
            submit_start = time.time()
            second_submit_result = self.client.predict(
                chat_input={"text": second_question, "files": []},
                chat_history=updated_chat_history,
                conv_name=conv_name,
                first_selector_choices=selector_choices_second,
                api_name="/submit_msg",
            )
            submit_duration = time.time() - submit_start

            # 确保第二轮用户问题写入历史
            second_chat_history = updated_chat_history + [(second_question, None)]
            if (
                isinstance(second_submit_result, (list, tuple))
                and len(second_submit_result) >= 2
                and second_submit_result[1]
            ):
                second_chat_history = second_submit_result[1]

            # 获取第二轮 AI 回复
            ai_start = time.time()
            second_chat_result = self.client.predict(
                chat_history=second_chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn",
            )
            ai_duration = time.time() - ai_start

            # 提取 AI 回复
            ai_response = _extract_reply(second_chat_result)

            # === 步骤3: 保存到数据库 ===
            if (
                conv_id
                and isinstance(second_chat_result, (list, tuple))
                and len(second_chat_result) >= 1
            ):
                updated_chat_history = second_chat_result[0]
                retrieval_msg = (
                    second_chat_result[1] if len(second_chat_result) > 1 else ""
                )

                persist_success = _persist_to_db(
                    conv_id, updated_chat_history, retrieval_msg
                )
                if persist_success:
                    note += ",persisted=yes"
                else:
                    note += ",persisted=no"
            else:
                logger.warning(f"跳过第二轮数据持久化: conv_id={conv_id}")
                note += ",persisted=skip"

            total_duration = time.time() - total_start

            # 计算 tokens/s
            if ai_response:
                chinese_chars = sum(1 for c in ai_response if "\u4e00" <= c <= "\u9fff")
                english_words = len([w for w in ai_response.split() if w.isascii()])
                estimated_tokens = chinese_chars * 1.5 + english_words
                tokens_per_s = estimated_tokens / ai_duration if ai_duration > 0 else 0
            else:
                tokens_per_s = 0

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_context",
                response_time=total_duration * 1000,
                response_length=len(str(ai_response)),
                exception=None,
                context={},
            )

            if kb_file:
                note += f",kb_file={kb_file}"

            _record_result(
                self.user_id,
                second_question,
                ai_response,
                submit_duration,
                ai_duration,
                total_duration,
                tokens_per_s,
                status,
                note,
            )

            logger.info(
                f"✓ {self.user_id} 完成上下文对话 | "
                f"提交:{submit_duration * 1000:.0f}ms + AI:{ai_duration:.2f}s = "
                f"总计:{total_duration:.2f}s | {tokens_per_s:.1f} tokens/s"
            )

        except Exception as e:
            total_duration = time.time() - total_start
            status = "failure"
            note = f"context=yes,error={str(e)[:100]}"

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_context",
                response_time=total_duration * 1000,
                response_length=0,
                exception=e,
                context={},
            )

            if kb_file:
                note += f",kb_file={kb_file}"

            _record_result(
                self.user_id,
                second_question,
                "",
                submit_duration,
                ai_duration,
                total_duration,
                0,
                status,
                note,
            )

            logger.error(f"✗ {self.user_id} 上下文对话失败: {str(e)}")

    @task(1)
    def complete_simple_chat_with_kb(self):
        """任务3: 简单问答（挂载知识库）"""
        if not self.logged_in:
            return

        if not USE_KB:
            logger.debug("USE_KB=False，跳过知识库简单任务")
            return

        if not self.file_choices:
            logger.debug(f"{self.user_id} 没有知识库文件，跳过知识库简单对话")
            return

        base_question = random.choice(KB_SIMPLE_QUESTIONS)
        question, selector_choices, kb_file = _prepare_question(
            base_question, self.file_choices, force=True
        )

        # 每个任务创建新的会话名称和 ID
        conv_name = f"压测_{self.user_id}_知识库简单_{int(time.time() * 1000)}"
        conv_id = None

        total_start = time.time()
        submit_duration = 0
        ai_duration = 0
        status = "success"
        note = f"kb_file={kb_file}" if kb_file else "kb_file=unknown"
        ai_response = ""

        try:
            submit_start = time.time()
            submit_result = self.client.predict(
                chat_input={"text": question, "files": []},
                chat_history=[],
                conv_name=conv_name,
                first_selector_choices=selector_choices,
                api_name="/submit_msg",
            )
            submit_duration = time.time() - submit_start

            if isinstance(submit_result, (list, tuple)) and len(submit_result) >= 3:
                chat_history = submit_result[1]
                conv_id_data = submit_result[2]
                conv_id = _normalize_conv_id(conv_id_data)
                note += f",conv_id={conv_id}"
            else:
                chat_history = [(question, None)]
                logger.warning("知识库简单 submit_result 格式异常")

            # 调用 chat_fn 并明确挂载文件
            ai_start = time.time()
            chat_result = self.client.predict(
                chat_history=chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="select",
                param_12=[f[1] for f in self.file_choices if f[0] == kb_file],
                api_name="/chat_fn",
            )
            ai_duration = time.time() - ai_start

            ai_response = _extract_reply(chat_result)

            if (
                conv_id
                and isinstance(chat_result, (list, tuple))
                and len(chat_result) >= 1
            ):
                updated_chat_history = chat_result[0]
                retrieval_msg = chat_result[1] if len(chat_result) > 1 else ""
                persist_success = _persist_to_db(
                    conv_id, updated_chat_history, retrieval_msg
                )
                note += ",persisted=yes" if persist_success else ",persisted=no"
            else:
                note += ",persisted=skip"

            total_duration = time.time() - total_start
            chinese_chars = sum(1 for c in ai_response) if ai_response else 0
            english_words = (
                len([w for w in ai_response.split() if w.isascii()])
                if ai_response
                else 0
            )
            estimated_tokens = chinese_chars * 1.5 + english_words
            tokens_per_s = estimated_tokens / ai_duration if ai_duration > 0 else 0

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_kb_simple",
                response_time=total_duration * 1000,
                response_length=len(str(ai_response)),
                exception=None,
                context={},
            )

            _record_result(
                self.user_id,
                question,
                ai_response,
                submit_duration,
                ai_duration,
                total_duration,
                tokens_per_s,
                status,
                note,
            )

            logger.info(
                f"✓ {self.user_id} 知识库简单 | "
                f"提交:{submit_duration * 1000:.0f}ms + AI:{ai_duration:.2f}s = "
                f"总计:{total_duration:.2f}s | {tokens_per_s:.1f} tokens/s"
            )

        except Exception as e:
            total_duration = time.time() - total_start
            status = "failure"
            note += f",error={str(e)[:100]}"

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_kb_simple",
                response_time=total_duration * 1000,
                response_length=0,
                exception=e,
                context={},
            )

            _record_result(
                self.user_id,
                question,
                "",
                submit_duration,
                ai_duration,
                total_duration,
                0,
                status,
                note,
            )

            logger.error(f"✗ {self.user_id} 知识库简单失败: {str(e)}")

    @task(1)
    def complete_context_chat_with_kb(self):
        """任务4: 多轮对话（挂载知识库）"""
        if not self.logged_in:
            return

        if not USE_KB:
            logger.debug("USE_KB=False，跳过知识库多轮任务")
            return

        if not self.file_choices:
            logger.debug(f"{self.user_id} 没有知识库文件，跳过知识库多轮对话")
            return

        base_second = random.choice(KB_CONTEXT_TEMPLATES)
        second_question, selector_choices_second, kb_file = _prepare_question(
            base_second["second"], self.file_choices, force=True
        )

        template = base_second
        conv_name = f"压测_{self.user_id}_知识库上下文_{int(time.time() * 1000)}"
        conv_id = None

        try:
            first_submit_result = self.client.predict(
                chat_input={"text": template["first"], "files": []},
                chat_history=[],
                conv_name=conv_name,
                first_selector_choices=_clone_selector_choices(self.file_choices),
                api_name="/submit_msg",
            )

            if (
                isinstance(first_submit_result, (list, tuple))
                and len(first_submit_result) >= 3
            ):
                first_chat_history = first_submit_result[1]
                conv_id_data = first_submit_result[2]
                conv_id = _normalize_conv_id(conv_id_data)
            else:
                first_chat_history = [(template["first"], None)]

            first_chat_result = self.client.predict(
                chat_history=first_chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="select",
                param_12=[f[1] for f in self.file_choices if f[0] == kb_file],
                api_name="/chat_fn",
            )

            if (
                isinstance(first_chat_result, (list, tuple))
                and len(first_chat_result) >= 1
            ):
                updated_chat_history = first_chat_result[0]
                if conv_id:
                    retrieval_msg_1 = (
                        first_chat_result[1] if len(first_chat_result) > 1 else ""
                    )
                    _persist_to_db(conv_id, updated_chat_history, retrieval_msg_1)
            else:
                logger.error("第一轮对话失败")
                return

        except Exception as e:
            logger.error(f"✗ {self.user_id} 知识库第一轮失败: {str(e)}")
            events.request.fire(
                request_type="gradio",
                name="/full_workflow_kb_context_round1",
                response_time=0,
                response_length=0,
                exception=e,
                context={},
            )
            _record_result(
                self.user_id,
                template.get("first", ""),
                "",
                0,
                0,
                0,
                0,
                "failure",
                "kb_context_round1_error",
            )
            return

        total_start = time.time()
        submit_duration = 0
        ai_duration = 0
        status = "success"
        note = f"context=yes,kb_file={kb_file}"
        ai_response = ""

        try:
            submit_start = time.time()
            second_submit_result = self.client.predict(
                chat_input={"text": second_question, "files": []},
                chat_history=updated_chat_history,
                conv_name=conv_name,
                first_selector_choices=selector_choices_second,
                api_name="/submit_msg",
            )
            submit_duration = time.time() - submit_start

            # 确保第二轮用户问题写入历史
            second_chat_history = updated_chat_history + [(second_question, None)]
            if (
                isinstance(second_submit_result, (list, tuple))
                and len(second_submit_result) >= 2
                and second_submit_result[1]
            ):
                second_chat_history = second_submit_result[1]

            ai_start = time.time()
            second_chat_result = self.client.predict(
                chat_history=second_chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="select",
                param_12=[f[1] for f in self.file_choices if f[0] == kb_file],
                api_name="/chat_fn",
            )
            ai_duration = time.time() - ai_start

            ai_response = _extract_reply(second_chat_result)

            if (
                conv_id
                and isinstance(second_chat_result, (list, tuple))
                and len(second_chat_result) >= 1
            ):
                updated_chat_history = second_chat_result[0]
                retrieval_msg = (
                    second_chat_result[1] if len(second_chat_result) > 1 else ""
                )
                persist_success = _persist_to_db(
                    conv_id, updated_chat_history, retrieval_msg
                )
                note += ",persisted=yes" if persist_success else ",persisted=no"
            else:
                note += ",persisted=skip"

            total_duration = time.time() - total_start
            chinese_chars = sum(1 for c in ai_response) if ai_response else 0
            english_words = (
                len([w for w in ai_response.split() if w.isascii()])
                if ai_response
                else 0
            )
            estimated_tokens = chinese_chars * 1.5 + english_words
            tokens_per_s = estimated_tokens / ai_duration if ai_duration > 0 else 0

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_kb_context",
                response_time=total_duration * 1000,
                response_length=len(str(ai_response)),
                exception=None,
                context={},
            )

            _record_result(
                self.user_id,
                second_question,
                ai_response,
                submit_duration,
                ai_duration,
                total_duration,
                tokens_per_s,
                status,
                note,
            )

            logger.info(
                f"✓ {self.user_id} 知识库多轮 | "
                f"提交:{submit_duration * 1000:.0f}ms + AI:{ai_duration:.2f}s = "
                f"总计:{total_duration:.2f}s | {tokens_per_s:.1f} tokens/s"
            )

        except Exception as e:
            total_duration = time.time() - total_start
            status = "failure"
            note += f",error={str(e)[:100]}"

            events.request.fire(
                request_type="gradio",
                name="/full_workflow_kb_context",
                response_time=total_duration * 1000,
                response_length=0,
                exception=e,
                context={},
            )

            _record_result(
                self.user_id,
                second_question,
                "",
                submit_duration,
                ai_duration,
                total_duration,
                0,
                status,
                note,
            )

            logger.error(f"✗ {self.user_id} 知识库多轮失败: {str(e)}")

    def on_stop(self):
        """测试结束"""
        logger.info(f"用户 {self.user_id} 测试结束")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时统计"""
    with _results_lock:
        count = _stats.get("count", 0)
        success_count = _stats.get("success_count", 0)
        failure_count = _stats.get("failure_count", 0)
        sum_ai = _stats.get("sum_ai_duration", 0.0)

        if count > 0:
            avg_submit = _stats["sum_submit_duration"] / count
            avg_total = _stats["sum_total_duration"] / count
            avg_ai = sum_ai / count
            avg_tokens = _stats["sum_tokens_per_s"] / count
            success_rate = success_count / count * 100
        else:
            avg_submit = avg_total = avg_ai = avg_tokens = success_rate = 0.0

        # 写入统计行（修复字段对齐）
        _ensure_results_file()
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # 表头: user_id, user_input, ai_response, submit_duration_s, ai_duration_s, total_duration_s, tokens_per_s, status, note, USE_KB, task_name
            writer.writerow(
                [
                    "AVERAGE",  # user_id
                    f"{count} samples",  # user_input
                    "",  # ai_response
                    f"{avg_submit:.3f}",  # submit_duration_s
                    f"{avg_ai:.3f}",  # ai_duration_s（直接累计）
                    f"{avg_total:.3f}",  # total_duration_s
                    f"{avg_tokens:.2f}",  # tokens_per_s
                    f"{success_count}✓/{failure_count}✗",  # status
                    f"success_rate={success_rate:.1f}%",  # note
                    str(USE_KB),
                    "AVERAGE",
                ]
            )

    print(f"\n{'=' * 60}")
    print("压力测试完成 - 完整用户流程")
    print(f"{'=' * 60}")
    print(f"总样本数: {count}")
    print(f"成功: {success_count} | 失败: {failure_count}")
    print(f"成功率: {success_rate:.1f}%")
    print(f"平均提交时间: {avg_submit:.3f}s")
    print(f"平均AI响应时间: {avg_ai:.3f}s")
    print(f"平均总时间: {avg_total:.3f}s")
    print(f"平均生成速度: {avg_tokens:.2f} tokens/s")
    print(f"{'=' * 60}\n")
