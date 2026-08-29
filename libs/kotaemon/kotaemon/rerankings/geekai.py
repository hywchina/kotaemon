from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional

import requests

from kotaemon.base import Document, Param

from .base import BaseReranking


class GeekAIReranking(BaseReranking):
    """Rerank documents with GeekAI's Qwen3 rerank endpoint."""

    endpoint_url: str = Param(
        "https://geekai.co/api/v1/rerank",
        help="GeekAI rerank endpoint URL",
        required=True,
    )
    api_key: str = Param(None, help="GeekAI API key", required=True)
    model_name: str = Param(
        "qwen3-rerank",
        help="GeekAI rerank model name",
        required=True,
    )
    top_n: Optional[int] = Param(
        None,
        help="Maximum number of reranked documents; defaults to all inputs",
    )
    timeout: Optional[float] = Param(60, help="API request timeout in seconds")

    def run(self, documents: list[Document], query: str) -> list[Document]:
        if not documents:
            return []

        input_docs = [
            document if isinstance(document, Document) else Document(content=document)
            for document in documents
        ]
        document_texts = [doc.text or " " for doc in input_docs]
        top_n = min(self.top_n or len(input_docs), len(input_docs))
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
                "top_n": top_n,
            },
            timeout=self.timeout,
        )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(
                f"GeekAI rerank returned HTTP {response.status_code} "
                "with a non-JSON response"
            ) from exc

        if not response.ok:
            message = payload.get("message") or payload.get("error") or "unknown error"
            raise RuntimeError(
                f"GeekAI rerank failed with HTTP {response.status_code}: {message}"
            )

        # GeekAI currently returns the rank position in `index`, not the input
        # document index. Map by the returned document text to preserve identity.
        indices_by_text: dict[str, deque[int]] = defaultdict(deque)
        for index, content in enumerate(document_texts):
            indices_by_text[content].append(index)

        output: list[Document] = []
        for result in payload.get("results", []):
            returned_document = result.get("document")
            if (
                not isinstance(returned_document, str)
                or not indices_by_text[returned_document]
            ):
                raise RuntimeError(
                    "GeekAI rerank response contains a document that was not in the "
                    "request"
                )
            original_index = indices_by_text[returned_document].popleft()
            document = input_docs[original_index]
            document.metadata["reranking_score"] = float(
                result.get("relevance_score", 0.0)
            )
            output.append(document)

        if len(output) != top_n:
            raise RuntimeError(
                "GeekAI rerank returned an unexpected number of results: "
                f"expected {top_n}, got {len(output)}"
            )
        return output
