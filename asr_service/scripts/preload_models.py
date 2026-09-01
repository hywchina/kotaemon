"""Download pinned models into this service and verify local-only loading."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = SERVICE_ROOT / "models"
CACHE_ROOT = SERVICE_ROOT / "model-cache"
MANIFEST_PATH = MODEL_ROOT / "manifest.json"
sys.path.insert(0, str(SERVICE_ROOT))

from app.backends.funasr import FunASRBackend  # noqa: E402
from app.config import Settings  # noqa: E402

MODEL_SPECS = {
    "streaming_model": {
        "role": "streaming-asr",
        "model_id": (
            "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
        ),
        "revision": "v2.0.4",
    },
    "offline_model": {
        "role": "offline-asr",
        "model_id": (
            "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
        ),
        "revision": "v2.0.4",
    },
    "vad_model": {
        "role": "vad",
        "model_id": "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        "revision": "v2.0.4",
    },
    "punctuation_model": {
        "role": "punctuation",
        "model_id": "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        "revision": "v2.0.4",
    },
    "speaker_model": {
        "role": "speaker",
        "model_id": "iic/speech_campplus_sv_zh-cn_16k-common",
        "revision": "v2.0.2",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_files(directory: Path) -> list[dict[str, str | int]]:
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.name.startswith(".cache"):
            files.append(
                {
                    "path": str(path.relative_to(SERVICE_ROOT)),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    return files


def _write_manifest(model_paths: dict[str, str]) -> None:
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "funasr_version": version("funasr"),
        "modelscope_version": version("modelscope"),
        "models": [],
    }
    for setting_name, spec in MODEL_SPECS.items():
        directory = Path(model_paths[setting_name])
        manifest["models"].append(
            {
                **spec,
                "directory": str(directory.relative_to(SERVICE_ROOT)),
                "files": _model_files(directory),
            }
        )
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def download_models() -> dict[str, str]:
    from modelscope.hub.snapshot_download import snapshot_download

    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    model_paths = {}
    for setting_name, spec in MODEL_SPECS.items():
        destination = MODEL_ROOT / spec["role"]
        print(f"Downloading {spec['model_id']}@{spec['revision']} to {destination}")
        downloaded = snapshot_download(
            model_id=spec["model_id"],
            revision=spec["revision"],
            cache_dir=CACHE_ROOT,
            local_dir=str(destination),
        )
        model_paths[setting_name] = str(Path(downloaded).resolve())
    _write_manifest(model_paths)
    return model_paths


def existing_models() -> dict[str, str]:
    model_paths = {
        setting_name: str((MODEL_ROOT / spec["role"]).resolve())
        for setting_name, spec in MODEL_SPECS.items()
    }
    missing = [path for path in model_paths.values() if not Path(path).is_dir()]
    if missing:
        raise RuntimeError("Missing local model directories: " + ", ".join(missing))
    return model_paths


async def verify_local_loading(model_paths: dict[str, str]) -> None:
    settings = replace(
        Settings.from_env(),
        backend="funasr",
        offline=True,
        device=os.getenv("ASR_DEVICE", "cpu"),
        **model_paths,
    )
    settings.validate()
    backend = FunASRBackend(settings)
    await backend.startup()
    print("Loaded every model from a local directory:")
    for role, model in backend.model_info().items():
        print(f"- {role}: {model}")
    await backend.shutdown()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Do not access the network; load the existing local model directories.",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download and checksum models without instantiating them.",
    )
    args = parser.parse_args()
    if args.verify_only and args.download_only:
        parser.error("--verify-only and --download-only cannot be combined")

    os.environ["MODELSCOPE_CACHE"] = str(CACHE_ROOT)
    os.environ["HF_HOME"] = str(SERVICE_ROOT / "model-cache" / "huggingface")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    model_paths = existing_models() if args.verify_only else download_models()
    if not args.download_only:
        await verify_local_loading(model_paths)


if __name__ == "__main__":
    os.chdir(SERVICE_ROOT)
    asyncio.run(main())
