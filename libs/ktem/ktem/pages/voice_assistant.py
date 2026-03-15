import gradio as gr
import html


class VoiceAssistantPage:
    def __init__(
        self,
        app,
        default_service_url: str = "http://localhost:8000/ws/v1/asr/test",
    ):
        """Embed the ASR web UI inside the current site tab."""

        if not isinstance(default_service_url, str):
            default_service_url = "http://localhost:8000/ws/v1/asr/test"

        safe_url = html.escape(default_service_url)

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
</style>

<div class="voice-assistant-embed-wrap">
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