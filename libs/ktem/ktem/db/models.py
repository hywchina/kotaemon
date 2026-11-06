from datetime import datetime, timezone

import ktem.db.base_models as base_models
from ktem.db.engine import engine
from sqlalchemy import Column, ForeignKey, String, Text
from sqlmodel import Field, SQLModel
from theflow.settings import settings
from theflow.utils.modules import import_dotted_string

_base_conv = (
    import_dotted_string(settings.KH_TABLE_CONV, safe=False)
    if hasattr(settings, "KH_TABLE_CONV")
    else base_models.BaseConversation
)

_base_user = (
    import_dotted_string(settings.KH_TABLE_USER, safe=False)
    if hasattr(settings, "KH_TABLE_USER")
    else base_models.BaseUser
)

_base_settings = (
    import_dotted_string(settings.KH_TABLE_SETTINGS, safe=False)
    if hasattr(settings, "KH_TABLE_SETTINGS")
    else base_models.BaseSettings
)

_base_issue_report = (
    import_dotted_string(settings.KH_TABLE_ISSUE_REPORT, safe=False)
    if hasattr(settings, "KH_TABLE_ISSUE_REPORT")
    else base_models.BaseIssueReport
)


class Conversation(_base_conv, table=True):  # type: ignore
    """Conversation record"""


class User(_base_user, table=True):  # type: ignore
    """User table"""


class Settings(_base_settings, table=True):  # type: ignore
    """Record of settings"""


class IssueReport(_base_issue_report, table=True):  # type: ignore
    """Record of issues"""


class SpeechTranscript(SQLModel, table=True):
    """An explicitly saved transcript, separate from model prompt history."""

    id: str = Field(primary_key=True)
    conversation_id: str = Field(
        sa_column=Column(
            String,
            ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    text: str = Field(sa_column=Column(Text, nullable=False))
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


if not getattr(settings, "KH_ENABLE_ALEMBIC", False):
    SQLModel.metadata.create_all(engine)
