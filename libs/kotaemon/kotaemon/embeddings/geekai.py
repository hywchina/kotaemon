from __future__ import annotations

import asyncio
from typing import Optional

import requests

from kotaemon.base import Document, DocumentWithEmbedding, Param

from .base import BaseEmbeddings


class GeekAIEmbeddings(BaseEmbeddings):
    """Embedding client for GeekAI's multimodal embedding endpoint.

    GeekAI's Qwen3-VL embedding API uses OpenAI's response shape, but its input
    is a list of typed content objects instead of a string or list of strings.
    """

    endpoint_url: str = Param(
        "https://geekai.co/api/v1/embeddings",
        help="GeekAI embeddings endpoint URL",
        required=True,
    )
    api_key: str = Param(None, help="GeekAI API key", required=True)
    model: str = Param(
        "qwen3-vl-embedding",
        help="GeekAI embedding model name",
        required=True,
    )
    batch_size: int = Param(16, help="Number of texts sent in each API request")
    timeout: Optional[float] = Param(60, help="API request timeout in seconds")

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = requests.post(
            self.endpoint_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": [
                    {"type": "text", "text": text if text else " "} for text in texts
                ],
            },
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(
                f"GeekAI embeddings returned HTTP {response.status_code} "
                "with a non-JSON response"
            ) from exc

        if not response.ok:
            message = payload.get("message") or payload.get("error") or "unknown error"
            raise RuntimeError(
                f"GeekAI embeddings failed with HTTP {response.status_code}: {message}"
            )

        items = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
        if len(items) != len(texts):
            raise RuntimeError(
                "GeekAI embeddings returned an unexpected number of vectors: "
                f"expected {len(texts)}, got {len(items)}"
            )

        embeddings = [item.get("embedding") for item in items]
        if any(not isinstance(embedding, list) for embedding in embeddings):
            raise RuntimeError("GeekAI embeddings response is missing vector data")
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
