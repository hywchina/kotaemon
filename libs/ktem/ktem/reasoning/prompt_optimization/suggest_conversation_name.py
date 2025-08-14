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
        "你是一位擅长为医疗诊断对话取简洁、准确、易记标题的专家。"
        "根据上面的对话内容（医生提供患者病例，AI提供辅助诊断建议），"
        "请生成一个合适的对话标题（最多 10 个词），"
        "标题需准确反映病例的核心信息或诊断主题，避免使用敏感信息（如患者姓名）。"
        "用 {lang} 回答。只输出标题，不要添加任何额外说明。"
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
