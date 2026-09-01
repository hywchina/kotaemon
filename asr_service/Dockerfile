FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    ASR_DATA_DIR=/opt/asr-service/data

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.3

WORKDIR /opt/asr-service
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra funasr

COPY . .

EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD .venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health/ready', timeout=3)" || exit 1

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
