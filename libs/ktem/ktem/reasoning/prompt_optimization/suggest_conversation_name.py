import logging

from ktem.llms.manager import llms

from kotaemon.base import AIMessage, BaseComponent, Document, HumanMessage, Node
from kotaemon.llms import ChatLLM, PromptTemplate

logger = logging.getLogger(__name__)


class SuggestConvNamePipeline(BaseComponent):
    """Suggest a good conversation name based on the chat history."""

    llm: ChatLLM = Node(default_callback=lambda _: llms.get_default())
    # SUGGEST_NAME_PROMPT_TEMPLATE = (
    #     "You are an expert at suggesting good and memorable conversation name. "
    #     "Based on the chat history above, "
    #     "suggest a good conversation name (max 10 words). "
    #     "Give answer in {lang}. Just output the conversation "
    #     "name without any extra."
    # )
    SUGGEST_NAME_PROMPT_TEMPLATE = (
        "你是一位擅长为对话取好且令人印象深刻名称的专家。"
        "基于以上的聊天记录，"
        "请建议一个合适的对话名称（最多 10 个词）。"
        "请使用 {lang} 作答。"
        "只输出对话名称本身，不要添加任何额外内容。"
    )
    prompt_template: str = SUGGEST_NAME_PROMPT_TEMPLATE
    lang: str = "Chinese"

    def run(self, chat_history: list[tuple[str, str]]) -> Document:  # type: ignore
        prompt_template = PromptTemplate(self.prompt_template)
        prompt = prompt_template.populate(lang=self.lang)

        messages = []
        for human, ai in chat_history:
            messages.append(HumanMessage(content=human))
            messages.append(AIMessage(content=ai))

        messages.append(HumanMessage(content=prompt))

        return self.llm(messages)
