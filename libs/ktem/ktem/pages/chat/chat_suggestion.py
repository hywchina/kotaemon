import gradio as gr
from ktem.app import BasePage
from theflow.settings import settings as flowsettings


class ChatSuggestion(BasePage):
    CHAT_SAMPLES = getattr(
        flowsettings,
        "KH_FEATURE_CHAT_SUGGESTION_SAMPLES",
        [
            "根据上传的病历或病人基本情况生成简要总结",
            "基于病例信息自动生成 FAQ，帮助快速理解和解答常见疑问",
            "用要点形式列出最重要的诊疗关键信息",
        ],
    )

    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        self.chat_samples = [[each] for each in self.CHAT_SAMPLES]
        with gr.Accordion(
            label="诊断建议",
            visible=getattr(flowsettings, "KH_FEATURE_CHAT_SUGGESTION", False),
        ) as self.accordion:
            self.default_example = gr.State(
                value=self.chat_samples,
            )
            self.examples = gr.DataFrame(
                value=self.chat_samples,
                headers=["Next Question"],
                interactive=False,
                elem_id="chat-suggestion",
                wrap=True,
            )

    def as_gradio_component(self):
        return self.examples

    def select_example(self, ev: gr.SelectData):
        return {"text": ev.value}
