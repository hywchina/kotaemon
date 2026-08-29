import gradio as gr
from sqlmodel import Session, select

from ktem.app import BasePage
from ktem.asr.ui import ASRModelManagement, VoiceprintManagement
from ktem.db.models import User, engine
from ktem.embeddings.ui import EmbeddingManagement
from ktem.index.ui import IndexManagement
from ktem.llms.ui import LLMManagement
from ktem.rerankings.ui import RerankingManagement

from .user import UserManagement


class ResourcesTab(BasePage):
    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Tab(
            "索引集合"
        ) as self.index_management_tab:  # translate Index Collections --》索引集合
            self.index_management = IndexManagement(self._app)

        with gr.Tab(
            "大语言模型"
        ) as self.llm_management_tab:  # translate LLMs --》大语言模型
            self.llm_management = LLMManagement(self._app)

        with gr.Tab(
            "嵌入模型"
        ) as self.emb_management_tab:  # translate Embeddings --》嵌入模型
            self.emb_management = EmbeddingManagement(self._app)

        with gr.Tab(
            "重排序模型"
        ) as self.rerank_management_tab:  # translate Rerankings --》重排序模型
            self.rerank_management = RerankingManagement(self._app)

        with gr.Tab(
            "语音识别模型", visible=not self._app.f_user_management
        ) as self.asr_model_management_tab:
            self.asr_model_management = ASRModelManagement(self._app)

        with gr.Tab(
            "声纹库", visible=not self._app.f_user_management
        ) as self.voiceprint_management_tab:
            self.voiceprint_management = VoiceprintManagement(self._app)

        if self._app.f_user_management:
            with gr.Tab(
                "用户管理", visible=False
            ) as self.user_management_tab:  # translate Users --》用户管理
                self.user_management = UserManagement(self._app)

    def on_subscribe_public_events(self):
        if self._app.f_user_management:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.toggle_admin_management,
                    "inputs": [self._app.user_id],
                    "outputs": [
                        self.user_management_tab,
                        self.asr_model_management_tab,
                        self.voiceprint_management_tab,
                    ],
                    "show_progress": "hidden",
                },
            )

            self._app.subscribe_event(
                name="onSignOut",
                definition={
                    "fn": self.toggle_admin_management,
                    "inputs": [self._app.user_id],
                    "outputs": [
                        self.user_management_tab,
                        self.asr_model_management_tab,
                        self.voiceprint_management_tab,
                    ],
                    "show_progress": "hidden",
                },
            )

    def toggle_admin_management(self, user_id):
        """Show administrator-only resource tabs for administrators."""
        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
            if user and user.admin:
                return (
                    gr.update(visible=True),
                    gr.update(visible=True),
                    gr.update(visible=True),
                )

            return (
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )
