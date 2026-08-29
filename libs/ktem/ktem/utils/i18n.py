"""Small UI text catalog for the Chinese intranet deployment."""

from __future__ import annotations

from typing import Any

ZH_CN_TEXT = {
    "Reasoning options": "推理方法",
    "Language": "回答语言",
    "Max context length (LLM)": "最大上下文长度（LLM）",
    "File loader": "文件解析方式",
    "Retrieval options": "检索方式",
    "Search top-k": "初始召回数量",
    "Reranking top-k": "重排序保留数量",
    "Reranker": "重排序模型",
    "LLM": "语言模型",
    "Highlight citation": "引用高亮",
    "Use LLM reranking": "使用 LLM 相关性评分",
    "Use query decomposition": "启用问题分解",
    "Use mind map": "生成思维导图",
    "Simple QA": "常规问答",
    "Decompose QA": "分解式问答",
    "English": "英语",
    "Japanese": "日语",
    "Chinese": "中文",
    "default": "默认",
    "select": "选择指定文件",
    "all": "全部",
    "text": "文本",
    "table": "表格",
    "image": "图片",
    "thumbnail": "缩略图",
}


def translate_ui_text(value: str) -> str:
    """Translate a known UI string and preserve unknown extension text."""

    return ZH_CN_TEXT.get(value, value)


def translate_choices(choices: Any) -> Any:
    """Translate Gradio choice labels without changing their stored values."""

    if not isinstance(choices, (list, tuple)):
        return choices

    translated = []
    for choice in choices:
        if isinstance(choice, (list, tuple)) and len(choice) == 2:
            translated.append((translate_ui_text(str(choice[0])), choice[1]))
        elif isinstance(choice, str):
            translated.append((translate_ui_text(choice), choice))
        else:
            translated.append(choice)
    return translated
