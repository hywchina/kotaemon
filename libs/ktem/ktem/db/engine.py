import os

from sqlalchemy import event
from sqlmodel import create_engine
from theflow.settings import settings


def create_database_engine(database_url: str):
    """Create the application engine with safe SQLite concurrency defaults."""

    is_sqlite = database_url.startswith("sqlite")
    connect_args = {}
    if is_sqlite:
        connect_args = {
            "check_same_thread": False,
            "timeout": int(os.getenv("KH_SQLITE_BUSY_TIMEOUT_MS", "30000")) / 1000,
        }

    database_engine = create_engine(database_url, connect_args=connect_args)
    if not is_sqlite:
        return database_engine

    busy_timeout_ms = int(os.getenv("KH_SQLITE_BUSY_TIMEOUT_MS", "30000"))
    use_wal = ":memory:" not in database_url

    @event.listens_for(database_engine, "connect")
    def configure_sqlite(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            if use_wal:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

    return database_engine


engine = create_database_engine(settings.KH_DATABASE)
