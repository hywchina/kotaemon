"""
Locust 压力测试脚本 - 测试 /submit_msg + /chat_fn 工作流
模拟多个用户同时向 AI 辅助诊断系统提交消息并获取回复
完整流程: submit_msg (提交) -> chat_fn (获取 AI 回复)
"""
from locust import User, task, between, events
from gradio_client import Client
import time
import random
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GradioUser(User):
    """
    模拟 Gradio 应用用户
    """
    # 用户任务之间的等待时间（秒）
    wait_time = between(1, 3)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.user_id = None
        self.conversation_name = None
        
    def on_start(self):
        """
        每个用户启动时执行一次
        初始化 Gradio Client
        """
        try:
            self.user_id = f"user_{random.randint(1000, 9999)}"
            self.conversation_name = f"{self.user_id}_conv_{int(time.time())}"
            self.client = Client("http://localhost:7860/")
            logger.info(f"用户 {self.user_id} 初始化成功，会话名: {self.conversation_name}")
        except Exception as e:
            logger.error(f"用户 {self.user_id} 初始化失败: {str(e)}")
            raise
    
    @task(3)
    def submit_and_chat_simple(self):
        """
        任务1: 提交简单消息并获取 AI 回复（权重3）
        完整流程: submit_msg -> chat_fn
        """
        test_messages = [
            "你好，请介绍一下你的功能。",
            "你能帮我做什么？",
            "请简单介绍一下这个系统。",
            "帮我分析患者的病情。",
            "如何使用这个辅助诊断系统？",
        ]
        
        message = random.choice(test_messages)
        
        start_time = time.time()
        try:
            # 步骤 1: 提交消息
            submit_result = self.client.predict(
                chat_input={"text": message, "files": []},
                chat_history=[],
                conv_name=self.conversation_name,
                first_selector_choices=[],
                api_name="/submit_msg"
            )
            
            # 检查返回值并提取对话历史
            if isinstance(submit_result, (list, tuple)) and len(submit_result) >= 2:
                chat_history = submit_result[1]
            else:
                chat_history = [(message, None)]
            
            # 步骤 2: 获取 AI 回复
            chat_result = self.client.predict(
                chat_history=chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn"
            )
            
            # 计算响应时间
            response_time = (time.time() - start_time) * 1000
            
            # 记录成功的请求
            events.request.fire(
                request_type="gradio",
                name="/submit_msg+chat_fn_simple",
                response_time=response_time,
                response_length=len(str(chat_result)),
                exception=None,
                context={}
            )
            
            logger.info(f"用户 {self.user_id} 完整工作流成功，响应时间: {response_time:.2f}ms")
            
        except Exception as e:
            # 计算失败请求的时间
            response_time = (time.time() - start_time) * 1000
            
            # 记录失败的请求
            events.request.fire(
                request_type="gradio",
                name="/submit_msg+chat_fn_simple",
                response_time=response_time,
                response_length=0,
                exception=e,
                context={}
            )
            
            logger.error(f"用户 {self.user_id} 完整工作流失败: {str(e)}")
    
    @task(2)
    def submit_and_chat_with_history(self):
        """
        任务2: 提交带历史记录的消息并获取 AI 回复（权重2）
        完整流程: submit_msg -> chat_fn
        """
        # 模拟对话历史
        chat_history_templates = [
            [
                ("你好", "你好！我是 AI 辅助诊断系统，很高兴为您服务。")
            ],
            [
                ("患者男性，65岁", "好的，请继续描述患者的症状。")
            ],
            [
                ("主诉胸闷3天", "请问有其他伴随症状吗？")
            ],
        ]
        
        initial_history = random.choice(chat_history_templates)
        
        follow_up_messages = [
            "伴有气促，活动后加重。",
            "既往有高血压病史10年。",
            "目前血压180/100mmHg。",
            "需要如何调整治疗方案？",
            "有什么注意事项？",
        ]
        
        message = random.choice(follow_up_messages)
        
        start_time = time.time()
        try:
            # 步骤 1: 提交消息（带历史记录）
            submit_result = self.client.predict(
                chat_input={"text": message, "files": []},
                chat_history=initial_history,
                conv_name=self.conversation_name,
                first_selector_choices=[],
                api_name="/submit_msg"
            )
            
            # 提取更新后的对话历史
            if isinstance(submit_result, (list, tuple)) and len(submit_result) >= 2:
                chat_history = submit_result[1]
            else:
                # 如果返回格式不对，手动构建
                chat_history = initial_history + [(message, None)]
            
            # 步骤 2: 获取 AI 回复
            chat_result = self.client.predict(
                chat_history=chat_history,
                llm_type="",
                use_citation="highlight",
                language="zh",
                param_11="disabled",
                param_12=[],
                api_name="/chat_fn"
            )
            
            response_time = (time.time() - start_time) * 1000
            
            events.request.fire(
                request_type="gradio",
                name="/submit_msg+chat_fn_history",
                response_time=response_time,
                response_length=len(str(chat_result)),
                exception=None,
                context={}
            )
            
            logger.info(f"用户 {self.user_id} 历史工作流成功，响应时间: {response_time:.2f}ms")
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            events.request.fire(
                request_type="gradio",
                name="/submit_msg+chat_fn_history",
                response_time=response_time,
                response_length=0,
                exception=e,
                context={}
            )
            
            logger.error(f"用户 {self.user_id} 历史工作流失败: {str(e)}")
    
    def on_stop(self):
        """
        每个用户停止时执行一次
        """
        logger.info(f"用户 {self.user_id} 测试结束")


# Locust 配置（可以通过命令行覆盖）
# 默认用户数: 10
# 默认孵化速率: 每秒增加 2 个用户
