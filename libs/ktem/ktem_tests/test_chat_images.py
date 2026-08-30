import json
from pathlib import Path

import gradio as gr
import pytest
from PIL import Image

import ktem.pages.chat as chat_page_module
from ktem.pages.chat import ChatPage


def _png(path: Path, size=(32, 24)) -> Path:
    Image.new("RGB", size, color=(32, 96, 160)).save(path, format="PNG")
    return path


def _page_without_ui() -> ChatPage:
    page = object.__new__(ChatPage)
    page.first_indexing_url_fn = None
    return page


def test_chat_image_is_validated_and_encoded(tmp_path):
    image_path = _png(tmp_path / "检查图.png")

    paths, names = chat_page_module.validate_chat_images([str(image_path)])
    encoded = chat_page_module.encode_chat_images(paths)

    assert paths == [str(image_path)]
    assert names == ["检查图.png"]
    assert encoded[0].startswith("data:image/png;base64,")


def test_chat_rejects_non_image_upload(tmp_path):
    text_path = tmp_path / "伪装图片.png"
    text_path.write_text("not an image", encoding="utf-8")

    with pytest.raises(gr.Error, match="无法读取图片"):
        chat_page_module.validate_chat_images([str(text_path)])


def test_image_only_message_uses_vision_prompt(tmp_path):
    image_path = _png(tmp_path / "胸片.png")
    page = _page_without_ui()

    result = page.submit_msg(
        {"text": "", "files": [str(image_path)]},
        [],
        "user-1",
        {},
        "conversation-1",
        "影像会话",
        [],
        None,
    )

    assert result[1][0][0].startswith(chat_page_module.DEFAULT_IMAGE_QUESTION)
    assert "胸片.png" in result[1][0][0]
    assert '<img src="./file=' in result[1][0][0]
    assert 'data-ktem-chat-attachments="true"' in result[1][0][0]
    assert result[2] == {
        "query": chat_page_module.DEFAULT_IMAGE_QUESTION,
        "image_paths": [str(image_path)],
    }


def test_chat_attachment_markup_is_excluded_from_fallback_llm_query(tmp_path):
    image_path = _png(tmp_path / "带 空格.png")
    markup = chat_page_module.render_chat_image_attachments(
        [str(image_path)], [image_path.name]
    )

    assert "%20" in markup
    assert chat_page_module.strip_chat_image_attachments(
        f"请分析图片\n\n{markup}"
    ) == "请分析图片"


def test_editing_an_image_question_appends_it_with_the_same_image(tmp_path):
    image_path = _png(tmp_path / "胸片.png")
    page = _page_without_ui()
    original = page.submit_msg(
        {"text": "原问题", "files": [str(image_path)]},
        [],
        "user-1",
        {},
        "conversation-1",
        "影像会话",
        [],
        None,
    )[1]

    result = page.edit_message(
        json.dumps(
            {"index": 0, "text": "请重点分析左肺", "files": [str(image_path)]},
            ensure_ascii=False,
        ),
        original,
        "user-1",
        {},
        "conversation-1",
        "影像会话",
        [],
        [],
        [],
        None,
    )

    assert result[1][0] == original[0]
    assert result[1][1][0].startswith("请重点分析左肺")
    assert result[2]["image_paths"] == [str(image_path)]


def test_chat_image_count_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_page_module, "KH_CHAT_IMAGE_MAX_FILES", 1)
    first = _png(tmp_path / "first.png")
    second = _png(tmp_path / "second.png")

    with pytest.raises(gr.Error, match="每次最多添加 1 张图片"):
        chat_page_module.validate_chat_images([str(first), str(second)])
