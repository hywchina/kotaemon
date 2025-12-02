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

# 添加项目路径到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入数据库模型（延迟导入避免循环依赖）
try:
    from libs.ktem.ktem.db.models import engine, Conversation
    from sqlmodel import Session, select
    DB_AVAILABLE = True
    logger.info("✓ 数据库模块导入成功")
except Exception as e:
    logger.warning(f"✗ 无法导入数据库模型: {e}，将跳过数据持久化")
    DB_AVAILABLE = False

# 结果文件与线程安全计数器
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "full_workflow_results.csv")
_results_lock = threading.Lock()
_stats = {
    "count": 0,
    "sum_submit_duration": 0.0,
    "sum_total_duration": 0.0,
    "sum_tokens_per_s": 0.0,
    "success_count": 0,
    "failure_count": 0
}

# 登录凭据
USERNAME = "admin"
PASSWORD = "admin"


def _ensure_results_file():
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "user_id", "user_input", "ai_response",
                "submit_duration_s", "ai_duration_s", "total_duration_s",
                "tokens_per_s", "status", "note"
            ])


def _record_result(user_id, user_input, ai_response, submit_duration, ai_duration,
                   total_duration, tokens_per_s, status="success", note=""):
    _ensure_results_file()
    with _results_lock:
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                user_id,
                user_input[:100],
                ai_response[:200] if ai_response else "",
                f"{submit_duration:.3f}",
                f"{ai_duration:.3f}",
                f"{total_duration:.3f}",
                f"{tokens_per_s:.2f}",
                status,
                note
            ])
        _stats["count"] += 1
        _stats["sum_submit_duration"] += submit_duration
        _stats["sum_total_duration"] += total_duration
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
            
            logger.info(f"找到对话记录，当前消息数: {len(result.data_source.get('messages', []))}")
            
            # 更新 data_source
            data_source = result.data_source or {}
            data_source['messages'] = chat_history
            
            # 添加 retrieval_messages（如果有）
            if retrieval_msg:
                retrieval_history = data_source.get('retrieval_messages', [])
                retrieval_history.append(retrieval_msg)
                data_source['retrieval_messages'] = retrieval_history
            
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
        self.conv_name = None
        self.conv_id = None
        self.logged_in = False

    def on_start(self):
        """每个用户启动时执行 - 登录"""
        try:
            self.user_id = f"user_{random.randint(1000, 9999)}"
            self.conv_name = f"压测_{self.user_id}_{int(time.time())}"
            self.client = Client("http://localhost:7860/")
            
            # 登录
            self.client.predict(usn=USERNAME, pwd=PASSWORD, api_name="/login_1")
            self.logged_in = True
            
            logger.info(f"✓ 用户 {self.user_id} 登录成功")
        except Exception as e:
            logger.error(f"✗ 用户 {self.user_id} 登录失败: {str(e)}")
            raise

    @task(3)
    def complete_simple_chat(self):
        """任务1: 完整的简单问答流程（权重3）"""
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
                conv_name=self.conv_name,
                first_selector_choices=[],
                api_name="/submit_msg"
            )
            submit_duration = time.time() - submit_start
            
            # 解析 submit_msg 的返回值
            if isinstance(submit_result, (list, tuple)) and len(submit_result) >= 3:
                chat_history = submit_result[1]  # 带问题的 chat_history
                conv_id_data = submit_result[2]  # conversation_id 数据
                
                # 提取真实的 conv_id
                if isinstance(conv_id_data, dict):
                    if 'value' in conv_id_data:
                        self.conv_id = conv_id_data['value']
                    elif 'choices' in conv_id_data and len(conv_id_data['choices']) > 0:
                        self.conv_id = conv_id_data['choices'][0][1]
                else:
                    self.conv_id = conv_id_data
                    
                note = f"conv_id={self.conv_id}"
            else:
                chat_history = [(question, None)]
                
            # === 步骤2: 调用 AI 生成回复 (chat_fn) ===
            ai_start = time.time()
            chat_result = self.client.predict(
                chat_history=chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn"
            )
            ai_duration = time.time() - ai_start
            
            # 提取 AI 回复
            ai_response = _extract_reply(chat_result)
            
            # === 步骤3: 保存到数据库 (persist_data_source) ===
            if self.conv_id and isinstance(chat_result, (list, tuple)) and len(chat_result) >= 1:
                updated_chat_history = chat_result[0]  # 包含完整对话的 chat_history
                retrieval_msg = chat_result[1] if len(chat_result) > 1 else ""
                
                persist_success = _persist_to_db(self.conv_id, updated_chat_history, retrieval_msg)
                if persist_success:
                    note += ",persisted=yes"
                else:
                    note += ",persisted=no"
            
            # 计算总时间和速度
            total_duration = time.time() - total_start
            
            # 估算 tokens/s
            if ai_response:
                chinese_chars = sum(1 for c in ai_response if '\u4e00' <= c <= '\u9fff')
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
                context={}
            )

            # 记录到 CSV
            _record_result(
                self.user_id, question, ai_response,
                submit_duration, ai_duration, total_duration,
                tokens_per_s, status, note
            )

            logger.info(
                f"✓ {self.user_id} 完成简单问答 | "
                f"提交:{submit_duration*1000:.0f}ms + AI:{ai_duration:.2f}s = "
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
                context={}
            )
            
            _record_result(
                self.user_id, question, "",
                submit_duration, ai_duration, total_duration,
                0, status, note
            )
            
            logger.error(f"✗ {self.user_id} 简单问答失败: {str(e)}")

    @task(2)
    def complete_context_chat(self):
        """任务2: 完整的多轮对话流程（权重2）"""
        if not self.logged_in:
            return
            
        conversation_templates = [
            {
                "first": "患者男性，65岁，主诉胸闷3天。",
                "second": "伴有气促，活动后加重。"
            },
            {
                "first": "患者女性，45岁，血压180/100mmHg。",
                "second": "既往有高血压病史10年，服药不规律。"
            },
            {
                "first": "患者咳嗽2周，伴发热。",
                "second": "体温38.5°C，有黄痰。"
            },
        ]

        template = random.choice(conversation_templates)
        
        # === 第一轮对话 ===
        try:
            # 提交第一条消息
            first_submit_result = self.client.predict(
                chat_input={"text": template["first"], "files": []},
                chat_history=[],
                conv_name=self.conv_name,
                first_selector_choices=[],
                api_name="/submit_msg"
            )
            
            # 解析结果
            if isinstance(first_submit_result, (list, tuple)) and len(first_submit_result) >= 3:
                first_chat_history = first_submit_result[1]
                conv_id_data = first_submit_result[2]
                
                if isinstance(conv_id_data, dict):
                    if 'value' in conv_id_data:
                        self.conv_id = conv_id_data['value']
                    elif 'choices' in conv_id_data and len(conv_id_data['choices']) > 0:
                        self.conv_id = conv_id_data['choices'][0][1]
                else:
                    self.conv_id = conv_id_data
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
                api_name="/chat_fn"
            )
            
            # 提取第一轮对话历史（包含AI回复）
            if isinstance(first_chat_result, (list, tuple)) and len(first_chat_result) >= 1:
                updated_chat_history = first_chat_result[0]
            else:
                logger.error(f"第一轮对话失败")
                return
                
        except Exception as e:
            logger.error(f"✗ {self.user_id} 第一轮对话失败: {str(e)}")
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
                chat_input={"text": template["second"], "files": []},
                chat_history=updated_chat_history,
                conv_name=self.conv_name,
                first_selector_choices=[],
                api_name="/submit_msg"
            )
            submit_duration = time.time() - submit_start
            
            # 解析结果
            if isinstance(second_submit_result, (list, tuple)) and len(second_submit_result) >= 2:
                second_chat_history = second_submit_result[1]
            else:
                second_chat_history = updated_chat_history + [(template["second"], None)]
            
            # 获取第二轮 AI 回复
            ai_start = time.time()
            second_chat_result = self.client.predict(
                chat_history=second_chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn"
            )
            ai_duration = time.time() - ai_start
            
            # 提取 AI 回复
            ai_response = _extract_reply(second_chat_result)
            
            # === 步骤3: 保存到数据库 ===
            if self.conv_id and isinstance(second_chat_result, (list, tuple)) and len(second_chat_result) >= 1:
                updated_chat_history = second_chat_result[0]
                retrieval_msg = second_chat_result[1] if len(second_chat_result) > 1 else ""
                
                persist_success = _persist_to_db(self.conv_id, updated_chat_history, retrieval_msg)
                if persist_success:
                    note += ",persisted=yes"
                else:
                    note += ",persisted=no"
            
            total_duration = time.time() - total_start
            
            # 计算 tokens/s
            if ai_response:
                chinese_chars = sum(1 for c in ai_response if '\u4e00' <= c <= '\u9fff')
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
                context={}
            )

            _record_result(
                self.user_id, template["second"], ai_response,
                submit_duration, ai_duration, total_duration,
                tokens_per_s, status, note
            )

            logger.info(
                f"✓ {self.user_id} 完成上下文对话 | "
                f"提交:{submit_duration*1000:.0f}ms + AI:{ai_duration:.2f}s = "
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
                context={}
            )
            
            _record_result(
                self.user_id, template["second"], "",
                submit_duration, ai_duration, total_duration,
                0, status, note
            )
            
            logger.error(f"✗ {self.user_id} 上下文对话失败: {str(e)}")

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
        
        if count > 0:
            avg_submit = _stats["sum_submit_duration"] / count
            avg_total = _stats["sum_total_duration"] / count
            avg_tokens = _stats["sum_tokens_per_s"] / count
            success_rate = (success_count / count * 100)
        else:
            avg_submit = avg_total = avg_tokens = success_rate = 0.0

        # 写入统计行
        _ensure_results_file()
        with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "AVERAGE",
                f"{count} samples",
                "",
                f"{avg_submit:.3f}",
                f"{avg_total-avg_submit:.3f}",
                f"{avg_total:.3f}",
                f"{avg_tokens:.2f}",
                f"{success_count}✓/{failure_count}✗",
                f"success_rate={success_rate:.1f}%"
            ])

    print(f"\n{'='*60}")
    print(f"压力测试完成 - 完整用户流程")
    print(f"{'='*60}")
    print(f"总样本数: {count}")
    print(f"成功: {success_count} | 失败: {failure_count}")
    print(f"成功率: {success_rate:.1f}%")
    print(f"平均提交时间: {avg_submit:.3f}s")
    print(f"平均AI响应时间: {avg_total-avg_submit:.3f}s")
    print(f"平均总时间: {avg_total:.3f}s")
    print(f"平均生成速度: {avg_tokens:.2f} tokens/s")
    print(f"{'='*60}\n")
