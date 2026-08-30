import os

from theflow.settings import settings as flowsettings

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
KH_HOSPITAL_MODE = getattr(flowsettings, "KH_HOSPITAL_MODE", False)
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)
GRADIO_SERVER_NAME = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
GRADIO_SERVER_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = os.path.join(KH_APP_DATA_DIR, "gradio_tmp")
    os.environ["GRADIO_TEMP_DIR"] = GRADIO_TEMP_DIR


from ktem.utils.logging import configure_logging  # noqa: E402

configure_logging(os.path.join(KH_APP_DATA_DIR, "logs"))


from ktem.main import App  # noqa

app = App()
demo = app.make()
demo.queue(
    api_open=not KH_HOSPITAL_MODE,
    max_size=int(os.getenv("KH_QUEUE_MAX_SIZE", "64")),
    default_concurrency_limit=int(os.getenv("KH_DEFAULT_CONCURRENCY_LIMIT", "8")),
).launch(
    favicon_path=app._favicon,
    inbrowser=not KH_HOSPITAL_MODE,
    allowed_paths=[
        "libs/ktem/ktem/assets",
        GRADIO_TEMP_DIR,
    ],
    share=KH_GRADIO_SHARE,
    server_name=GRADIO_SERVER_NAME,
    server_port=GRADIO_SERVER_PORT,
    show_api=not KH_HOSPITAL_MODE,
    show_error=False,
    max_threads=int(os.getenv("KH_MAX_THREADS", "16")),
    max_file_size=os.getenv("KH_MAX_UPLOAD_SIZE", "100mb"),
)
