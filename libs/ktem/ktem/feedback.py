"""Feedback persistence and permission-aware queries.

The existing ``IssueReport`` table is intentionally reused so installations do not
need a database migration.  New metadata lives in the JSON ``issues`` payload and
legacy reports remain readable.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlmodel import Session, select
from theflow.settings import settings as flowsettings
from tzlocal import get_localzone

from ktem.db.models import Conversation, IssueReport, User, engine


SOURCE_LABELS = {
    "manual": "手工反馈",
    "like": "点赞",
    "dislike": "点踩",
}
STATUS_LABELS = {
    "pending": "待处理",
    "reviewing": "处理中",
    "resolved": "已解决",
    "dismissed": "已关闭",
}
VALID_STATUSES = frozenset(STATUS_LABELS)


def _now_iso() -> str:
    return dt.datetime.now(get_localzone()).isoformat(timespec="seconds")


def _json_safe(value: Any) -> Any:
    """Return a JSON-compatible snapshot without trusting component value types."""

    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return str(value)


def _redact_secrets(value: Any) -> Any:
    """Remove credentials before a settings snapshot is rendered in the UI."""

    secret_markers = ("api_key", "apikey", "password", "secret", "token", "credential")
    if isinstance(value, dict):
        return {
            str(key): (
                "***"
                if any(marker in str(key).lower() for marker in secret_markers)
                else _redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _message_index_key(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)


def _text_preview(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = str(value.get("content") or value.get("text") or value)
    elif isinstance(value, (list, tuple)):
        text = " ".join(_text_preview(item, limit=limit) for item in value)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _is_admin(session: Session, user_id: str | None) -> bool:
    if not user_id:
        return False
    if user_id == "default" and not getattr(
        flowsettings, "KH_FEATURE_USER_MANAGEMENT", False
    ):
        return True
    user = session.exec(select(User).where(User.id == user_id)).first()
    return bool(user and user.admin)


@dataclass(frozen=True)
class FeedbackRecord:
    id: int
    user_id: str
    username: str
    created_at: str
    updated_at: str
    source: str
    source_label: str
    status: str
    status_label: str
    correctness: str
    categories: list[str]
    detail: str
    admin_note: str
    conversation_id: str
    conversation_name: str
    message_index: Any
    response: Any
    response_preview: str
    chat: dict[str, Any]
    settings: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_report(
    report: IssueReport,
    usernames: dict[str, str],
    conversation_names: dict[str, str],
) -> FeedbackRecord:
    payload = dict(report.issues or {})
    chat = dict(report.chat or {})
    source = str(payload.get("source") or "manual")
    if source == "reaction":
        source = "like" if payload.get("reaction") == "like" else "dislike"
    elif source not in SOURCE_LABELS:
        source = "manual"

    user_id = str(report.user or "")
    conv_id = str(chat.get("conv_id") or "")
    categories = payload.get("issues") or []
    if not isinstance(categories, list):
        categories = [str(categories)]

    response = chat.get("message_value")
    created_at = str(payload.get("created_at") or "历史记录")
    updated_at = str(payload.get("updated_at") or created_at)
    status = str(payload.get("status") or "pending")
    if status not in VALID_STATUSES:
        status = "pending"

    return FeedbackRecord(
        id=int(report.id or 0),
        user_id=user_id,
        username=usernames.get(user_id, "本地用户" if user_id == "default" else user_id),
        created_at=created_at.replace("T", " "),
        updated_at=updated_at.replace("T", " "),
        source=source,
        source_label=SOURCE_LABELS[source],
        status=status,
        status_label=STATUS_LABELS[status],
        correctness=str(payload.get("correctness") or ""),
        categories=[str(item) for item in categories],
        detail=str(payload.get("more_detail") or ""),
        admin_note=str(payload.get("admin_note") or ""),
        conversation_id=conv_id,
        conversation_name=conversation_names.get(conv_id, conv_id),
        message_index=chat.get("message_index"),
        response=response,
        response_preview=_text_preview(response),
        chat=chat,
        settings=dict(report.settings or {}),
    )


def create_manual_feedback(
    *,
    user_id: str | None,
    correctness: str,
    categories: list[str],
    detail: str,
    chat: dict[str, Any],
    settings: dict[str, Any] | None,
    db_engine=engine,
) -> int:
    if not user_id:
        raise PermissionError("请先登录后再提交反馈")
    if not correctness and not categories and not (detail or "").strip():
        raise ValueError("请至少选择一项反馈或填写补充说明")

    now = _now_iso()
    report = IssueReport(
        issues={
            "schema_version": 2,
            "source": "manual",
            "created_at": now,
            "updated_at": now,
            "status": "pending",
            "admin_note": "",
            "correctness": correctness or "",
            "issues": list(categories or []),
            "more_detail": (detail or "").strip(),
        },
        chat=_json_safe(chat),
        settings=_json_safe(settings or {}),
        user=str(user_id),
    )
    with Session(db_engine) as session:
        session.add(report)
        session.commit()
        session.refresh(report)
        return int(report.id or 0)


def upsert_reaction_feedback(
    session: Session,
    *,
    user_id: str | None,
    conversation_id: str,
    message_index: Any,
    message_value: Any,
    liked: bool,
) -> IssueReport:
    """Create or update one reaction per user/conversation/assistant message."""

    if not user_id:
        raise PermissionError("请先登录后再评价回答")

    index_key = _message_index_key(message_index)
    existing = None
    reports = session.exec(
        select(IssueReport).where(IssueReport.user == str(user_id))
    ).all()
    for candidate in reports:
        payload = candidate.issues or {}
        chat = candidate.chat or {}
        if (
            payload.get("source") == "reaction"
            and str(chat.get("conv_id") or "") == str(conversation_id)
            and _message_index_key(chat.get("message_index")) == index_key
        ):
            existing = candidate
            break

    now = _now_iso()
    reaction = "like" if liked else "dislike"
    if existing is None:
        existing = IssueReport(user=str(user_id))
        created_at = now
        admin_note = ""
    else:
        created_at = str((existing.issues or {}).get("created_at") or now)
        admin_note = str((existing.issues or {}).get("admin_note") or "")

    existing.issues = {
        "schema_version": 2,
        "source": "reaction",
        "reaction": reaction,
        "created_at": created_at,
        "updated_at": now,
        "status": "pending",
        "admin_note": admin_note,
        "correctness": "correct" if liked else "incorrect",
        "issues": [],
        "more_detail": "",
    }
    existing.chat = {
        "conv_id": str(conversation_id or ""),
        "message_index": _json_safe(message_index),
        "message_value": _json_safe(message_value),
    }
    session.add(existing)
    session.flush()
    return existing


def list_feedback(
    requester_id: str | None,
    *,
    include_all: bool = False,
    user_filter: str = "all",
    source_filter: str = "all",
    status_filter: str = "all",
    db_engine=engine,
) -> list[FeedbackRecord]:
    if not requester_id:
        return []

    with Session(db_engine) as session:
        if include_all and not _is_admin(session, requester_id):
            raise PermissionError("仅管理员可以查看全部反馈")

        statement = select(IssueReport)
        if not include_all:
            statement = statement.where(IssueReport.user == str(requester_id))
        elif user_filter != "all":
            statement = statement.where(IssueReport.user == user_filter)
        reports = session.exec(statement.order_by(IssueReport.id.desc())).all()

        users = session.exec(select(User)).all() if include_all else []
        usernames = {str(user.id): user.username for user in users}
        if not include_all:
            current_user = session.exec(
                select(User).where(User.id == str(requester_id))
            ).first()
            if current_user:
                usernames[str(current_user.id)] = current_user.username

        conv_ids = {
            str((report.chat or {}).get("conv_id") or "") for report in reports
        }
        conv_ids.discard("")
        conversation_names = {}
        if conv_ids:
            conversations = session.exec(
                select(Conversation).where(Conversation.id.in_(conv_ids))
            ).all()
            conversation_names = {item.id: item.name for item in conversations}

        records = [
            _normalise_report(report, usernames, conversation_names)
            for report in reports
        ]

    if source_filter != "all":
        records = [record for record in records if record.source == source_filter]
    if status_filter != "all":
        records = [record for record in records if record.status == status_filter]
    return records


def get_feedback(
    requester_id: str | None,
    feedback_id: int | str | None,
    *,
    include_all: bool = False,
    db_engine=engine,
) -> FeedbackRecord | None:
    if feedback_id in (None, ""):
        return None
    records = list_feedback(
        requester_id,
        include_all=include_all,
        db_engine=db_engine,
    )
    return next((record for record in records if record.id == int(feedback_id)), None)


def update_feedback_status(
    requester_id: str | None,
    feedback_id: int | str,
    status: str,
    admin_note: str,
    *,
    db_engine=engine,
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError("无效的处理状态")
    with Session(db_engine) as session:
        if not _is_admin(session, requester_id):
            raise PermissionError("仅管理员可以处理反馈")
        report = session.get(IssueReport, int(feedback_id))
        if report is None:
            raise ValueError("反馈记录不存在")
        payload = copy.deepcopy(report.issues or {})
        payload["status"] = status
        payload["admin_note"] = (admin_note or "").strip()[:4000]
        payload["updated_at"] = _now_iso()
        report.issues = payload
        session.add(report)
        session.commit()


def feedback_detail(record: FeedbackRecord | None) -> dict[str, Any]:
    if record is None:
        return {"提示": "请选择一条反馈记录"}
    correctness = {
        "correct": "回答正确",
        "incorrect": "回答错误",
    }.get(record.correctness, record.correctness or "未填写")
    category_labels = {
        "offensive": "回答内容不当",
        "wrong-evidence": "证据材料有误",
    }
    return {
        "反馈编号": record.id,
        "提交用户": record.username,
        "提交时间": record.created_at,
        "更新时间": record.updated_at,
        "反馈来源": record.source_label,
        "准确性评价": correctness,
        "问题分类": [category_labels.get(item, item) for item in record.categories],
        "补充说明": record.detail,
        "处理状态": record.status_label,
        "管理员备注": record.admin_note,
        "会话": record.conversation_name or record.conversation_id,
        "回复位置": record.message_index,
        "相关回复": record.response,
        "会话上下文": record.chat.get("chat_history"),
        "检索信息": record.chat.get("info_panel"),
        "用户设置快照": _redact_secrets(record.settings),
    }
