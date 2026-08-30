import uuid

import gradio as gr
from theflow.settings import settings as flowsettings

from ktem.app import BasePage
from ktem.asr.render import render_live_transcript, upsert_segment
from ktem.asr.schema import ASRStreamRequest, TranscriptEventType
from ktem.asr.service import get_asr_service
from ktem.utils.commands import WEB_SEARCH_COMMAND

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_ENABLE_ASR = getattr(flowsettings, "KH_ENABLE_ASR", True)

if not KH_DEMO_MODE:
    PLACEHOLDER_TEXT = "这是一次新会话的开始。"
else:
    PLACEHOLDER_TEXT = (
        "Welcome to Kotaemon Demo. "
        "Start by browsing preloaded conversations to get onboard.\n"
        "Check out Hint section for more tips."
    )


class ChatPanel(BasePage):
    def __init__(self, app):
        self._app = app
        self._asr_service = get_asr_service() if KH_ENABLE_ASR else None
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
        if KH_ENABLE_ASR:
            self.asr_segments = gr.State(value=[])
            self.asr_message_index = gr.State(value=-1)
        self.pending_multimodal_input = gr.State(value={"query": "", "image_paths": []})

        with gr.Row(elem_id="chat-composer-row"):
            search_hint = (
                f"，使用 @{WEB_SEARCH_COMMAND} 搜索网页" if WEB_SEARCH_COMMAND else ""
            )
            self.text_input = gr.MultimodalTextbox(
                interactive=True,
                scale=20,
                file_count="multiple",
                file_types=["image"],
                placeholder=(
                    f"输入消息{search_hint}，或点击左下角添加图片、使用 @文件名 引用资料"
                ),
                container=False,
                show_label=False,
                elem_id="chat-input",
            )
            self.submit_btn = gr.Button(
                "↑",
                variant="primary",
                min_width=44,
                elem_id="chat-submit-button",
                elem_classes=["chat-composer-action", "chat-submit-action"],
            )
            if KH_ENABLE_ASR:
                self.asr_start_button = gr.Button(
                    "🎙",
                    elem_id="asr-start-button",
                    elem_classes=["chat-composer-action", "asr-microphone-button"],
                    min_width=44,
                    variant="secondary",
                )
                self.asr_stop_button = gr.Button(
                    "■",
                    elem_id="asr-stop-button",
                    elem_classes=[
                        "chat-composer-action",
                        "asr-microphone-button",
                        "asr-stop-button",
                    ],
                    min_width=44,
                    variant="stop",
                    visible=False,
                )

        # Browser-injected message action icons use these hidden Gradio controls to
        # invoke permission-checked Python callbacks.
        self.message_action_payload = gr.Textbox(
            value="",
            container=False,
            elem_id="chat-message-action-payload",
            elem_classes=["chat-action-bridge"],
        )
        self.edit_message_button = gr.Button(
            "提交消息修改",
            elem_id="chat-edit-message-bridge",
            elem_classes=["chat-action-bridge"],
        )
        self.delete_message_button = gr.Button(
            "删除消息",
            elem_id="chat-delete-message-bridge",
            elem_classes=["chat-action-bridge"],
        )

    def submit_msg(self, chat_input, chat_history):
        """Submit a message to the chatbot"""
        return "", chat_history + [(chat_input, None)]

    @staticmethod
    def _update_transcript_message(
        chat_history,
        message_index,
        segments,
        *,
        status,
        is_recording,
        is_mock,
    ):
        """Render one ASR session as an assistant-side chat message."""

        history = list(chat_history or [])
        message = render_live_transcript(
            segments,
            status=status,
            is_recording=is_recording,
            is_mock=is_mock,
        )
        if message_index < 0 or message_index >= len(history):
            message_index = len(history)
            history.append((None, message))
        else:
            history[message_index] = (None, message)
        return history, message_index

    def begin_transcription(self, chat_history):
        """Append the initial assistant-side transcript message."""

        segments = []
        is_mock = bool(self._asr_service and self._asr_service.is_mock)
        history, message_index = self._update_transcript_message(
            chat_history,
            -1,
            segments,
            status="正在录音",
            is_recording=True,
            is_mock=is_mock,
        )
        return (
            segments,
            history,
            message_index,
            gr.update(visible=False),
            gr.update(visible=True),
        )

    def stream_transcription(self, previous_segments, chat_history, message_index):
        """Stream provider events into an assistant-side chat message."""

        segments = list(previous_segments or [])
        is_mock = bool(self._asr_service and self._asr_service.is_mock)

        if self._asr_service is None:
            return

        request = ASRStreamRequest(session_id=uuid.uuid4().hex)
        try:
            for event in self._asr_service.stream(request):
                if (
                    event.event_type == TranscriptEventType.SEGMENT
                    and event.segment is not None
                ):
                    segments = upsert_segment(segments, event.segment)
                    history, message_index = self._update_transcript_message(
                        chat_history,
                        message_index,
                        segments,
                        status="正在录音",
                        is_recording=True,
                        is_mock=is_mock,
                    )
                    chat_history = history
                    yield (
                        segments,
                        history,
                        message_index,
                        gr.update(visible=False),
                        gr.update(visible=True),
                    )

            history, message_index = self._update_transcript_message(
                chat_history,
                message_index,
                segments,
                status="转写已完成",
                is_recording=False,
                is_mock=is_mock,
            )
            yield (
                segments,
                history,
                message_index,
                gr.update(visible=True),
                gr.update(visible=False),
            )
        except Exception as exc:  # noqa: BLE001 - provider errors become UI status
            history, message_index = self._update_transcript_message(
                chat_history,
                message_index,
                segments,
                status=f"转写失败：{exc}",
                is_recording=False,
                is_mock=is_mock,
            )
            yield (
                segments,
                history,
                message_index,
                gr.update(visible=True),
                gr.update(visible=False),
            )

    def stop_transcription(self, segments, chat_history, message_index):
        """Keep completed segments in chat when the user cancels recording."""

        is_mock = bool(self._asr_service and self._asr_service.is_mock)
        history, message_index = self._update_transcript_message(
            chat_history,
            message_index,
            segments or [],
            status="录音已取消",
            is_recording=False,
            is_mock=is_mock,
        )
        return (
            history,
            message_index,
            gr.update(visible=True),
            gr.update(visible=False),
        )

    def on_register_events(self):
        # ChatPage owns the event chains because ASR messages share conversation
        # persistence and history state with text messages.
        return
