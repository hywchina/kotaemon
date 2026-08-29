"""Administrator-authorized voiceprint metadata management."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from theflow.settings import settings as flowsettings

from ktem.db.engine import engine as application_engine

from .db import VoiceprintTable


class VoiceprintPermissionError(PermissionError):
    """Raised when a non-administrator attempts to manage voiceprints."""


def _default_admin_checker(user_id: str | None) -> bool:
    if not getattr(flowsettings, "KH_FEATURE_USER_MANAGEMENT", False):
        return user_id == "default"
    if not user_id:
        return False

    # Import lazily to avoid a database-model import cycle during app startup.
    from ktem.db.models import User

    with Session(application_engine) as session:
        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        return bool(user and user.admin)


class VoiceprintManager:
    """Persist voiceprint metadata and enforce administrator-only mutations."""

    def __init__(
        self,
        db_engine: Engine = application_engine,
        admin_checker: Callable[[str | None], bool] = _default_admin_checker,
    ):
        self._engine = db_engine
        self._admin_checker = admin_checker
        VoiceprintTable.metadata.create_all(self._engine)

    @property
    def db_engine(self) -> Engine:
        return self._engine

    def assert_admin(self, user_id: str | None) -> None:
        if not self._admin_checker(user_id):
            raise VoiceprintPermissionError("只有管理员可以管理声纹库")

    def list_for_admin(self, user_id: str | None) -> list[VoiceprintTable]:
        self.assert_admin(user_id)
        return self.list_active()

    def list_active(self) -> list[VoiceprintTable]:
        """Internal read used by speaker verification during transcription."""

        with Session(self._engine) as session:
            items = session.execute(
                select(VoiceprintTable).order_by(VoiceprintTable.created_at)
            ).scalars()
            return list(items)

    def get_for_admin(self, user_id: str | None, voiceprint_id: str) -> VoiceprintTable:
        self.assert_admin(user_id)
        with Session(self._engine) as session:
            item = session.get(VoiceprintTable, voiceprint_id)
            if item is None:
                raise ValueError("声纹记录不存在")
            session.expunge(item)
            return item

    def add(
        self,
        user_id: str | None,
        display_name: str,
        provider_id: str,
        sample_count: int = 1,
        *,
        is_mock: bool = False,
    ) -> VoiceprintTable:
        self.assert_admin(user_id)
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("姓名不能为空")

        with Session(self._engine) as session:
            existing = session.execute(
                select(VoiceprintTable).where(
                    VoiceprintTable.display_name == display_name
                )
            ).scalar_one_or_none()
            if existing:
                raise ValueError(f"声纹姓名“{display_name}”已存在")

            item = VoiceprintTable(
                display_name=display_name,
                provider_id=provider_id,
                sample_count=max(1, sample_count),
                is_mock=is_mock,
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            session.expunge(item)
            return item

    def delete(self, user_id: str | None, voiceprint_id: str) -> None:
        self.assert_admin(user_id)
        with Session(self._engine) as session:
            item = session.get(VoiceprintTable, voiceprint_id)
            if item is None:
                raise ValueError("声纹记录不存在")
            session.delete(item)
            session.commit()

    def seed_mock(self, names: Iterable[str]) -> None:
        """Seed deterministic demo identities without bypassing normal UI auth."""

        with Session(self._engine) as session:
            if session.execute(select(VoiceprintTable.id).limit(1)).first():
                return
            for name in names:
                session.add(
                    VoiceprintTable(
                        display_name=name,
                        provider_id=f"mock-seed-{name}",
                        sample_count=1,
                        is_mock=True,
                    )
                )
            session.commit()
