"""
Locust 压力测试脚本 - 测试 Kotaemon AI 辅助诊断系统
模拟多个用户同时使用 /chat_fn 接口进行对话
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
        
    def on_start(self):
        """
        每个用户启动时执行一次
        初始化 Gradio Client
        """
        try:
            self.user_id = f"user_{random.randint(1000, 9999)}"
            self.client = Client("http://localhost:7860/")
            logger.info(f"用户 {self.user_id} 初始化成功")
        except Exception as e:
            logger.error(f"用户 {self.user_id} 初始化失败: {str(e)}")
            raise
    
    @task(3)
    def chat_simple_question(self):
        """
        任务1: 发送简单问题并获取回复（权重3）
        """
        test_questions = [
            "你好，请介绍一下你的功能。",
            "你能帮我做什么？",
            "请简单介绍一下你自己。",
            "你有哪些主要功能？",
            "如何使用这个系统？",
        ]
        
        question = random.choice(test_questions)
        
        # 构建对话历史
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
                api_name="/chat_fn"
            )
            
            # 计算响应时间
            response_time = (time.time() - start_time) * 1000
            
            # 记录成功的请求
            events.request.fire(
                request_type="gradio",
                name="/chat_fn_simple",
                response_time=response_time,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
            
            logger.info(f"用户 {self.user_id} 简单问题成功，响应时间: {response_time:.2f}ms")
            
        except Exception as e:
            # 计算失败请求的时间
            response_time = (time.time() - start_time) * 1000
            
            # 记录失败的请求
            events.request.fire(
                request_type="gradio",
                name="/chat_fn_simple",
                response_time=response_time,
                response_length=0,
                exception=e,
                context={}
            )
            
            logger.error(f"用户 {self.user_id} 简单问题失败: {str(e)}")
    
    @task(2)
    def chat_with_context(self):
        """
        任务2: 带上下文的多轮对话（权重2）
        """
        # 模拟多轮对话场景
        conversation_templates = [
            [
                ("患者男性，65岁，主诉胸闷3天。", "请问有其他症状吗？"),
                ("伴有气促，活动后加重。", None)
            ],
            [
                ("患者女性，45岁，血压180/100mmHg。", "高血压的情况，请继续。"),
                ("既往有高血压病史10年，服药不规律。", None)
            ],
            [
                ("患者咳嗽2周，伴发热。", "体温多少？有痰吗？"),
                ("体温38.5°C，有黄痰。", None)
            ],
        ]
        
        chat_history = random.choice(conversation_templates)
        
        start_time = time.time()
        try:
            result = self.client.predict(
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
                name="/chat_fn_context",
                response_time=response_time,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
            
            logger.info(f"用户 {self.user_id} 上下文对话成功，响应时间: {response_time:.2f}ms")
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            events.request.fire(
                request_type="gradio",
                name="/chat_fn_context",
                response_time=response_time,
                response_length=0,
                exception=e,
                context={}
            )
            
            logger.error(f"用户 {self.user_id} 上下文对话失败: {str(e)}")
    
    def on_stop(self):
        """
        每个用户停止时执行一次
        """
        logger.info(f"用户 {self.user_id} 测试结束")


# Locust 配置（可以通过命令行覆盖）
# 默认用户数: 10
# 默认孵化速率: 每秒增加 2 个用户
