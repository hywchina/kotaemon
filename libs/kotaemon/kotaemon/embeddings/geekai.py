from __future__ import annotations

import asyncio
from typing import Optional

import requests

from kotaemon.base import Document, DocumentWithEmbedding, Param

from .base import BaseEmbeddings


class OpenAICompatibleEmbeddings(BaseEmbeddings):
    """Embedding client for OpenAI-compatible HTTP endpoints.

    Most compatible services accept a list of strings. Some multimodal
    gateways, including GeekAI's Qwen3-VL endpoint, instead require typed text
    objects while keeping the OpenAI response shape. ``input_format`` keeps
    that transport detail out of the embedding and retrieval business logic.
    """

    endpoint_url: str = Param(
        None,
        help="OpenAI-compatible embeddings endpoint URL",
        required=True,
    )
    api_key: str = Param(None, help="API key", required=True)
    model: str = Param(
        None,
        help="Embedding model name",
        required=True,
    )
    input_format: str = Param(
        "openai",
        help="Request input format: openai (string list) or typed_text",
    )
    batch_size: int = Param(16, help="Number of texts sent in each API request")
    timeout: Optional[float] = Param(60, help="API request timeout in seconds")

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.input_format == "openai":
            request_input: list[str] | list[dict[str, str]] = [
                text if text else " " for text in texts
            ]
        elif self.input_format == "typed_text":
            request_input = [
                {"type": "text", "text": text if text else " "} for text in texts
            ]
        else:
            raise ValueError(
                "input_format must be either 'openai' or 'typed_text'"
            )

        response = requests.post(
            self.endpoint_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": request_input,
            },
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(
                f"Embedding service returned HTTP {response.status_code} "
                "with a non-JSON response"
            ) from exc

        if not response.ok:
            message = payload.get("message") or payload.get("error") or "unknown error"
            raise RuntimeError(
                f"Embedding service failed with HTTP {response.status_code}: {message}"
            )

        items = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
        if len(items) != len(texts):
            raise RuntimeError(
                "Embedding service returned an unexpected number of vectors: "
                f"expected {len(texts)}, got {len(items)}"
            )

        embeddings = [item.get("embedding") for item in items]
        if any(not isinstance(embedding, list) for embedding in embeddings):
            raise RuntimeError("Embedding service response is missing vector data")
        return embeddings

    def invoke(
        self,
        text: str | list[str] | Document | list[Document],
        *args,
        **kwargs,
    ) -> list[DocumentWithEmbedding]:
        del args, kwargs
        input_docs = self.prepare_input(text)
        if not input_docs:
            return []

        batch_size = max(int(self.batch_size), 1)
        vectors: list[list[float]] = []
        for start in range(0, len(input_docs), batch_size):
            batch = input_docs[start : start + batch_size]
            vectors.extend(self._embed_batch([doc.text or " " for doc in batch]))

        return [
            DocumentWithEmbedding(embedding=vector, content=doc)
            for doc, vector in zip(input_docs, vectors)
        ]

    async def ainvoke(
        self,
        text: str | list[str] | Document | list[Document],
        *args,
        **kwargs,
    ) -> list[DocumentWithEmbedding]:
        return await asyncio.to_thread(self.invoke, text, *args, **kwargs)


class GeekAIEmbeddings(OpenAICompatibleEmbeddings):
    """Backward-compatible preset for GeekAI's typed Qwen3-VL endpoint."""

    endpoint_url: str = Param(
        "https://geekai.co/api/v1/embeddings",
        help="GeekAI embeddings endpoint URL",
        required=True,
    )
    model: str = Param(
        "qwen3-vl-embedding",
        help="GeekAI embedding model name",
        required=True,
    )
    input_format: str = Param("typed_text", help="GeekAI typed text input format")
