import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from ktem.db.models import Conversation, IssueReport, User
from ktem.feedback import (
    create_manual_feedback,
    feedback_detail,
    get_feedback,
    list_feedback,
    update_feedback_status,
    upsert_reaction_feedback,
)


@pytest.fixture()
def feedback_engine():
    db_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(db_engine)
    with Session(db_engine) as session:
        session.add_all(
            [
                User(
                    id="admin-id",
                    username="admin",
                    username_lower="admin",
                    password="hash",
                    admin=True,
                ),
                User(
                    id="alice-id",
                    username="alice",
                    username_lower="alice",
                    password="hash",
                    admin=False,
                ),
                User(
                    id="bob-id",
                    username="bob",
                    username_lower="bob",
                    password="hash",
                    admin=False,
                ),
                Conversation(id="conv-alice", user="alice-id", name="Alice 会话"),
                Conversation(id="conv-bob", user="bob-id", name="Bob 会话"),
            ]
        )
        session.commit()
    return db_engine


def test_feedback_is_isolated_for_users_and_visible_to_admin(feedback_engine):
    alice_report_id = create_manual_feedback(
        user_id="alice-id",
        correctness="incorrect",
        categories=["wrong-evidence"],
        detail="证据与原文不一致",
        chat={"conv_id": "conv-alice", "chat_history": [["问题", "回答"]]},
        settings={"language": "zh"},
        db_engine=feedback_engine,
    )
    create_manual_feedback(
        user_id="bob-id",
        correctness="correct",
        categories=[],
        detail="回答很好",
        chat={"conv_id": "conv-bob"},
        settings={},
        db_engine=feedback_engine,
    )

    alice_records = list_feedback("alice-id", db_engine=feedback_engine)
    assert [record.id for record in alice_records] == [alice_report_id]
    assert alice_records[0].conversation_name == "Alice 会话"

    admin_records = list_feedback(
        "admin-id", include_all=True, db_engine=feedback_engine
    )
    assert {record.username for record in admin_records} == {"alice", "bob"}

    with pytest.raises(PermissionError):
        list_feedback("alice-id", include_all=True, db_engine=feedback_engine)
    bob_report_id = next(
        record.id for record in admin_records if record.user_id == "bob-id"
    )
    assert (
        get_feedback("alice-id", bob_report_id, db_engine=feedback_engine)
        is None
    )


def test_reaction_is_upserted_per_message(feedback_engine):
    with Session(feedback_engine) as session:
        first = upsert_reaction_feedback(
            session,
            user_id="alice-id",
            conversation_id="conv-alice",
            message_index=2,
            message_value="第一版回答",
            liked=True,
        )
        session.commit()
        first_id = first.id

    with Session(feedback_engine) as session:
        second = upsert_reaction_feedback(
            session,
            user_id="alice-id",
            conversation_id="conv-alice",
            message_index=2,
            message_value="第一版回答",
            liked=False,
        )
        session.commit()
        second_id = second.id
        count = len(
            session.exec(
                select(IssueReport).where(IssueReport.user == "alice-id")
            ).all()
        )

    assert first_id == second_id
    assert count == 1
    record = list_feedback("alice-id", db_engine=feedback_engine)[0]
    assert record.source == "dislike"
    assert record.response_preview == "第一版回答"


def test_only_admin_can_update_feedback_status(feedback_engine):
    report_id = create_manual_feedback(
        user_id="alice-id",
        correctness="incorrect",
        categories=[],
        detail="需要复核",
        chat={"conv_id": "conv-alice"},
        settings={},
        db_engine=feedback_engine,
    )

    with pytest.raises(PermissionError):
        update_feedback_status(
            "alice-id",
            report_id,
            "resolved",
            "越权修改",
            db_engine=feedback_engine,
        )

    update_feedback_status(
        "admin-id",
        report_id,
        "resolved",
        "已核对并修正知识库",
        db_engine=feedback_engine,
    )
    record = get_feedback("alice-id", report_id, db_engine=feedback_engine)
    assert record is not None
    assert record.status == "resolved"
    assert record.admin_note == "已核对并修正知识库"


def test_empty_manual_feedback_is_rejected(feedback_engine):
    with pytest.raises(ValueError, match="至少选择"):
        create_manual_feedback(
            user_id="alice-id",
            correctness="",
            categories=[],
            detail="",
            chat={},
            settings={},
            db_engine=feedback_engine,
        )


def test_feedback_detail_redacts_credentials(feedback_engine):
    report_id = create_manual_feedback(
        user_id="alice-id",
        correctness="incorrect",
        categories=[],
        detail="设置异常",
        chat={"conv_id": "conv-alice"},
        settings={"api_key": "do-not-display", "nested": {"token": "hidden"}},
        db_engine=feedback_engine,
    )
    record = get_feedback("alice-id", report_id, db_engine=feedback_engine)

    detail = feedback_detail(record)

    assert detail["用户设置快照"] == {
        "api_key": "***",
        "nested": {"token": "***"},
    }
