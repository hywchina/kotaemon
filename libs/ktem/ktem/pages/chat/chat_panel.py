import gradio as gr
from ktem.app import BasePage
from theflow.settings import settings as flowsettings

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)

if not KH_DEMO_MODE:
    PLACEHOLDER_TEXT = (
        "这是一次新会话的开始。\n"
        # "您可以上传文件或输入网页URL开始使用。"
        # "更多功能（如图谱检索）请访问文件管理标签页。"
    )  # translate This is the beginning... --》这是一次新对话的开始...
else:
    PLACEHOLDER_TEXT = (
        "Welcome to Kotaemon Demo. "
        "Start by browsing preloaded conversations to get onboard.\n"
        "Check out Hint section for more tips."
    )


class ChatPanel(BasePage):
    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        self.chatbot = gr.Chatbot(
            label=self._app.app_name,
            placeholder=PLACEHOLDER_TEXT,
            show_label=False,
            elem_id="main-chat-bot",
            show_copy_button=True,
            likeable=True,
            bubble_full_width=False,
        )
        with gr.Row():
            self.text_input = gr.MultimodalTextbox(
                interactive=True,
                scale=20,
                file_count="multiple",  # translate
                placeholder=(  # translate
                    "输入消息，或@filename文件开始会话"
                ),  # translate Type a message, search the @web, or tag a file with @filename --》输入消息、使用@web搜索或通过@filename标记文件
                container=False,
                show_label=False,
                elem_id="chat-input",
            )

    def submit_msg(self, chat_input, chat_history):
        """Submit a message to the chatbot"""
        return "", chat_history + [(chat_input, None)]
