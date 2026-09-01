#!/usr/bin/env bash
set -euo pipefail

service_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$service_root"

if [[ ! -f .env ]]; then
  echo "Missing $service_root/.env; copy .env.example and set ASR_API_KEY." >&2
  exit 1
fi

set -a
source .env
set +a

if [[ "${ASR_BACKEND:-}" != "funasr" || "${ASR_OFFLINE:-}" != "true" ]]; then
  echo "Offline startup requires ASR_BACKEND=funasr and ASR_OFFLINE=true." >&2
  exit 1
fi

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

exec .venv/bin/uvicorn app.main:app \
  --host "${ASR_HOST:-127.0.0.1}" \
  --port "${ASR_PORT:-8002}"
