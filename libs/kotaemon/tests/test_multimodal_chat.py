from kotaemon.indices.qa.citation_qa import build_multimodal_message_content


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
