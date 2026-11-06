"""Chat composer controls and explicit transcript persistence."""

from datetime import datetime, timezone
from html import escape

import gradio as gr
from ktem.db.models import Conversation, SpeechTranscript, engine
from sqlalchemy import delete, insert, literal
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .speech_gateway import tickets

MIC = """
<div id="speech-microphone">
  <button type="button" aria-label="开始录音" title="开始录音">
    <svg class="speech-mic" width="18" height="18" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="1.8"
         stroke-linecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3"/>
      <path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3M9 22h6"/>
    </svg>
    <svg class="speech-stop" width="16" height="16" viewBox="0 0 24 24"
         fill="currentColor" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>
  </button>
</div>
"""
PREVIEW = """
<section id="speech-preview" hidden aria-label="语音转写">
  <div id="speech-status" role="status"></div>
  <pre id="speech-text"></pre>
  <button id="speech-save" type="button" hidden>保存转写</button>
</section>
"""


def _owned_conversation(db, conversation_id, user_id):
    if conversation_id:
        conversation = db.get(Conversation, conversation_id)
        if conversation and conversation.user == user_id:
            return conversation


def saved_transcripts(conversation_id, user_id):
    with Session(engine) as db:
        if not _owned_conversation(db, conversation_id, user_id):
            return gr.update(value="", visible=False)
        entries = db.exec(
            select(SpeechTranscript)
            .where(SpeechTranscript.conversation_id == conversation_id)
            .order_by(SpeechTranscript.created)
        ).all()
        value = "".join(f"<pre>{escape(entry.text)}</pre>" for entry in entries)
        return gr.update(value=value, visible=bool(entries))


def start_recording(user_id, conversation_id, request: gr.Request):
    if not user_id or not request.session_hash:
        raise gr.Error("请先登录再录音")
    if conversation_id:
        with Session(engine) as db:
            if not _owned_conversation(db, conversation_id, user_id):
                raise gr.Error("请在自己的会话中录音")
    return tickets.issue(user_id, request.session_hash, conversation_id)


def save_recording(token, user_id, conversation_id, control, request):
    record = tickets.result(token, user_id, request.session_hash)
    if not record or not record.text:
        raise gr.Error("转写已过期或尚未完成")
    with Session(engine) as db:
        saved = db.get(SpeechTranscript, record.id)
        if saved and _owned_conversation(db, saved.conversation_id, user_id):
            target_id = saved.conversation_id
        else:
            if conversation_id != record.conversation:
                raise gr.Error("会话已切换，请返回录音时的会话")
            try:
                if conversation_id:
                    # Select the owner and insert in one statement so deletion cannot
                    # leave a transcript without its conversation on legacy SQLite.
                    result = db.execute(
                        insert(SpeechTranscript).from_select(
                            ["id", "conversation_id", "text", "created"],
                            select(
                                literal(record.id),
                                Conversation.id,
                                literal(record.text),
                                literal(datetime.now(timezone.utc)),
                            ).where(
                                Conversation.id == conversation_id,
                                Conversation.user == user_id,
                            ),
                        )
                    )
                    if result.rowcount != 1:
                        raise gr.Error("该会话无法保存转写")
                    target_id = conversation_id
                else:
                    target_id = record.id
                    db.add(Conversation(id=target_id, user=user_id, name="语音转写"))
                    db.add(
                        SpeechTranscript(
                            id=record.id, conversation_id=target_id, text=record.text
                        )
                    )
                db.commit()
            except IntegrityError:
                db.rollback()
                saved = db.get(SpeechTranscript, record.id)
                if not saved or not _owned_conversation(
                    db, saved.conversation_id, user_id
                ):
                    raise
                target_id = saved.conversation_id

    choices = control.load_chat_history(user_id)
    return (
        target_id,
        gr.update(value=target_id, choices=choices),
        saved_transcripts(target_id, user_id),
    )


def delete_transcripts(db, conversation_id):
    db.execute(
        delete(SpeechTranscript).where(
            SpeechTranscript.conversation_id == conversation_id
        )
    )


class SpeechControls:
    def __init__(self):
        gr.HTML(PREVIEW, elem_id="speech-preview-wrap")
        self.saved = gr.HTML(visible=False, elem_id="speech-saved")
        self.token = gr.Textbox(visible=False)
        self.start = gr.Button(
            "开始语音识别", elem_id="speech-start-bridge", elem_classes="speech-bridge"
        )
        self.save = gr.Button(
            "保存语音识别", elem_id="speech-save-bridge", elem_classes="speech-bridge"
        )

    def bind(self, user, control):
        conversation = control.conversation_id
        self.start.click(
            start_recording,
            inputs=[user, conversation],
            outputs=self.token,
            api_name=False,
            queue=False,
        ).success(
            fn=None,
            inputs=self.token,
            js="token => window.kotaSpeech.open(token)",
            queue=False,
        )

        def save(token, user_id, conversation_id, request: gr.Request):
            return save_recording(token, user_id, conversation_id, control, request)

        self.save.click(
            save,
            inputs=[self.token, user, conversation],
            outputs=[conversation, control.conversation, self.saved],
            api_name=False,
            queue=False,
        ).success(fn=None, js="() => window.kotaSpeech.saved()", queue=False)
        conversation.change(
            saved_transcripts,
            inputs=[conversation, user],
            outputs=self.saved,
            api_name=False,
            queue=False,
        )
        user.change(
            fn=None,
            js="() => window.kotaSpeech.reset()",
            queue=False,
        )
