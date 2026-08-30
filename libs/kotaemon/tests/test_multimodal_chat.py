import time

from kotaemon.base import BaseComponent, Document, LLMInterface
from kotaemon.indices.qa import citation_qa
from kotaemon.indices.qa.citation_qa import (
    AnswerWithContextPipeline,
    build_multimodal_message_content,
)
from kotaemon.llms import ChatLLM


class _StreamingLLM(ChatLLM):
    def run(self, *_args, **_kwargs):
        return LLMInterface(content="回答")

    def stream(self, *_args, **_kwargs):
        yield LLMInterface(content="回答")


class _DelayedMindmap(BaseComponent):
    def run(self, *_args, **_kwargs):
        time.sleep(0.03)
        return Document(content="思维导图")


def test_user_images_are_included_without_multimodal_evidence_setting():
    content = build_multimodal_message_content(
        "请分析图片",
        user_images=["data:image/png;base64,user"],
        evidence_images=["data:image/png;base64,evidence"],
        include_evidence_images=False,
    )

    assert content == [
        {"type": "text", "text": "请分析图片"},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,user"},
        },
    ]


def test_user_images_precede_evidence_images_and_respect_limit():
    content = build_multimodal_message_content(
        "问题",
        user_images=["user-image"],
        evidence_images=[f"evidence-{index}" for index in range(20)],
        include_evidence_images=True,
    )

    image_urls = [item["image_url"]["url"] for item in content[1:]]
    assert image_urls[0] == "user-image"
    assert len(image_urls) == 10


def test_mindmap_uses_its_own_longer_optional_pipeline_timeout(monkeypatch):
    monkeypatch.setattr(citation_qa, "CITATION_TIMEOUT", 0.0)
    monkeypatch.setattr(citation_qa, "MINDMAP_TIMEOUT", 0.2)
    pipeline = AnswerWithContextPipeline(
        llm=_StreamingLLM(),
        create_mindmap_pipeline=_DelayedMindmap(),
        enable_mindmap=True,
    )

    stream = pipeline.stream("问题", "证据")
    while True:
        try:
            next(stream)
        except StopIteration as completed:
            answer = completed.value
            break

    assert answer.metadata["mindmap"].text == "思维导图"
