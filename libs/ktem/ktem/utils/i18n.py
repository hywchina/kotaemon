"""Small UI text catalog for the Chinese intranet deployment."""

from __future__ import annotations

from typing import Any

ZH_CN_TEXT = {
    "Reasoning options": "推理方法",
    "Language": "回答语言",
    "Max context length (LLM)": "最大上下文长度（LLM）",
    "File loader": "文件解析方式",
    "Default (open-source)": "默认解析器（开源）",
    "Retrieval options": "检索方式",
    "LLM for relevant scoring": "相关性评分语言模型",
    "Number of document chunks to retrieve": "召回文档片段数量",
    "Retrieval mode": "检索模式",
    "Prioritize table": "优先检索表格",
    "Use MMR": "启用结果多样性优化（MMR）",
    "Use reranking": "启用重排序",
    "Use LLM relevant scoring": "启用语言模型相关性评分",
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
    "Complex QA": "复杂问题分解",
    "Language model": "语言模型",
    "Citation style": "引用样式",
    "Create Mindmap": "生成思维导图",
    "System Prompt": "系统提示词",
    "QA Prompt": "问答提示词",
    "QA Prompt (contains {context}, {question}, {lang})": (
        "问答提示词（包含 {context}、{question}、{lang}）"
    ),
    "Number of interactions to include": "携带的最近对话轮数",
    "Maximum message length for context rewriting": "触发上下文改写的最大消息长度",
    "Decompose Prompt": "问题分解提示词",
    "English": "英语",
    "Japanese": "日语",
    "Chinese": "中文",
    "default": "默认",
    "simple": "常规问答",
    "complex": "复杂问题分解",
    "vector": "向量检索",
    "hybrid": "混合检索",
    "FileIndex": "文件索引",
    "ChatOpenAI": "兼容聊天接口",
    "OpenAIEmbeddings": "兼容嵌入接口",
    "GeekAIEmbeddings": "GeekAI 嵌入接口",
    "GeekAIReranking": "GeekAI 重排序接口",
    "TeiFastReranking": "本地 TEI 重排序接口",
    "True": "是",
    "False": "否",
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
