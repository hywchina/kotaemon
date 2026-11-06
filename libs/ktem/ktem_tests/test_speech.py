from types import SimpleNamespace

import gradio as gr
import pytest
from ktem.db.models import Conversation, SpeechTranscript
from ktem.pages.chat import speech_ui
from ktem.pages.chat.speech_gateway import RecordingTickets
from sqlalchemy import func
from sqlmodel import Session, create_engine, select


@pytest.fixture
def speech_storage(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'speech.db'}")
    Conversation.__table__.create(engine)
    SpeechTranscript.__table__.create(engine)
    recordings = RecordingTickets()
    monkeypatch.setattr(speech_ui, "engine", engine)
    monkeypatch.setattr(speech_ui, "tickets", recordings)
    return engine, recordings


def test_preview_is_ephemeral_until_owner_saves(speech_storage):
    engine, recordings = speech_storage
    request = SimpleNamespace(session_hash="test-browser")
    control = SimpleNamespace(load_chat_history=lambda user: [])
    token = speech_ui.start_recording("owner", None, request)

    assert recordings.claim(token)
    assert recordings.claim(token) is None
    recordings.finish(token, "说话人 1：<hello>")
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(SpeechTranscript)).one() == 0
        assert db.exec(select(func.count()).select_from(Conversation)).one() == 0

    with pytest.raises(gr.Error):
        speech_ui.save_recording(token, "other-user", None, control, request)
    with pytest.raises(gr.Error):
        speech_ui.save_recording(
            token, "owner", None, control, SimpleNamespace(session_hash="other-browser")
        )

    conversation_id, _, rendered = speech_ui.save_recording(
        token, "owner", None, control, request
    )
    assert rendered["value"] == "<pre>说话人 1：&lt;hello&gt;</pre>"
    assert (
        speech_ui.saved_transcripts(conversation_id, "other-user")["visible"] is False
    )
    assert (
        speech_ui.save_recording(token, "owner", None, control, request)[0]
        == conversation_id
    )
    with Session(engine) as db:
        assert db.get(Conversation, conversation_id).data_source == {}
        assert db.exec(select(func.count()).select_from(SpeechTranscript)).one() == 1
        speech_ui.delete_transcripts(db, conversation_id)
        db.commit()
    assert speech_ui.saved_transcripts(conversation_id, "owner")["visible"] is False


def test_switching_conversations_cannot_redirect_a_recording(speech_storage):
    engine, recordings = speech_storage
    request = SimpleNamespace(session_hash="test-browser")
    control = SimpleNamespace(load_chat_history=lambda user: [])
    with Session(engine) as db:
        db.add(Conversation(id="first", user="owner"))
        db.add(Conversation(id="second", user="owner"))
        db.commit()

    token = speech_ui.start_recording("owner", "first", request)
    assert recordings.claim(token)
    recordings.finish(token, "说话人 1：第一句")
    with pytest.raises(gr.Error, match="会话已切换"):
        speech_ui.save_recording(token, "owner", "second", control, request)
    assert (
        speech_ui.save_recording(token, "owner", "first", control, request)[0]
        == "first"
    )
