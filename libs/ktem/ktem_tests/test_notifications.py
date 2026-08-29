from __future__ import annotations

import logging

from ktem.utils.notifications import UserFacingError, report_exception


def test_expected_error_is_safe_and_has_no_incident_id(caplog) -> None:
    with caplog.at_level(logging.INFO):
        notice = report_exception("send-message", UserFacingError("请输入问题。"))

    assert notice.message == "请输入问题。"
    assert notice.level == "warning"
    assert notice.incident_id is None


def test_unexpected_error_gets_traceable_safe_message(caplog) -> None:
    with caplog.at_level(logging.ERROR):
        notice = report_exception("chat", RuntimeError("secret upstream detail"))

    assert notice.incident_id
    assert "secret upstream detail" not in notice.display_message
    assert notice.incident_id in caplog.text
    assert "secret upstream detail" in caplog.text


def test_timeout_error_has_actionable_message() -> None:
    notice = report_exception("chat", TimeoutError("request timed out"))

    assert "超时" in notice.message
    assert "模型服务" in notice.message
