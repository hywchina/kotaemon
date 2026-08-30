from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import pandas as pd
from ktem.index.file.ui import FileIndexPage
from ktem.pages.chat import ChatPage, open_info_panel_for_evidence, toggle_info_panel
from ktem.pages.chat import chat_panel as chat_panel_module
from ktem.reasoning.simple import FullDecomposeQAPipeline, FullQAPipeline
from ktem.utils.i18n import translate_choices, translate_ui_text


def _page_without_ui() -> FileIndexPage:
    page = object.__new__(FileIndexPage)
    page.selected_panel_false = "未选择文件"
    page.selected_panel_true = "已选文件：{name}"
    return page


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
    assert panel.pending_multimodal_input.value == {"query": "", "image_paths": []}
    assert panel.chatbot.placeholder.startswith("开始一次辅助诊断问答")
    assert not hasattr(panel, "regen_btn")


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
