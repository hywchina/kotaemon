"""Tests for startup model service connectivity checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from kotaemon.base import DocumentWithEmbedding

SCRIPT_PATH = Path(__file__).parents[3] / "scripts/model_service_preflight.py"
SPEC = importlib.util.spec_from_file_location("model_service_preflight", SCRIPT_PATH)
model_service_preflight = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = model_service_preflight
SPEC.loader.exec_module(model_service_preflight)


class FakeManager:
    def __init__(self, model):
        self.model = model

    def get_default_name(self):
        return "test-model"

    def get_default(self):
        return self.model


def test_llm_embedding_and_rerank_checks_validate_response_shapes():
    llm_requests = []

    def llm(prompt):
        llm_requests.append(prompt)
        return SimpleNamespace(text="OK")

    def embedding(text):
        return [DocumentWithEmbedding(content=text, embedding=[0.1, 0.2, 0.3])]

    class Reranker:
        def run(self, documents, query):
            del query
            documents[0].metadata["reranking_score"] = 0.9
            return documents

    assert model_service_preflight.check_llm(FakeManager(llm)) == (
        "默认模型：test-model，视觉输入：通过"
    )
    content = llm_requests[0].content
    assert content[0]["type"] == "text"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "向量维度：3" in model_service_preflight.check_embedding(
        FakeManager(embedding)
    )
    assert "返回结果：2 条" in model_service_preflight.check_rerank(
        FakeManager(Reranker())
    )


def test_invalid_model_response_fails_the_service_check():
    result = model_service_preflight.run_service_check(
        "Embedding",
        lambda: model_service_preflight.check_embedding(FakeManager(lambda _: [])),
    )

    assert result.status == "FAIL"
    assert "未返回向量" in result.detail


def test_mock_asr_is_reported_as_skipped():
    manager = SimpleNamespace(
        get=lambda: SimpleNamespace(provider="mock", model="mock-asr")
    )

    result = model_service_preflight.run_service_check(
        "ASR",
        lambda: model_service_preflight.check_asr(manager, enabled=True),
    )

    assert result.status == "SKIP"
    assert "模拟 ASR" in result.detail


def test_error_output_redacts_api_keys(monkeypatch):
    monkeypatch.setenv("GEEKAI_API_KEY", "sk-secret-from-env")

    result = model_service_preflight.run_service_check(
        "LLM",
        lambda: (_ for _ in ()).throw(
            RuntimeError("Authorization: Bearer sk-secret-from-env")
        ),
    )

    assert result.status == "FAIL"
    assert "sk-secret-from-env" not in result.detail
    assert "***" in result.detail
