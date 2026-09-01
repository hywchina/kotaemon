# Kotaemon standalone ASR service

> 在新服务器部署前，请先阅读完整中文手册：
> [DEPLOYMENT_ZH.md](DEPLOYMENT_ZH.md)。其中包含服务器要求、联网/离线模型下载、
> 原生与 Docker 启动、systemd、Kotaemon 配置、声纹迁移、验收和故障排查。

This directory is an independent API service. It does not import or modify the
Kotaemon application. It implements the selected stack:

- FunASR `paraformer-zh-streaming` for low-latency partial text.
- FunASR `paraformer-zh` + FSMN-VAD + CT-Punc for final correction.
- 3D-Speaker CAM++ for speaker embeddings.
- Incremental cosine clustering for session-local speaker labels.
- A private SQLite voiceprint registry for enrolled identity matching.

The API output intentionally matches Kotaemon's existing provider-neutral
segment fields. See [API.md](API.md) for the wire contract.

## Directory boundary

All ASR service implementation, runtime data, deployment files, model metadata,
clients and tests live below `asr_service/`. The parent Kotaemon project is not a
Python dependency of this service.

## Current local deployment

The checked-in service profile is designed to load models exclusively from
`models/`. On the prepared Intel macOS host, the isolated environment and all
five model snapshots are already installed below this directory. Runtime model
loading does not require ModelScope or Hugging Face network access.

Start the real offline service in the foreground:

```bash
cd asr_service
./scripts/start_offline.sh
```

It listens on `127.0.0.1:8002`. The API key is stored only in the ignored
`.env` file. Check readiness with:

```bash
set -a; source .env; set +a
curl http://127.0.0.1:8002/health/ready
```

## Run protocol tests without loading models

```bash
cd asr_service
uv sync --group dev
ASR_API_KEY=local-test-key uv run uvicorn app.main:app \
  --host 127.0.0.1 --port 8002
uv run pytest
```

Tests inject the `mock` backend to exercise WebSocket revisions, speaker labels,
voiceprint CRUD and identity attachment quickly. The deployed `.env` remains on
the real `funasr` backend.

## Run FunASR and 3D-Speaker

```bash
cd asr_service
uv sync --extra funasr --group dev
cp .env.example .env
# Set ASR_BACKEND=funasr, replace ASR_API_KEY, and choose cpu or cuda.
uv run python scripts/preload_models.py
./scripts/start_offline.sh
```

The preload command pins model revisions, writes them to `models/`, generates
`models/manifest.json` with SHA-256 checksums, and verifies local loading. To
repeat the loading check with no downloads:

```bash
uv run --env-file .env python scripts/preload_models.py --verify-only
```

Only the first model preload requires network access. Hospital runtime must use
a prebuilt image or a pre-populated `models/` directory and must not download
models.
For GPU deployment, install the PyTorch build matching the host CUDA driver
before syncing the remaining dependencies.

## Docker

The included image is a CPU-oriented baseline. Download or restore `models/`
on the host first; Compose mounts that directory read-only at runtime instead
of copying roughly 2.1 GB of weights into the image:

```bash
cd asr_service
cp .env.example .env
# Edit .env and set ASR_BACKEND=funasr.
docker compose build
docker compose up -d
```

Build context is this directory only. `data/` remains a writable host volume.
A GPU production image should use an approved CUDA/PyTorch base image.

## Security and operational constraints

- Voice embeddings are biometric data. Encrypt the service volume, audit every
  enrollment/deletion, and define retention and consent policy before rollout.
- Do not expose this API to the public network. Use TLS and network allowlists.
- Replace the development key and avoid long-lived keys in browser JavaScript.
- Threshold defaults are placeholders. Tune them using de-identified hospital
  recordings and report FAR/FRR, DER, Chinese CER and latency percentiles.
- Track model licenses and checksums in [MODEL_LICENSES.md](MODEL_LICENSES.md).
