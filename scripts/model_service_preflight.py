#!/usr/bin/env python3
"""Test every configured model service before the web application starts."""

from __future__ import annotations

import os
import re
import sys
import time
from base64 import b64encode
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for relative_path in ("libs/ktem", "libs/kotaemon"):
    sys.path.insert(0, str(PROJECT_ROOT / relative_path))


class ServiceSkipped(RuntimeError):
    """Signal that a configured service intentionally needs no live check."""


@dataclass(frozen=True)
class ServiceCheckResult:
    """One model service connectivity result."""

    service: str
    status: str
    detail: str
    elapsed_seconds: float


def _safe_error(exc: Exception) -> str:
    """Return a concise error without exposing API keys or authorization headers."""

    message = re.sub(
        r"(?i)(authorization:\s*bearer\s+)[^\s,;]+",
        r"\1***",
        str(exc),
    )
    message = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "***", message)
    for variable_name in (
        "GEEKAI_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
        "KH_LOCAL_MODEL_API_KEY",
        "KH_ASR_API_KEY",
    ):
        secret = os.getenv(variable_name, "")
        if secret:
            message = message.replace(secret, "***")
    message = " ".join(message.split())
    if len(message) > 400:
        message = message[:397] + "..."
    return f"{type(exc).__name__}: {message or '未提供错误详情'}"


def _response_text(response: Any) -> str:
    """Extract text from the response shapes supported by Kotaemon LLMs."""

    for attribute in ("text", "content"):
        value = getattr(response, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list) and candidates:
        value = candidates[0]
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise RuntimeError("语言模型返回内容为空")


def check_llm(manager) -> str:
    """Send one minimal vision request through the configured default LLM."""

    from PIL import Image

    from kotaemon.base import HumanMessage

    model_name = manager.get_default_name()
    image_buffer = BytesIO()
    Image.new("RGB", (64, 64), color="white").save(image_buffer, format="PNG")
    image_url = "data:image/png;base64," + b64encode(image_buffer.getvalue()).decode(
        "ascii"
    )
    response = manager.get_default()(
        HumanMessage(
            content=[
                {"type": "text", "text": "启动视觉连通性检查，请仅回复 OK。"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        )
    )
    _response_text(response)
    return f"默认模型：{model_name}，视觉输入：通过"


def check_embedding(manager) -> str:
    """Generate one vector through the configured default embedding model."""

    model_name = manager.get_default_name()
    output = manager.get_default()("启动连通性检查")
    if not isinstance(output, list) or not output:
        raise RuntimeError("嵌入模型未返回向量")
    embedding = getattr(output[0], "embedding", None)
    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("嵌入模型返回的向量格式无效")
    return f"默认模型：{model_name}，向量维度：{len(embedding)}"


def check_rerank(manager) -> str:
    """Rerank two small documents through the configured default model."""

    from kotaemon.base import Document

    model_name = manager.get_default_name()
    documents = [
        Document(content="患者出现胸闷症状。"),
        Document(content="患者今日体温正常。"),
    ]
    output = manager.get_default().run(documents, "胸闷")
    if not isinstance(output, list) or not output:
        raise RuntimeError("重排序模型未返回结果")
    if not any("reranking_score" in (item.metadata or {}) for item in output):
        raise RuntimeError("重排序结果缺少相关性分数")
    return f"默认模型：{model_name}，返回结果：{len(output)} 条"


def check_asr(
    manager, *, enabled: bool, service_factory: Callable | None = None
) -> str:
    """Skip Mock ASR and require a health check for future real providers."""

    if not enabled:
        raise ServiceSkipped("语音识别功能未启用")

    config = manager.get()
    if config.provider.lower() == "mock":
        raise ServiceSkipped("当前使用模拟 ASR，无需检查外部接口")

    if service_factory is None:
        raise RuntimeError("真实 ASR 未提供服务工厂")
    service = service_factory()
    healthcheck = getattr(service.provider, "healthcheck", None)
    if not callable(healthcheck):
        raise RuntimeError("真实 ASR Provider 未实现 healthcheck()")
    healthcheck()
    return f"供应商：{config.provider}，模型：{config.model or '未命名'}"


def _check_llm_runtime() -> str:
    from ktem.llms.manager import llms

    return check_llm(llms)


def _check_embedding_runtime() -> str:
    from ktem.embeddings.manager import embedding_models_manager

    return check_embedding(embedding_models_manager)


def _check_rerank_runtime() -> str:
    from ktem.rerankings.manager import reranking_models_manager

    return check_rerank(reranking_models_manager)


def _check_asr_runtime() -> str:
    from theflow.settings import settings as flowsettings

    enabled = bool(getattr(flowsettings, "KH_ENABLE_ASR", False))
    if not enabled:
        raise ServiceSkipped("语音识别功能未启用")

    from ktem.asr.service import get_asr_model_manager, get_asr_service

    return check_asr(
        get_asr_model_manager(),
        enabled=True,
        service_factory=get_asr_service,
    )


def run_service_check(service: str, check: Callable[[], str]) -> ServiceCheckResult:
    """Execute one check and normalize pass, skip and failure output."""

    started_at = time.monotonic()
    try:
        detail = check()
        status = "PASS"
    except ServiceSkipped as exc:
        detail = str(exc)
        status = "SKIP"
    except Exception as exc:  # noqa: BLE001 - errors must block application startup
        detail = _safe_error(exc)
        status = "FAIL"
    return ServiceCheckResult(
        service=service,
        status=status,
        detail=detail,
        elapsed_seconds=time.monotonic() - started_at,
    )


def run_all_checks() -> list[ServiceCheckResult]:
    """Run required model checks in startup dependency order."""

    checks = (
        ("LLM", _check_llm_runtime),
        ("Embedding", _check_embedding_runtime),
        ("Rerank", _check_rerank_runtime),
        ("ASR", _check_asr_runtime),
    )
    results = []
    for service, check in checks:
        print(f"[CHECK] 正在测试 {service} 服务...", flush=True)
        result = run_service_check(service, check)
        print(
            f"[{result.status}] {result.service}：{result.detail} "
            f"({result.elapsed_seconds:.2f}s)",
            flush=True,
        )
        results.append(result)
    return results


def main() -> int:
    results = run_all_checks()
    passed = sum(result.status == "PASS" for result in results)
    skipped = sum(result.status == "SKIP" for result in results)
    failed = sum(result.status == "FAIL" for result in results)
    print(f"[SUMMARY] 模型服务通过 {passed} 项，跳过 {skipped} 项，失败 {failed} 项。")
    if failed:
        print("[ERROR] 模型服务预检失败，已阻止应用启动。")
        return 1
    print("[INFO] 所有必需模型服务检查通过，可以启动应用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
