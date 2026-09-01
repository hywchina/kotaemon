from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import pandas as pd
from ktem.index.file.ui import FileIndexPage
from ktem.pages.chat import ChatPage, open_info_panel_for_evidence, toggle_info_panel
from ktem.pages.chat import chat_panel as chat_panel_module
from ktem.pages.login import LoginPage, fetch_creds, signin_js
from ktem.reasoning.simple import FullDecomposeQAPipeline, FullQAPipeline
from ktem.utils.i18n import translate_choices, translate_ui_text


def _page_without_ui() -> FileIndexPage:
    page = object.__new__(FileIndexPage)
    page.selected_panel_false = "未选择文件"
    page.selected_panel_true = "已选文件：{name}"
    return page


def test_login_form_is_available_without_optional_ui_javascript() -> None:
    with gr.Blocks():
        page = LoginPage(SimpleNamespace(app_name="AI 辅助诊断系统"))

    assert page.usn.visible is True
    assert page.pwd.visible is True
    assert page.btn_login.visible is True
    assert "localStorage.getItem" in fetch_creds
    assert "localStorage.setItem" in signin_js
    assert "getStorage(" not in fetch_creds


def test_localized_file_table_selection_keeps_internal_id() -> None:
    page = _page_without_ui()
    table = pd.DataFrame([{"ID": "file-1", "文件名": "病历.pdf"}])
    event = SimpleNamespace(value="病历.pdf", index=(0, 1), selected=True)

    file_id, label = page.interact_file_list(table, event)

    assert file_id == "file-1"
    assert label == "已选文件：病历.pdf"


def test_group_selection_uses_untranslated_state_values() -> None:
    page = _page_without_ui()
    groups = [{"id": "group-1", "name": "心内科", "files": ["file-1"]}]
    event = SimpleNamespace(value="心内科", index=(0, 1), selected=True)

    result = page.interact_group_list(groups, event)

    assert result == ("### 分组信息", "group-1", "心内科", ["file-1"])


def test_chat_composer_uses_one_send_or_microphone_action(monkeypatch) -> None:
    monkeypatch.setattr(chat_panel_module, "KH_ENABLE_ASR", True)
    monkeypatch.setattr(
        chat_panel_module,
        "get_asr_service",
        lambda: SimpleNamespace(is_mock=True),
    )

    with gr.Blocks():
        panel = chat_panel_module.ChatPanel(SimpleNamespace(app_name="医院知识库"))

    assert panel.submit_btn.value == "↑"
    assert panel.asr_start_button.value == "🎙"
    assert panel.text_input.file_types == ["image"]
    assert panel.text_input.file_count == "multiple"
    assert panel.text_input.placeholder == "请输入问题"
    assert panel.pending_multimodal_input.value == {"query": "", "image_paths": []}
    assert panel.chatbot.placeholder.startswith("开始一次辅助诊断问答")
    assert not hasattr(panel, "regen_btn")


def test_chat_composer_uses_streaming_audio_for_real_asr(monkeypatch) -> None:
    monkeypatch.setattr(chat_panel_module, "KH_ENABLE_ASR", True)
    monkeypatch.setattr(
        chat_panel_module,
        "get_asr_service",
        lambda: SimpleNamespace(is_mock=False),
    )

    with gr.Blocks():
        panel = chat_panel_module.ChatPanel(SimpleNamespace(app_name="医院知识库"))

    assert panel.uses_live_audio is True
    assert panel.asr_live_audio.streaming is True
    assert panel.asr_live_audio.sources == ["microphone"]
    assert panel.asr_live_audio.type == "numpy"
    assert panel.asr_cancel_bridge.value == "取消录音"
    assert panel.asr_confirm_bridge.value == "完成录音"
    assert not hasattr(panel, "asr_start_button")


def test_chat_composer_assets_define_upload_menu_and_inline_recorder() -> None:
    assets_root = Path(__file__).parents[1] / "ktem" / "assets"
    main_js = (assets_root / "js" / "main.js").read_text(encoding="utf-8")
    medical_css = (assets_root / "css" / "medical.css").read_text(
        encoding="utf-8"
    )

    for fragment in (
        "Authentication callbacks run during the initial Gradio load",
        "ktem-attachment-menu",
        "添加图片",
        "添加文件",
        "#quick-file input[type=\"file\"]",
        "ktem-composer-notice",
        "图片仅支持 PNG、JPEG 和 WebP 格式",
        'classList.toggle("has-attachments", hasFiles)',
        "ktem-inline-recorder",
        "Array.from({ length: 72 }",
        'endRecording("cancel")',
        'endRecording("confirm")',
    ):
        assert fragment in main_js

    assert main_js.index("globalThis.getStorage") < main_js.index(
        'const chatTab = document.getElementById("chat-tab")'
    )
    assert "feedbackSubmitButton.parentNode === feedbackSubmitContent" in main_js
    assert (
        'reportDiv.insertBefore(shareConvCheckbox, reportDiv.querySelector("button"))'
        not in main_js
    )
    assert "feedbackSubmitContent.insertBefore" in main_js

    for selector in (
        ".ktem-attachment-menu",
        ".ktem-composer-notice",
        "#chat-composer-row.has-attachments",
        ".ktem-inline-recorder",
        "#asr-live-audio",
        "body.ktem-asr-recording #main-chat-bot .message.pending",
    ):
        assert selector in medical_css

    for recorder_style in (
        "width: min(56%, 460px)",
        "transform: translate(-50%, -50%)",
        "flex: 0 0 2px",
        "max-height: 24px",
    ):
        assert recorder_style in medical_css

    for composer_style in (
        "width: min(calc(100% - 32px), 964px)",
        "max-height: 180px",
        "textarea.scroll-hide::-webkit-scrollbar",
        "#chat-composer-row.has-expanded-text",
        "bottom: 10px",
    ):
        assert composer_style in medical_css

    for voiceprint_style in (
        "#voiceprint-display-name",
        "#voiceprint-sample-tabs",
        ".voiceprint-action-row",
        "#voiceprint-register-recording",
        ".stretch:has(> #suggest-chat-checkbox)",
        "#feedback-submit-panel #is-public-checkbox",
    ):
        assert voiceprint_style in medical_css


def test_quick_upload_mentions_indexed_documents_in_composer() -> None:
    page = _page_without_ui()

    result = page.complete_quick_file_upload(
        ["/tmp/检查 报告.pdf", "/tmp/用药.md"],
        ["file-1", "file-2"],
        {"text": "请总结", "files": ["/tmp/image.png"]},
    )

    assert result[2] == {
        "text": '请总结 @"检查 报告.pdf" @"用药.md"',
        "files": ["/tmp/image.png"],
    }


def test_quick_upload_does_not_mention_failed_or_duplicate_documents() -> None:
    page = _page_without_ui()
    existing = {"text": '请比较 @"病历.pdf"', "files": []}

    failed = page.complete_quick_file_upload(["/tmp/失败.pdf"], [], existing)
    duplicate = page.complete_quick_file_upload(
        ["/tmp/病历.pdf"], ["file-1"], existing
    )

    assert failed[2] == existing
    assert duplicate[2] == existing


def test_mindmap_toolbar_keeps_only_zoom_controls() -> None:
    chat_source = (
        Path(__file__).parents[1] / "ktem" / "pages" / "chat" / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "toolbarItems.slice(2).forEach((item) => item.remove())" in chat_source
    assert 'const toolbarLabels = ["放大", "缩小"]' in chat_source


def test_evidence_panel_is_opt_in_and_toggleable() -> None:
    panel_update, visible, button_update = toggle_info_panel(False)

    assert visible is True
    assert panel_update["visible"] is True
    assert button_update["variant"] == "secondary"

    panel_update, visible, button_update = toggle_info_panel(True)

    assert visible is False
    assert panel_update["visible"] is False
    assert button_update["variant"] == "secondary"


def test_evidence_opens_info_panel_without_changing_button_style() -> None:
    panel_update, visible, button_update = open_info_panel_for_evidence(
        '<details class="evidence"><div class="evidence-content">参考资料</div></details>',
        False,
    )

    assert panel_update["visible"] is True
    assert visible is True
    assert button_update["variant"] == "secondary"


def test_empty_evidence_does_not_open_info_panel() -> None:
    panel_update, visible, button_update = open_info_panel_for_evidence("", False)

    assert "visible" not in panel_update
    assert visible is False
    assert button_update["variant"] == "secondary"


def test_mindmap_alone_does_not_open_info_panel() -> None:
    panel_update, visible, _ = open_info_panel_for_evidence(
        '<details class="evidence"><div class="markmap">导图</div></details>', False
    )

    assert "visible" not in panel_update
    assert visible is False


def test_edit_message_appends_follow_up_without_rewriting_history() -> None:
    page = object.__new__(ChatPage)
    chat_history = [
        ("患者有哪些用药禁忌？", "原回答"),
        ("第二个问题", "第二个回答"),
    ]

    result = page.edit_message(
        '{"index": 0, "text": "患者服用华法林有哪些禁忌？"}',
        chat_history,
        "user-1",
        {},
        "conversation-1",
        "测试会话",
        [],
        ["证据一", "证据二"],
        [{"plot": 1}, {"plot": 2}],
        None,
    )

    assert result[0] == {}
    assert result[1] == chat_history + [("患者服用华法林有哪些禁忌？", None)]
    assert result[-2:] == [
        ["证据一", "证据二"],
        [{"plot": 1}, {"plot": 2}],
    ]


def test_asr_display_turns_are_excluded_from_llm_history() -> None:
    page = object.__new__(ChatPage)
    chat_history = [
        (None, '<section data-ktem-message-type="asr">转写内容</section>'),
        ("医生的问题", "模型回答"),
    ]

    assert page._reasoning_history(chat_history) == [("医生的问题", "模型回答")]


def test_hospital_settings_terms_keep_internal_values() -> None:
    assert translate_ui_text("LLM for relevant scoring") == "相关性评分语言模型"
    assert translate_ui_text("ChatOpenAI") == "兼容聊天接口"
    assert translate_ui_text("FileIndex") == "文件索引"
    assert translate_choices(["simple", "hybrid"]) == [
        ("常规问答", "simple"),
        ("混合检索", "hybrid"),
    ]


def test_generated_chat_actions_and_notifications_are_localized() -> None:
    main_js = (
        Path(__file__).parents[1] / "ktem" / "assets" / "js" / "main.js"
    ).read_text(encoding="utf-8")

    for english, chinese in (
        ('["Warning", "警告"]', "警告"),
        ('["Error", "错误"]', "错误"),
        ('label = "复制回答"', "复制回答"),
        ('label = "不满意"', "不满意"),
        ('label = "满意"', "满意"),
    ):
        assert english in main_js, chinese


def test_default_hospital_prompts_are_chinese() -> None:
    simple_settings = FullQAPipeline.get_user_settings()
    complex_settings = FullDecomposeQAPipeline.get_user_settings()

    assert simple_settings["system_prompt"]["value"].startswith("你是一个")
    assert "如果上下文不足" in simple_settings["qa_prompt"]["value"]
    assert "最多拆分为 3 个" in complex_settings["decompose_prompt"]["value"]
