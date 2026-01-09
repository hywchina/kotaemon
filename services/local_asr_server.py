import os
import json
import tempfile
import shutil
import time
import logging
import torch
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

# ======================
# 路径 & 配置加载
# ======================

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONF_PATH = os.path.join(PROJECT_ROOT, "conf", "asr_models.json")
# Allow FunASR/HF tokenizers that rely on remote code to load correctly
os.environ.setdefault("FUNASR_TRUST_REMOTE_CODE", "true")

# ======================
# Logging
# ======================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("local_asr_server")


def load_default_asr_model_path(conf_path: str) -> str:
    with open(conf_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    defaults = [m for m in data.get("models", []) if m.get("default")]
    if len(defaults) != 1:
        raise ValueError("Exactly one default ASR model must be set")

    model_path = os.path.expanduser(defaults[0]["model_name"])
    if not os.path.isdir(model_path):
        raise FileNotFoundError(f"ASR model path not found: {model_path}")

    return model_path


MODEL_DIR = load_default_asr_model_path(CONF_PATH)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"ASR service starting. Device={DEVICE}, CONF_PATH={CONF_PATH}")

# ======================
# FastAPI App
# ======================

app = FastAPI(title="Local ASR Service (FunASR)")

asr_model = None


# ======================
# 启动时加载模型
# ======================

@app.on_event("startup")
def load_model():
    global asr_model
    try:
        logger.info("Loading ASR model...")
        # 方法1: 尝试使用本地 FunASR 模型；任何错误都转用备用方案
        from funasr import AutoModel
        try:
            asr_model = AutoModel(
                model=MODEL_DIR,
                device=DEVICE,
                disable_update=True,
                disable_log=False,
            )
            logger.info(f"Loaded FunASR AutoModel from local dir: {MODEL_DIR}")
            return
        except Exception as e:
            logger.warning(f"AutoModel local load failed: {e}. Trying ModelScope ID...")

        # 方法2: 使用 modelscope ID 而非本地路径
        model_id = "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
        asr_model = AutoModel(
            model=model_id,
            device=DEVICE,
            disable_update=True,
        )
        logger.info(f"Loaded FunASR model using ModelScope ID: {model_id}")
        return
    except Exception as e:
        logger.exception(f"All ASR loading methods failed: {e}")
        logger.error("Please upgrade funasr: pip install --upgrade funasr")
        logger.error("Or install from source: pip install git+https://github.com/alibaba-damo-academy/FunASR.git")
        raise


# ======================
# API Schema
# ======================

class ASROut(BaseModel):
    text: str


# ======================
# ASR Endpoint
# ======================

@app.post("/asr", response_model=ASROut)
async def speech_to_text(file: UploadFile = File(...)):
    if asr_model is None:
        raise HTTPException(status_code=503, detail="ASR model not loaded")
    
    suffix = os.path.splitext(file.filename)[-1]
    if not suffix:
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        audio_path = tmp.name

    try:
        start = time.time()
        file_size = os.path.getsize(audio_path)
        logger.info(f"/asr received file={file.filename} saved={audio_path} size={file_size} bytes")
        # 使用 FunASR 的 generate 方法
        result = asr_model.generate(input=audio_path)
        
        # FunASR 返回格式处理
        if isinstance(result, list) and len(result) > 0:
            text = result[0].get("text", "")
        elif isinstance(result, dict):
            text = result.get("text", "")
        else:
            text = str(result)

        elapsed = time.time() - start
        logger.info(f"/asr finished in {elapsed:.2f}s, text='{text}'")
        return ASROut(text=text)
    except Exception as e:
        logger.exception(f"ASR processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"ASR processing failed: {str(e)}")
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


# ======================
# 健康检查
# ======================

@app.get("/health")
def health_check():
    info = {
        "status": "healthy" if asr_model is not None else "model not loaded",
        "model_dir": MODEL_DIR,
        "device": DEVICE
    }
    logger.info(f"/health -> {info}")
    return info


# ======================
# 本地启动（可选）
# ======================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
    # uvicorn services.local_asr_server:app --host 0.0.0.0 --port 8002