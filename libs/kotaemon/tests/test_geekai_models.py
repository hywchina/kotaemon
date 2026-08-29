from unittest.mock import Mock, patch

import pytest

from kotaemon.base import Document, DocumentWithEmbedding
from kotaemon.embeddings import GeekAIEmbeddings
from kotaemon.rerankings import GeekAIReranking


def json_response(payload: dict, *, status_code: int = 200) -> Mock:
    response = Mock()
    response.ok = status_code < 400
    response.status_code = status_code
    response.json.return_value = payload
    return response


@patch("kotaemon.embeddings.geekai.requests.post")
def test_geekai_embeddings_uses_typed_input_and_preserves_order(post: Mock):
    post.return_value = json_response(
        {
            "data": [
                {"index": 1, "embedding": [3.0, 4.0]},
                {"index": 0, "embedding": [1.0, 2.0]},
            ]
        }
    )
    embeddings = GeekAIEmbeddings(api_key="test-key", batch_size=2)

    output = embeddings(["第一段", "第二段"])

    assert all(isinstance(item, DocumentWithEmbedding) for item in output)
    assert [item.text for item in output] == ["第一段", "第二段"]
    assert [item.embedding for item in output] == [[1.0, 2.0], [3.0, 4.0]]
    post.assert_called_once_with(
        "https://geekai.co/api/v1/embeddings",
        headers={
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        },
        json={
            "model": "qwen3-vl-embedding",
            "input": [
                {"type": "text", "text": "第一段"},
                {"type": "text", "text": "第二段"},
            ],
        },
        timeout=60,
    )


@patch("kotaemon.embeddings.geekai.requests.post")
def test_geekai_embeddings_batches_requests(post: Mock):
    post.side_effect = [
        json_response(
            {
                "data": [
                    {"index": 0, "embedding": [1.0]},
                    {"index": 1, "embedding": [2.0]},
                ]
            }
        ),
        json_response({"data": [{"index": 0, "embedding": [3.0]}]}),
    ]
    embeddings = GeekAIEmbeddings(api_key="test-key", batch_size=2)

    output = embeddings(["a", "b", "c"])

    assert [item.embedding for item in output] == [[1.0], [2.0], [3.0]]
    assert post.call_count == 2


@patch("kotaemon.rerankings.geekai.requests.post")
def test_geekai_rerank_maps_by_document_instead_of_response_index(post: Mock):
    post.return_value = json_response(
        {
            "results": [
                {
                    # GeekAI uses this as the rank position, not the input index.
                    "index": 0,
                    "document": "苹果是一种水果",
                    "relevance_score": 0.97,
                },
                {
                    "index": 1,
                    "document": "今天会下雨",
                    "relevance_score": 0.08,
                },
            ]
        }
    )
    documents = [
        Document("今天会下雨", metadata={"source": "weather"}),
        Document("苹果是一种水果", metadata={"source": "fruit"}),
    ]
    reranker = GeekAIReranking(api_key="test-key")

    output = reranker(documents, query="什么是水果？")

    assert [item.metadata["source"] for item in output] == ["fruit", "weather"]
    assert [item.metadata["reranking_score"] for item in output] == [0.97, 0.08]
    post.assert_called_once_with(
        "https://geekai.co/api/v1/rerank",
        headers={
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        },
        json={
            "model": "qwen3-rerank",
            "query": "什么是水果？",
            "documents": ["今天会下雨", "苹果是一种水果"],
            "top_n": 2,
        },
        timeout=60,
    )


@patch("kotaemon.rerankings.geekai.requests.post")
def test_geekai_rerank_rejects_unknown_returned_document(post: Mock):
    post.return_value = json_response(
        {
            "results": [
                {
                    "index": 0,
                    "document": "接口意外返回的内容",
                    "relevance_score": 0.5,
                }
            ]
        }
    )
    reranker = GeekAIReranking(api_key="test-key", top_n=1)

    with pytest.raises(RuntimeError, match="was not in the request"):
        reranker([Document("原始内容")], query="问题")
