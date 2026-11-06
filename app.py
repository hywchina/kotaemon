import os

from theflow.settings import settings as flowsettings

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)
# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = os.path.join(KH_APP_DATA_DIR, "gradio_tmp")
    os.environ["GRADIO_TEMP_DIR"] = GRADIO_TEMP_DIR


from ktem.main import App  # noqa
from ktem.pages.chat.speech_gateway import ENABLED, mount_speech  # noqa

app = App()
demo = app.make()
allowed_paths = [
    os.path.abspath("libs/ktem/ktem/assets"),
    os.path.abspath(GRADIO_TEMP_DIR),
]

if ENABLED:
    import gradio as gr
    import uvicorn
    from fastapi import FastAPI

    server = FastAPI()
    mount_speech(server)
    gr.mount_gradio_app(
        server,
        demo.queue(),
        path="/",
        favicon_path=app._favicon,
        allowed_paths=allowed_paths,
    )
    uvicorn.run(
        server,
        host=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        ws_max_size=65536,
    )
else:
    demo.queue().launch(
        favicon_path=app._favicon,
        inbrowser=True,
        allowed_paths=allowed_paths,
        share=KH_GRADIO_SHARE,
        server_name="0.0.0.0",
    )
