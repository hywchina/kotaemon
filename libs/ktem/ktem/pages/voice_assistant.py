import html
import socket
from urllib.parse import urlsplit, urlunsplit

import gradio as gr
from theflow.settings import settings as flowsettings


def _get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _replace_localhost_with_local_ip(url: str) -> str:
    parsed = urlsplit(url)
    hostname = parsed.hostname

    if hostname not in {"localhost", "127.0.0.1"}:
        return url

    local_ip = _get_local_ip()
    port = f":{parsed.port}" if parsed.port else ""
    auth = ""
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        auth = f"{auth}@"

    netloc = f"{auth}{local_ip}{port}"
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


class VoiceAssistantPage:
    def __init__(
        self,
        app,
        default_service_url: str | None = None,
    ):
        """Embed the ASR web UI inside the current site tab."""

        del app
        if not default_service_url:
            default_service_url = getattr(
                flowsettings,
                "KH_VOICE_ASSISTANT_URL",
                "https://localhost:17003/ws/v1/asr/test",
            )
        parsed = urlsplit(default_service_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("KH_VOICE_ASSISTANT_URL must be a valid HTTP(S) URL")

        default_service_url = _replace_localhost_with_local_ip(default_service_url)
        fallback_service_url = _replace_localhost_with_local_ip(default_service_url)

        safe_url = html.escape(default_service_url, quote=True)
        safe_fallback_url = html.escape(fallback_service_url, quote=True)

        with gr.Column(elem_classes=["fill-main-area-height", "scrollable"]):
            gr.HTML(
                f"""
<style>
  .voice-assistant-embed-wrap {{
    margin: -8px -12px 0 -12px;
    height: calc(100vh - 96px);
    min-height: 680px;
    background: transparent;
  }}

  .voice-assistant-note {{
    margin: 0 0 8px 0;
    padding: 8px 12px;
    border-radius: 8px;
    background: #fff8e1;
    color: #5d4037;
    font-size: 13px;
    line-height: 1.5;
  }}

  .voice-assistant-note a {{
    color: #0d47a1;
    text-decoration: underline;
    word-break: break-all;
  }}
</style>

<div class="voice-assistant-embed-wrap">
  <div class="voice-assistant-note">
    如果访问当前语音助手不可用，请跳转至：
    <a href="{safe_fallback_url}" target="_blank" rel="noopener noreferrer">{safe_fallback_url}</a>
  </div>
  <iframe
    title="ASR Voice Assistant"
    src="{safe_url}"
    allow="microphone *; camera *; clipboard-read *; clipboard-write *"
    style="display:block; width:100%; height:100%; border:0; border-radius:0; background:transparent;"
    referrerpolicy="no-referrer"
  ></iframe>
</div>
"""
            )
