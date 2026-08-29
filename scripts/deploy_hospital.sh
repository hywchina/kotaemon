#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_MODE="${1:---native}"
ENV_FILE="$PROJECT_DIR/.env"
ENV_TEMPLATE="$PROJECT_DIR/.env.hospital.example"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.hospital.yml"

prepare_config() {
    if [[ -f "$ENV_FILE" ]]; then
        echo "[INFO] $ENV_FILE 已存在，未覆盖。"
        return 0
    fi
    cp "$ENV_TEMPLATE" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "[ACTION] 已生成 $ENV_FILE，请填写管理员密码和模型服务密钥后重新执行部署。"
}

if [[ "$DEPLOY_MODE" == "--prepare" ]]; then
    prepare_config
    exit 0
fi

if [[ ! -f "$ENV_FILE" ]]; then
    prepare_config
    exit 2
fi

cd "$PROJECT_DIR"
case "$DEPLOY_MODE" in
    --native)
        ./run.sh doctor
        ./run.sh restart
        ./run.sh status
        ;;
    --docker)
        if ! docker compose version >/dev/null 2>&1; then
            echo "[ERROR] 未检测到 Docker Compose v2。" >&2
            exit 1
        fi
        mkdir -p "$PROJECT_DIR/ktem_app_data"
        export KH_CONTAINER_UID="${KH_CONTAINER_UID:-$(id -u)}"
        export KH_CONTAINER_GID="${KH_CONTAINER_GID:-$(id -g)}"
        docker compose -f "$COMPOSE_FILE" run --rm --no-deps app \
            .venv/bin/python scripts/hospital_preflight.py --env-file /dev/null
        docker compose -f "$COMPOSE_FILE" up -d --pull never
        docker compose -f "$COMPOSE_FILE" ps
        ;;
    *)
        echo "用法: ./scripts/deploy_hospital.sh {--prepare|--native|--docker}" >&2
        exit 2
        ;;
esac
