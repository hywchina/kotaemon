import html
from typing import Optional

import gradio as gr
from ktem.app import BasePage
from ktem.feedback import (
    FeedbackRecord,
    create_manual_feedback,
    get_feedback,
    list_feedback,
)


class ReportIssue(BasePage):
    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Accordion(
            label="反馈", open=False, elem_id="report-accordion"
        ):  # translate Feedback --》反馈
            with gr.Accordion(
                label="提交反馈", open=True, elem_id="feedback-submit-panel"
            ):
                self.correctness = gr.Radio(  # translate
                    choices=[  # translate
                        (
                            "回答正确",
                            "correct",
                        ),  # translate The answer is correct --》回答正确
                        (
                            "回答错误",
                            "incorrect",
                        ),  # translate The answer is incorrect --》回答错误
                    ],
                    label="准确性评估:",  # translate Correctness: --》准确性评估:
                )
                self.issues = gr.CheckboxGroup(
                    choices=[
                        (
                            "回答内容不当",
                            "offensive",
                        ),  # translate The answer is offensive --》回答内容不当
                        (
                            "证据材料有误",
                            "wrong-evidence",
                        ),  # translate The evidence is incorrect --》证据材料有误
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
                    "提交时会附带当前会话上下文，以便定位问题。"
                )
                self.report_btn = gr.Button(
                    "提交反馈", variant="primary", elem_id="feedback-submit-button"
                )

            with gr.Accordion(
                label="我的反馈", open=False, elem_id="my-feedback-panel"
            ):
                self.my_feedback_choice = gr.Dropdown(
                    label="反馈记录",
                    choices=[],
                    interactive=True,
                    elem_id="my-feedback-choice",
                )
                self.my_feedback_detail = gr.Markdown(
                    "暂无反馈记录。", elem_id="my-feedback-detail"
                )
                self.refresh_my_feedback_btn = gr.Button(
                    "刷新记录", size="sm", elem_id="my-feedback-refresh"
                )

    @staticmethod
    def _my_feedback_markdown(record: FeedbackRecord | None) -> str:
        if record is None:
            return "暂无反馈记录。"

        correctness = {
            "correct": "回答正确",
            "incorrect": "回答错误",
        }.get(record.correctness, record.correctness or "未填写")
        category_labels = {
            "offensive": "回答内容不当",
            "wrong-evidence": "证据材料有误",
        }
        categories = "、".join(
            category_labels.get(item, item) for item in record.categories
        ) or "无"

        def safe(value):
            return html.escape(str(value or "无"))

        rows = [
            f"**来源：** {safe(record.source_label)}",
            f"**时间：** {safe(record.created_at)}",
            f"**状态：** {safe(record.status_label)}",
            f"**准确性：** {safe(correctness)}",
            f"**问题：** {safe(categories)}",
        ]
        if record.detail:
            rows.append(f"**说明：** {safe(record.detail)}")
        if record.response_preview:
            rows.append(f"**相关回复：** {safe(record.response_preview)}")
        if record.admin_note:
            rows.append(f"**处理备注：** {safe(record.admin_note)}")
        return "\n\n".join(rows)

    def list_my_feedback(self, user_id):
        records = list_feedback(user_id)
        choices = [
            (
                f"#{record.id} · {record.created_at} · "
                f"{record.source_label} · {record.status_label}",
                record.id,
            )
            for record in records
        ]
        selected = records[0] if records else None
        return (
            gr.update(
                choices=choices,
                value=selected.id if selected is not None else None,
            ),
            self._my_feedback_markdown(selected),
        )

    def show_my_feedback(self, user_id, feedback_id):
        record = get_feedback(user_id, feedback_id)
        return self._my_feedback_markdown(record)

    def report(
        self,
        correctness: str,
        issues: list[str],
        more_detail: str,
        conv_id: str,
        chat_history: list,
        settings: dict,
        user_id: Optional[str],
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

        try:
            create_manual_feedback(
                user_id=user_id,
                correctness=correctness or "",
                categories=issues or [],
                detail=more_detail or "",
                chat={
                    "conv_id": conv_id,
                    "chat_history": chat_history,
                    "info_panel": info_panel,
                    "chat_state": chat_state,
                    "selecteds": selecteds_,
                },
                settings=settings,
            )
        except (PermissionError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info("感谢您的反馈，已加入“我的反馈”。")
        feedback_choice, feedback_detail = self.list_my_feedback(user_id)
        return None, [], "", feedback_choice, feedback_detail

    def on_register_events(self):
        self.refresh_my_feedback_btn.click(
            self.list_my_feedback,
            inputs=[self._app.user_id],
            outputs=[self.my_feedback_choice, self.my_feedback_detail],
            show_progress="hidden",
        )
        self.my_feedback_choice.change(
            self.show_my_feedback,
            inputs=[self._app.user_id, self.my_feedback_choice],
            outputs=[self.my_feedback_detail],
            show_progress="hidden",
        )

    def on_subscribe_public_events(self):
        if not self._app.f_user_management:
            return
        self._app.subscribe_event(
            name="onSignIn",
            definition={
                "fn": self.list_my_feedback,
                "inputs": [self._app.user_id],
                "outputs": [self.my_feedback_choice, self.my_feedback_detail],
                "show_progress": "hidden",
            },
        )
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: (
                    gr.update(choices=[], value=None),
                    "暂无反馈记录。",
                ),
                "outputs": [self.my_feedback_choice, self.my_feedback_detail],
                "show_progress": "hidden",
            },
        )

    def _on_app_created(self):
        if not self._app.f_user_management:
            self._app.app.load(
                self.list_my_feedback,
                inputs=[self._app.user_id],
                outputs=[self.my_feedback_choice, self.my_feedback_detail],
            )
