"""Application logging configuration for local and intranet deployments."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_HANDLER_NAME = "ktem-runtime-file"


def configure_logging(log_dir: str | Path) -> Path:
    """Configure a rotating runtime log once and return its file path."""

    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "app.log"

    root_logger = logging.getLogger()
    if any(
        getattr(handler, "name", None) == _HANDLER_NAME
        for handler in root_logger.handlers
    ):
        return log_path

    level_name = os.getenv("KH_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    max_bytes = int(os.getenv("KH_LOG_MAX_BYTES", str(20 * 1024 * 1024)))
    backup_count = int(os.getenv("KH_LOG_BACKUP_COUNT", "10"))

    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.name = _HANDLER_NAME
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "[process=%(process)d thread=%(threadName)s] %(message)s"
        )
    )
    handler.setLevel(level)
    root_logger.addHandler(handler)
    root_logger.setLevel(min(root_logger.level or level, level))
    return log_path
