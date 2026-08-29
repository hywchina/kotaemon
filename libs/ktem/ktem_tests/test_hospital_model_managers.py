from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.mark.parametrize(
    ("module_name", "manager_name", "table_name", "settings_name", "allowed_name"),
    (
        (
            "ktem.llms.manager",
            "LLMManager",
            "LLMTable",
            "KH_LLMS",
            "allowed-llm",
        ),
        (
            "ktem.embeddings.manager",
            "EmbeddingManager",
            "EmbeddingTable",
            "KH_EMBEDDINGS",
            "allowed-embedding",
        ),
        (
            "ktem.rerankings.manager",
            "RerankingManager",
            "RerankingTable",
            "KH_RERANKINGS",
            "allowed-reranker",
        ),
    ),
)
def test_hospital_manager_ignores_stale_database_providers(
    module_name: str,
    manager_name: str,
    table_name: str,
    settings_name: str,
    allowed_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module: Any = __import__(module_name, fromlist=[manager_name])
    table = getattr(module, table_name)
    manager_class = getattr(module, manager_name)
    test_engine = create_engine("sqlite:///:memory:")
    table.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        session.add_all(
            [
                table(name=allowed_name, spec={"__type__": "allowed"}, default=True),
                table(name="stale-public", spec={"__type__": "public"}, default=False),
            ]
        )
        session.commit()

    monkeypatch.setattr(module, "engine", test_engine)
    monkeypatch.setattr(module.flowsettings, "KH_HOSPITAL_MODE", True)
    monkeypatch.setattr(
        module.flowsettings,
        settings_name,
        {
            allowed_name: {
                "spec": {"__type__": "allowed"},
                "default": True,
                "managed": True,
            }
        },
    )
    loaded_specs: list[dict] = []
    monkeypatch.setattr(
        module,
        "deserialize",
        lambda spec, safe: loaded_specs.append(spec) or object(),
    )

    manager = manager_class()

    assert set(manager.info()) == {allowed_name}
    assert manager.get_default_name() == allowed_name
    assert loaded_specs == [{"__type__": "allowed"}]
