from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Optional

import requests

from kotaemon.base import Document, Param

from .base import BaseReranking

logger = logging.getLogger(__name__)


class OpenAICompatibleReranking(BaseReranking):
    """Rerank documents through an OpenAI-style authenticated endpoint.

    Reranking is not part of the official OpenAI API. Compatible gateways
    commonly return either the original input index or the echoed document;
    this adapter accepts both response shapes so provider details do not leak
    into retrieval pipelines.
    """

    endpoint_url: str = Param(
        None,
        help="OpenAI-compatible rerank endpoint URL",
        required=True,
    )
    api_key: str = Param(None, help="API key", required=True)
    model_name: str = Param(
        None,
        help="Rerank model name",
        required=True,
    )
    top_n: Optional[int] = Param(
        None,
        help="Maximum number of reranked documents; defaults to all inputs",
    )
    batch_size: int = Param(
        32,
        help="Maximum number of documents sent in one rerank request",
    )
    max_batch_characters: int = Param(
        24000,
        help="Maximum combined document characters sent in one rerank request",
    )
    max_document_characters: int = Param(
        12000,
        help="Maximum characters from one document sent to the rerank service",
    )
    response_mapping: str = Param(
        "auto",
        help="Response mapping: auto, document, or index",
    )
    timeout: Optional[float] = Param(60, help="API request timeout in seconds")

    def _fallback(
        self,
        documents: list[Document],
        top_n: int,
        reason: str,
    ) -> list[Document]:
        """Keep the original retrieval order when optional reranking degrades."""

        logger.warning("Rerank service degraded to retrieval order: %s", reason)
        output = documents[:top_n]
        for document in output:
            document.metadata["reranking_fallback"] = True
        return output

    def _request_batch(
        self,
        batch: list[tuple[int, Document, str]],
        query: str,
        top_n: int,
    ) -> list[tuple[float, int, Document]]:
        if self.response_mapping not in {"auto", "document", "index"}:
            raise ValueError("response_mapping must be auto, document, or index")

        document_texts = [text for _, _, text in batch]
        response = requests.post(
            self.endpoint_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "query": query,
                "documents": document_texts,
                "top_n": min(top_n, len(batch)),
            },
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(
                f"Rerank service returned HTTP {response.status_code} "
                "with a non-JSON response"
            ) from exc

        if not response.ok:
            message = payload.get("message") or payload.get("error") or "unknown error"
            raise RuntimeError(
                f"Rerank service failed with HTTP {response.status_code}: {message}"
            )

        # Prefer the echoed document because some gateways use `index` as the
        # result rank. Fall back to the input index used by other providers.
        indices_by_text: dict[str, deque[int]] = defaultdict(deque)
        for batch_index, content in enumerate(document_texts):
            indices_by_text[content].append(batch_index)

        output: list[tuple[float, int, Document]] = []
        used_batch_indices: set[int] = set()
        for result in payload.get("results", []):
            returned_document = result.get("document")
            if isinstance(returned_document, dict):
                returned_document = returned_document.get("text")

            batch_index: int | None = None
            if self.response_mapping != "index" and (
                isinstance(returned_document, str)
                and indices_by_text[returned_document]
            ):
                batch_index = indices_by_text[returned_document].popleft()
            elif self.response_mapping != "document":
                returned_index = result.get("index")
                if (
                    isinstance(returned_index, int)
                    and 0 <= returned_index < len(batch)
                    and returned_index not in used_batch_indices
                ):
                    batch_index = returned_index

            if batch_index is None:
                raise RuntimeError(
                    "Rerank service response cannot be mapped to an input document"
                )
            used_batch_indices.add(batch_index)
            original_index, document, _ = batch[batch_index]
            score = float(result.get("relevance_score", 0.0))
            document.metadata["reranking_score"] = score
            output.append((score, original_index, document))

        expected = min(top_n, len(batch))
        if len(output) != expected:
            raise RuntimeError(
                "Rerank service returned an unexpected number of results: "
                f"expected {expected}, got {len(output)}"
            )
        return output

    def _iter_batches(
        self, documents: list[Document]
    ) -> list[list[tuple[int, Document, str]]]:
        batch_size = max(1, int(self.batch_size))
        batch_character_limit = max(1, int(self.max_batch_characters))
        document_character_limit = max(1, int(self.max_document_characters))
        batches: list[list[tuple[int, Document, str]]] = []
        batch: list[tuple[int, Document, str]] = []
        batch_characters = 0

        for index, document in enumerate(documents):
            text = (document.text or " ")[:document_character_limit]
            if batch and (
                len(batch) >= batch_size
                or batch_characters + len(text) > batch_character_limit
            ):
                batches.append(batch)
                batch = []
                batch_characters = 0
            batch.append((index, document, text))
            batch_characters += len(text)

        if batch:
            batches.append(batch)
        return batches

    def run(self, documents: list[Document], query: str) -> list[Document]:
        if not documents:
            return []

        input_docs = [
            document if isinstance(document, Document) else Document(content=document)
            for document in documents
        ]
        top_n = min(self.top_n or len(input_docs), len(input_docs))
        try:
            ranked: list[tuple[float, int, Document]] = []
            for batch in self._iter_batches(input_docs):
                ranked.extend(
                    self._request_batch(batch, query=query, top_n=top_n)
                )
        except (requests.RequestException, RuntimeError, TypeError, ValueError) as exc:
            return self._fallback(input_docs, top_n, str(exc))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [document for _, _, document in ranked[:top_n]]


class GeekAIReranking(OpenAICompatibleReranking):
    """Backward-compatible preset for GeekAI's Qwen3 rerank endpoint."""

    endpoint_url: str = Param(
        "https://geekai.co/api/v1/rerank",
        help="GeekAI rerank endpoint URL",
        required=True,
    )
    model_name: str = Param(
        "qwen3-rerank",
        help="GeekAI rerank model name",
        required=True,
    )
    response_mapping: str = Param(
        "document",
        help="GeekAI echoes documents while index contains the rank position",
    )
