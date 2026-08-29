"""Safe HTML renderer for the live multi-speaker transcript panel."""

from __future__ import annotations

import html

from .schema import TranscriptSegment


def upsert_segment(segments: list[dict], segment: TranscriptSegment) -> list[dict]:
    """Insert a new segment or replace its latest partial result."""

    output = list(segments or [])
    state = segment.to_state()
    for index, existing in enumerate(output):
        if existing.get("segment_id") == segment.segment_id:
            output[index] = state
            return output
    output.append(state)
    return output


def _format_timestamp(milliseconds: int) -> str:
    seconds = max(0, milliseconds) // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def render_live_transcript(
    segments: list[dict] | None,
    *,
    status: str,
    is_recording: bool,
    is_mock: bool,
) -> str:
    """Render transcript state while escaping provider-controlled content."""

    segment_items = [TranscriptSegment.from_state(item) for item in segments or []]
    recording_class = " is-recording" if is_recording else ""
    mode_badge = '<span class="asr-mode-badge">模拟数据</span>' if is_mock else ""
    safe_status = html.escape(status)

    if segment_items:
        turns = []
        for item in segment_items:
            speaker_index = item.speaker_id.rsplit("_", 1)[-1]
            try:
                color_index = int(speaker_index) % 4
            except ValueError:
                color_index = 0
            partial_class = " asr-partial" if not item.is_final else ""
            verified = ""
            if item.speaker_name and item.verification_score is not None:
                verified = (
                    '<span class="asr-verified" title="声纹匹配置信度 '
                    f'{item.verification_score:.0%}">已识别</span>'
                )
            turns.append(
                f'<article class="asr-turn speaker-{color_index}{partial_class}">'
                '<div class="asr-turn-meta">'
                f"<strong>{html.escape(item.display_speaker)}</strong>{verified}"
                f"<span>{_format_timestamp(item.start_ms)}</span>"
                "</div>"
                f"<p>{html.escape(item.text)}</p>"
                "</article>"
            )
        body = "".join(turns)
    else:
        body = '<div class="asr-empty">正在等待语音，识别结果会按说话人实时显示……</div>'

    return (
        f'<section class="asr-chat-transcript{recording_class}" '
        'data-ktem-message-type="asr" aria-live="polite">'
        '<header class="asr-live-header">'
        '<div><span class="asr-recording-dot"></span>'
        f"<strong>语音实时转写</strong>{mode_badge}</div>"
        f'<span class="asr-live-status">{safe_status}</span>'
        "</header>"
        f'<div class="asr-turns">{body}</div>'
        "</section>"
    )
