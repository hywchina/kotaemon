"""User-facing notifications with traceable server-side diagnostics."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Literal

import gradio as gr

NotificationLevel = Literal["info", "warning", "error"]


class UserFacingError(ValueError):
    """An expected error whose message is safe to display to the user."""


@dataclass(frozen=True)
class UserNotification:
    """A localized message and its optional server-side incident identifier."""

    message: str
    level: NotificationLevel = "error"
    incident_id: str | None = None

    @property
    def display_message(self) -> str:
        if self.incident_id:
            return f"{self.message}\n\n故障编号：`{self.incident_id}`"
        return self.message

    @property
    def toast_message(self) -> str:
        if self.incident_id:
            return f"{self.message}（故障编号：{self.incident_id}）"
        return self.message


def _new_incident_id() -> str:
    return uuid.uuid4().hex[:10].upper()


def _default_message(exc: Exception) -> str:
    if isinstance(exc, UserFacingError):
        return str(exc)
    if isinstance(exc, (TimeoutError,)):
        return "服务响应超时，请稍后重试；若持续出现，请联系管理员检查模型服务。"
    if isinstance(exc, (ConnectionError,)):
        return "暂时无法连接模型服务，请稍后重试。"
    if isinstance(exc, PermissionError):
        return "当前账号没有执行此操作的权限。"
    if isinstance(exc, FileNotFoundError):
        return "所需文件不存在或已被移动，请刷新页面后重试。"

    error_name = type(exc).__name__.lower()
    error_text = str(exc).lower()
    if "timeout" in error_name or "timed out" in error_text:
        return "服务响应超时，请稍后重试；若持续出现，请联系管理员检查模型服务。"
    if any(
        marker in error_text
        for marker in (
            "connection refused",
            "connection error",
            "name or service not known",
            "nodename nor servname",
        )
    ):
        return "暂时无法连接模型服务，请稍后重试。"
    if "no models in pool" in error_text:
        return "系统尚未配置可用模型，请联系管理员完成模型配置。"
    if "api key" in error_text or "unauthorized" in error_text:
        return "模型服务认证失败，请联系管理员检查服务密钥。"
    return "系统处理请求时发生异常，请稍后重试。"


def report_exception(
    operation: str,
    exc: Exception,
    *,
    logger: logging.Logger | None = None,
    fallback_message: str | None = None,
) -> UserNotification:
    """Log an exception and return a safe, traceable Chinese notification."""

    target_logger = logger or logging.getLogger(__name__)
    if isinstance(exc, UserFacingError):
        target_logger.info("User input rejected: operation=%s reason=%s", operation, exc)
        return UserNotification(message=str(exc), level="warning")

    incident_id = _new_incident_id()
    target_logger.exception(
        "Operation failed: operation=%s incident_id=%s",
        operation,
        incident_id,
        exc_info=exc,
    )
    return UserNotification(
        message=fallback_message or _default_message(exc),
        level="error",
        incident_id=incident_id,
    )


def show_notification(notification: UserNotification) -> None:
    """Show a Gradio toast without interrupting a streaming response."""

    if notification.level == "info":
        gr.Info(notification.toast_message)
    else:
        gr.Warning(notification.toast_message, duration=12)


def notify_exception(
    operation: str,
    exc: Exception,
    *,
    logger: logging.Logger | None = None,
    fallback_message: str | None = None,
) -> UserNotification:
    """Create, log and display a user-safe exception notification."""

    notification = report_exception(
        operation,
        exc,
        logger=logger,
        fallback_message=fallback_message,
    )
    show_notification(notification)
    return notification
