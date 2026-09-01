"""SQLite-backed voiceprint registry; raw embeddings never leave this service."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .clustering import normalize_embedding


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class VoiceprintRecord:
    id: str
    display_name: str
    sample_count: int
    created_at: datetime
    updated_at: datetime
    embedding: np.ndarray


class VoiceprintStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS voiceprint (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL UNIQUE,
                    sample_count INTEGER NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> VoiceprintRecord:
        dimension = int(row["embedding_dim"])
        embedding = np.frombuffer(row["embedding"], dtype=np.float32).copy()
        if len(embedding) != dimension:
            raise RuntimeError("Stored voiceprint embedding dimension is corrupt")
        return VoiceprintRecord(
            id=row["id"],
            display_name=row["display_name"],
            sample_count=int(row["sample_count"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            embedding=embedding,
        )

    def create(self, display_name: str, embedding: np.ndarray) -> VoiceprintRecord:
        normalized_name = display_name.strip()
        if not normalized_name:
            raise ValueError("display_name must not be empty")
        normalized = normalize_embedding(embedding)
        identifier = uuid.uuid4().hex
        now = _utcnow().isoformat()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO voiceprint
                    (id, display_name, sample_count, embedding_dim, embedding,
                     created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        normalized_name,
                        len(normalized),
                        normalized.astype(np.float32).tobytes(),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Voiceprint name already exists: {normalized_name}"
            ) from exc
        return self.get(identifier)

    def add_sample(self, identifier: str, embedding: np.ndarray) -> VoiceprintRecord:
        current = self.get(identifier)
        incoming = normalize_embedding(embedding)
        if len(incoming) != len(current.embedding):
            raise ValueError("Voiceprint embedding dimension changed")
        combined = normalize_embedding(
            current.embedding * current.sample_count + incoming
        )
        now = _utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE voiceprint
                SET sample_count = ?, embedding = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    current.sample_count + 1,
                    combined.astype(np.float32).tobytes(),
                    now,
                    identifier,
                ),
            )
        return self.get(identifier)

    def get(self, identifier: str) -> VoiceprintRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM voiceprint WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return self._record(row)

    def list(self) -> list[VoiceprintRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM voiceprint ORDER BY created_at, id"
            ).fetchall()
        return [self._record(row) for row in rows]

    def delete(self, identifier: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM voiceprint WHERE id = ?", (identifier,)
            )
        if cursor.rowcount != 1:
            raise KeyError(identifier)

    def identify(
        self, embedding: np.ndarray, *, threshold: float
    ) -> tuple[VoiceprintRecord, float] | None:
        query = normalize_embedding(embedding)
        best: tuple[VoiceprintRecord, float] | None = None
        for item in self.list():
            if len(item.embedding) != len(query):
                continue
            score = max(-1.0, min(1.0, float(np.dot(query, item.embedding))))
            if best is None or score > best[1]:
                best = (item, score)
        return best if best is not None and best[1] >= threshold else None
