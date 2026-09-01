import uuid

import gradio as gr
from theflow.settings import settings as flowsettings

from ktem.app import BasePage
from ktem.asr.render import render_live_transcript, upsert_segment
from ktem.asr.schema import ASRStreamRequest, TranscriptEventType
from ktem.asr.service import get_asr_service

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_ENABLE_ASR = getattr(flowsettings, "KH_ENABLE_ASR", True)

if not KH_DEMO_MODE:
    PLACEHOLDER_TEXT = (
        "开始一次辅助诊断问答\n\n"
        "可输入医学问题、添加检查图片，或引用知识库资料。"
        "模型回答仅供临床参考。"
    )
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
        self.uses_live_audio = bool(
            self._asr_service is not None and not self._asr_service.is_mock
        )
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
            self.asr_runtime_session_id = gr.State(value="")
        self.pending_multimodal_input = gr.State(value={"query": "", "image_paths": []})

        with gr.Row(elem_id="chat-composer-row"):
            self.text_input = gr.MultimodalTextbox(
                interactive=True,
                scale=20,
                file_count="multiple",
                file_types=["image"],
                placeholder="请输入问题",
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
                if self.uses_live_audio:
                    self.asr_cancel_bridge = gr.Button(
                        "取消录音",
                        elem_id="asr-cancel-bridge",
                        elem_classes=["chat-action-bridge"],
                    )
                    self.asr_confirm_bridge = gr.Button(
                        "完成录音",
                        elem_id="asr-confirm-bridge",
                        elem_classes=["chat-action-bridge"],
                    )
                    self.asr_live_audio = gr.Audio(
                        sources=["microphone"],
                        type="numpy",
                        streaming=True,
                        container=False,
                        show_label=False,
                        show_download_button=False,
                        show_share_button=False,
                        editable=False,
                        min_width=160,
                        scale=2,
                        elem_id="asr-live-audio",
                        elem_classes=["asr-live-audio"],
                    )
                else:
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

    def start_live_transcription(self) -> str:
        """Create the server-side WebSocket session for native microphone audio."""

        if self._asr_service is None or not self.uses_live_audio:
            raise gr.Error("当前未启用本地实时 ASR")
        session_id = uuid.uuid4().hex
        try:
            self._asr_service.start_live_stream(ASRStreamRequest(session_id=session_id))
        except Exception as exc:  # noqa: BLE001 - provider error is user-facing
            raise gr.Error(f"无法启动本地 ASR：{exc}") from exc
        return session_id

    @staticmethod
    def _merge_live_events(segments, events):
        merged = list(segments or [])
        for event in events:
            if (
                event.event_type == TranscriptEventType.SEGMENT
                and event.segment is not None
            ):
                merged = upsert_segment(merged, event.segment)
        return merged

    def stream_live_audio(
        self,
        audio_chunk,
        session_id,
        previous_segments,
        chat_history,
        message_index,
    ):
        """Forward one Gradio microphone chunk and render available ASR events."""

        segments = list(previous_segments or [])
        if not audio_chunk or not session_id:
            return session_id, segments, chat_history, message_index
        try:
            events = self._asr_service.feed_live_stream(session_id, audio_chunk)
            segments = self._merge_live_events(segments, events)
            history, message_index = self._update_transcript_message(
                chat_history,
                message_index,
                segments,
                status="正在录音",
                is_recording=True,
                is_mock=False,
            )
            return session_id, segments, history, message_index
        except Exception as exc:  # noqa: BLE001 - provider error is user-facing
            self._asr_service.abort_live_stream(session_id)
            history, message_index = self._update_transcript_message(
                chat_history,
                message_index,
                segments,
                status=f"转写失败：{exc}",
                is_recording=False,
                is_mock=False,
            )
            return "", segments, history, message_index

    def finish_live_transcription(
        self,
        stop_mode,
        session_id,
        previous_segments,
        chat_history,
        message_index,
        retrieval_history,
        plot_history,
    ):
        """Confirm or cancel the recording and close its provider WebSocket."""

        segments = list(previous_segments or [])
        history = list(chat_history or [])
        retrieval = list(retrieval_history or [])
        plots = list(plot_history or [])
        if stop_mode == "cancel":
            if session_id:
                self._asr_service.abort_live_stream(session_id)
            if 0 <= message_index < len(history):
                history.pop(message_index)
                if message_index < len(retrieval):
                    retrieval.pop(message_index)
                if message_index < len(plots):
                    plots.pop(message_index)
            return "", [], history, -1, retrieval, plots

        status = "转写已完成"
        try:
            if session_id:
                events = self._asr_service.finish_live_stream(session_id)
                segments = self._merge_live_events(segments, events)
        except Exception as exc:  # noqa: BLE001 - provider error is user-facing
            status = f"转写失败：{exc}"
            if session_id:
                self._asr_service.abort_live_stream(session_id)
        history, message_index = self._update_transcript_message(
            history,
            message_index,
            segments,
            status=status,
            is_recording=False,
            is_mock=False,
        )
        return (
            "",
            segments,
            history,
            message_index,
            retrieval,
            plots,
        )

    def cancel_live_transcription(
        self,
        session_id,
        previous_segments,
        chat_history,
        message_index,
        retrieval_history,
        plot_history,
    ):
        """Cancel browser recording and discard its temporary transcript turn."""

        return self.finish_live_transcription(
            "cancel",
            session_id,
            previous_segments,
            chat_history,
            message_index,
            retrieval_history,
            plot_history,
        )

    def confirm_live_transcription(
        self,
        session_id,
        previous_segments,
        chat_history,
        message_index,
        retrieval_history,
        plot_history,
    ):
        """Finish browser recording and keep its finalized transcript turn."""

        return self.finish_live_transcription(
            "confirm",
            session_id,
            previous_segments,
            chat_history,
            message_index,
            retrieval_history,
            plot_history,
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
