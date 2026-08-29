from ktem.db.engine import create_database_engine


def test_sqlite_engine_enables_concurrency_and_integrity_pragmas(tmp_path):
    database_path = tmp_path / "hospital.db"
    engine = create_database_engine(f"sqlite:///{database_path}")

    try:
        with engine.connect() as connection:
            busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()

        assert busy_timeout == 30000
        assert foreign_keys == 1
        assert journal_mode == "wal"
    finally:
        engine.dispose()
