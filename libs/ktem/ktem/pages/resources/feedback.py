"""Administrator feedback review UI."""

from __future__ import annotations

import gradio as gr
import pandas as pd

from ktem.app import BasePage
from ktem.feedback import (
    SOURCE_LABELS,
    STATUS_LABELS,
    feedback_detail,
    get_feedback,
    list_feedback,
    update_feedback_status,
)


TABLE_COLUMNS = ["编号", "时间", "用户", "来源", "评价", "问题", "状态", "会话"]
CATEGORY_LABELS = {
    "offensive": "回答内容不当",
    "wrong-evidence": "证据材料有误",
}


class FeedbackManagement(BasePage):
    """Let administrators review and process all feedback records."""

    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    @staticmethod
    def _empty_table():
        return pd.DataFrame(columns=TABLE_COLUMNS)

    def on_building_ui(self):
        gr.Markdown(
            "## 反馈管理\n\n"
            "集中查看用户主动提交的反馈以及对 AI 回复的点赞、点踩。"
        )
        with gr.Row(elem_id="feedback-admin-filters"):
            self.user_filter = gr.Dropdown(
                label="用户",
                choices=[("全部用户", "all")],
                value="all",
                min_width=180,
            )
            self.source_filter = gr.Dropdown(
                label="来源",
                choices=[("全部来源", "all")]
                + [(label, value) for value, label in SOURCE_LABELS.items()],
                value="all",
                min_width=150,
            )
            self.status_filter = gr.Dropdown(
                label="状态",
                choices=[("全部状态", "all")]
                + [(label, value) for value, label in STATUS_LABELS.items()],
                value="all",
                min_width=150,
            )
            self.refresh_button = gr.Button(
                "刷新", size="sm", elem_id="feedback-admin-refresh", min_width=80
            )

        self.feedback_table = gr.DataFrame(
            value=self._empty_table(),
            headers=TABLE_COLUMNS,
            datatype=["number", "str", "str", "str", "str", "str", "str", "str"],
            interactive=False,
            height=360,
            wrap=True,
            column_widths=[7, 18, 12, 10, 12, 18, 10, 20],
            elem_id="feedback-admin-table",
        )
        self.selected_feedback_id = gr.State(value=None)

        with gr.Group(visible=False, elem_id="feedback-admin-detail") as self.detail_panel:
            self.detail = gr.JSON(label="反馈详情")
            with gr.Row():
                self.edit_status = gr.Dropdown(
                    label="处理状态",
                    choices=[(label, value) for value, label in STATUS_LABELS.items()],
                    value="pending",
                    min_width=160,
                )
                self.admin_note = gr.Textbox(
                    label="管理员备注",
                    placeholder="填写处理结果或后续说明，普通用户可在“我的反馈”中看到。",
                    lines=2,
                    max_lines=5,
                    scale=4,
                )
            with gr.Row(elem_id="feedback-admin-actions"):
                self.save_button = gr.Button(
                    "保存处理结果", variant="primary", min_width=120
                )
                self.close_button = gr.Button("关闭详情", min_width=100)

    @staticmethod
    def _assessment(record):
        if record.source in {"like", "dislike"}:
            return record.source_label
        return {
            "correct": "回答正确",
            "incorrect": "回答错误",
        }.get(record.correctness, record.correctness or "未填写")

    @staticmethod
    def _categories(record):
        return "、".join(
            CATEGORY_LABELS.get(item, item) for item in record.categories
        )

    def list_admin_feedback(
        self,
        user_id,
        user_filter="all",
        source_filter="all",
        status_filter="all",
    ):
        try:
            all_records = list_feedback(user_id, include_all=True)
            records = list_feedback(
                user_id,
                include_all=True,
                user_filter=user_filter or "all",
                source_filter=source_filter or "all",
                status_filter=status_filter or "all",
            )
        except PermissionError:
            return self._empty_table(), gr.update(
                choices=[("全部用户", "all")], value="all"
            )

        user_options = []
        seen_users = set()
        for record in all_records:
            if record.user_id not in seen_users:
                seen_users.add(record.user_id)
                user_options.append((record.username or record.user_id, record.user_id))
        user_choices = [("全部用户", "all"), *user_options]
        valid_user_ids = {value for _, value in user_choices}
        selected_user = user_filter if user_filter in valid_user_ids else "all"

        rows = [
            {
                "编号": record.id,
                "时间": record.created_at,
                "用户": record.username,
                "来源": record.source_label,
                "评价": self._assessment(record),
                "问题": self._categories(record),
                "状态": record.status_label,
                "会话": record.conversation_name or record.conversation_id,
            }
            for record in records
        ]
        table = pd.DataFrame.from_records(rows, columns=TABLE_COLUMNS)
        return table, gr.update(choices=user_choices, value=selected_user)

    def filter_admin_feedback(
        self,
        user_id,
        user_filter="all",
        source_filter="all",
        status_filter="all",
    ):
        try:
            records = list_feedback(
                user_id,
                include_all=True,
                user_filter=user_filter or "all",
                source_filter=source_filter or "all",
                status_filter=status_filter or "all",
            )
        except PermissionError:
            return self._empty_table()
        rows = [
            {
                "编号": record.id,
                "时间": record.created_at,
                "用户": record.username,
                "来源": record.source_label,
                "评价": self._assessment(record),
                "问题": self._categories(record),
                "状态": record.status_label,
                "会话": record.conversation_name or record.conversation_id,
            }
            for record in records
        ]
        return pd.DataFrame.from_records(rows, columns=TABLE_COLUMNS)

    @staticmethod
    def select_feedback(table, event: gr.SelectData):
        if not event.selected or table is None:
            return None
        try:
            return int(table.iloc[event.index[0]]["编号"])
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return None

    def load_selected_feedback(self, user_id, feedback_id):
        if feedback_id in (None, ""):
            return (
                gr.update(visible=False),
                {"提示": "请选择一条反馈记录"},
                "pending",
                "",
            )
        try:
            record = get_feedback(user_id, feedback_id, include_all=True)
        except PermissionError as exc:
            raise gr.Error(str(exc)) from exc
        if record is None:
            return (
                gr.update(visible=False),
                {"提示": "反馈记录不存在"},
                "pending",
                "",
            )
        return (
            gr.update(visible=True),
            feedback_detail(record),
            record.status,
            record.admin_note,
        )

    def save_feedback(self, user_id, feedback_id, status, admin_note):
        if feedback_id in (None, ""):
            raise gr.Error("请先选择一条反馈记录")
        try:
            update_feedback_status(user_id, feedback_id, status, admin_note)
        except (PermissionError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info("处理结果已保存")

    def on_register_events(self):
        table_outputs = [self.feedback_table, self.user_filter]
        table_inputs = [
            self._app.user_id,
            self.user_filter,
            self.source_filter,
            self.status_filter,
        ]
        self.refresh_button.click(
            self.list_admin_feedback,
            inputs=table_inputs,
            outputs=table_outputs,
            show_progress="hidden",
        )
        for trigger in (
            self.user_filter.change,
            self.source_filter.change,
            self.status_filter.change,
        ):
            trigger(
                self.filter_admin_feedback,
                inputs=table_inputs,
                outputs=[self.feedback_table],
                show_progress="hidden",
            )

        self.feedback_table.select(
            self.select_feedback,
            inputs=[self.feedback_table],
            outputs=[self.selected_feedback_id],
            show_progress="hidden",
        )
        self.selected_feedback_id.change(
            self.load_selected_feedback,
            inputs=[self._app.user_id, self.selected_feedback_id],
            outputs=[
                self.detail_panel,
                self.detail,
                self.edit_status,
                self.admin_note,
            ],
            show_progress="hidden",
        )
        self.save_button.click(
            self.save_feedback,
            inputs=[
                self._app.user_id,
                self.selected_feedback_id,
                self.edit_status,
                self.admin_note,
            ],
            outputs=[],
        ).success(
            self.list_admin_feedback,
            inputs=table_inputs,
            outputs=table_outputs,
            show_progress="hidden",
        ).success(
            self.load_selected_feedback,
            inputs=[self._app.user_id, self.selected_feedback_id],
            outputs=[
                self.detail_panel,
                self.detail,
                self.edit_status,
                self.admin_note,
            ],
            show_progress="hidden",
        )
        self.close_button.click(
            lambda: None,
            outputs=[self.selected_feedback_id],
            show_progress="hidden",
        )

    def on_subscribe_public_events(self):
        if not self._app.f_user_management:
            return
        self._app.subscribe_event(
            name="onSignIn",
            definition={
                "fn": self.list_admin_feedback,
                "inputs": [
                    self._app.user_id,
                    self.user_filter,
                    self.source_filter,
                    self.status_filter,
                ],
                "outputs": [self.feedback_table, self.user_filter],
                "show_progress": "hidden",
            },
        )
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: (
                    self._empty_table(),
                    gr.update(choices=[("全部用户", "all")], value="all"),
                ),
                "outputs": [self.feedback_table, self.user_filter],
                "show_progress": "hidden",
            },
        )

    def _on_app_created(self):
        if not self._app.f_user_management:
            self._app.app.load(
                self.list_admin_feedback,
                inputs=[
                    self._app.user_id,
                    self.user_filter,
                    self.source_filter,
                    self.status_filter,
                ],
                outputs=[self.feedback_table, self.user_filter],
            )
