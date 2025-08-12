from typing import Optional

import gradio as gr
from ktem.app import BasePage
from ktem.db.models import IssueReport, engine
from sqlmodel import Session


class ReportIssue(BasePage):
    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Accordion(label="反馈", open=False, elem_id="report-accordion"):  # translate Feedback --》反馈
            self.correctness = gr.Radio(  # translate
                choices=[  # translate
                    ("回答正确", "correct"),  # translate The answer is correct --》回答正确
                    ("回答错误", "incorrect"),  # translate The answer is incorrect --》回答错误
                ],
                label="准确性评估:",  # translate Correctness: --》准确性评估:
            )
            self.issues = gr.CheckboxGroup(
                choices=[
                    ("回答内容不当", "offensive"),  # translate The answer is offensive --》回答内容不当
                    ("证据材料有误", "wrong-evidence"),  # translate The evidence is incorrect --》证据材料有误
                ],
                label="其他问题:",  # translate Other issue: --》其他问题:
            )
            self.more_detail = gr.Textbox(
                placeholder=(
                    "补充说明（例如：错误详情、正确答案等）"  # translate More detail... --》补充说明...
                ),
                container=False,
                lines=3,
            )
            gr.Markdown(
                "系统将发送当前对话记录和用户设置以协助问题调查"  # translate This will send... --》系统将发送...
            )
            self.report_btn = gr.Button("提交反馈")  # translate Report --》提交反馈

    def report(
        self,
        correctness: str,
        issues: list[str],
        more_detail: str,
        conv_id: str,
        chat_history: list,
        settings: dict,
        user_id: Optional[int],
        info_panel: str,
        chat_state: dict,
        *selecteds,
    ):
        selecteds_ = {}
        for index in self._app.index_manager.indices:
            if index.selector is not None:
                if isinstance(index.selector, int):
                    selecteds_[str(index.id)] = selecteds[index.selector]
                elif isinstance(index.selector, tuple):
                    selecteds_[str(index.id)] = [selecteds[_] for _ in index.selector]
                else:
                    print(f"Unknown selector type: {index.selector}")

        with Session(engine) as session:
            issue = IssueReport(
                issues={
                    "correctness": correctness,
                    "issues": issues,
                    "more_detail": more_detail,
                },
                chat={
                    "conv_id": conv_id,
                    "chat_history": chat_history,
                    "info_panel": info_panel,
                    "chat_state": chat_state,
                    "selecteds": selecteds_,
                },
                settings=settings,
                user=user_id,
            )
            session.add(issue)
            session.commit()
        gr.Info("感谢您的反馈")  # translate Thank you for your feedback --》感谢您的反馈
