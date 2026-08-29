from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import torch
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONF_PATH = PROJECT_ROOT / "conf" / "rerank_models.json"


@dataclass(frozen=True)
class RerankModelConfig:
    model_name: str
    batch_size: int = 32
    max_length: int = 512


def load_default_rerank_config(
    conf_path: str | Path = DEFAULT_CONF_PATH,
) -> RerankModelConfig:
    """Load the single model marked as default in the reranker config."""
    path = Path(conf_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Rerank config not found: {path}")

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    defaults = [model for model in data.get("models", []) if model.get("default")]
    if len(defaults) != 1:
        raise ValueError("Rerank config must contain exactly one default model")

    selected = defaults[0]
    model_name = os.getenv("RERANK_MODEL_PATH", selected.get("model_name", ""))
    if not model_name:
        raise ValueError("The default rerank model is missing 'model_name'")

    model_path = Path(model_name).expanduser()
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path

    return RerankModelConfig(
        model_name=str(model_path),
        batch_size=int(selected.get("batch_size", 32)),
        max_length=int(selected.get("max_length", 512)),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_default_rerank_config(
        os.getenv("RERANK_CONFIG_PATH", str(DEFAULT_CONF_PATH))
    )
    device = os.getenv("RERANK_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    app.state.rerank_config = config
    app.state.rerank_device = device
    app.state.rerank_model = CrossEncoder(
        config.model_name,
        device=device,
        max_length=config.max_length,
    )
    yield
    app.state.rerank_model = None


app = FastAPI(title="Kotaemon Local Reranker", lifespan=lifespan)


class RerankInput(BaseModel):
    query: str = Field(min_length=1)
    texts: list[str] = Field(min_length=1)
    is_truncated: bool = True


class RerankOutputItem(BaseModel):
    index: int
    score: float


@app.get("/health")
def health(request: Request):
    config: RerankModelConfig = request.app.state.rerank_config
    return {
        "status": "ok",
        "model": config.model_name,
        "device": request.app.state.rerank_device,
    }


@app.post("/rerank", response_model=list[RerankOutputItem])
def rerank(payload: RerankInput, request: Request):
    model: CrossEncoder = request.app.state.rerank_model
    config: RerankModelConfig = request.app.state.rerank_config
    pairs = [[payload.query, text] for text in payload.texts]
    scores = model.predict(pairs, batch_size=config.batch_size)
    return sorted(
        [
            RerankOutputItem(index=index, score=float(score))
            for index, score in enumerate(scores)
        ],
        key=lambda item: item.score,
        reverse=True,
    )
