import asyncio
import base64
import json
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Optional

import gradio as gr
from decouple import config
from ktem.app import BasePage
from ktem.components import reasonings
from ktem.db.models import Conversation, engine
from ktem.index.file.ui import File
from ktem.reasoning.prompt_optimization.mindmap import MINDMAP_HTML_EXPORT_TEMPLATE
from ktem.reasoning.prompt_optimization.suggest_conversation_name import (
    SuggestConvNamePipeline,
)
from ktem.reasoning.prompt_optimization.suggest_followup_chat import (
    SuggestFollowupQuesPipeline,
)
from plotly.io import from_json
from PIL import Image, UnidentifiedImageError
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings
from theflow.utils.modules import import_dotted_string

from kotaemon.base import Document
from kotaemon.indices.ingests.files import KH_DEFAULT_FILE_EXTRACTORS
from kotaemon.indices.qa.utils import strip_think_tag

from ...utils import (
    SUPPORTED_LANGUAGE_MAP,
    format_mentions_for_display,
    get_mentions_regex,
    get_urls,
    prepare_llm_query,
)
from ...utils.commands import WEB_SEARCH_COMMAND
from ...utils.hf_papers import get_recommended_papers
from ...utils.notifications import notify_exception
from ...utils.rate_limit import check_rate_limit
from .chat_panel import ChatPanel
from .chat_suggestion import ChatSuggestion
from .common import STATE
from .control import ConversationControl
from .demo_hint import HintPage
from .paper_list import PaperListPage
from .report import ReportIssue

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)
KH_WEB_SEARCH_BACKEND = getattr(flowsettings, "KH_WEB_SEARCH_BACKEND", None)
KH_ENABLE_URL_UPLOAD = getattr(flowsettings, "KH_ENABLE_URL_UPLOAD", False)
KH_ENABLE_ASR = getattr(flowsettings, "KH_ENABLE_ASR", True)
KH_CHAT_IMAGE_MAX_FILES = max(
    1, int(getattr(flowsettings, "KH_CHAT_IMAGE_MAX_FILES", 4))
)
KH_CHAT_IMAGE_MAX_SIZE_MB = max(
    1, int(getattr(flowsettings, "KH_CHAT_IMAGE_MAX_SIZE_MB", 8))
)
KH_CHAT_IMAGE_MAX_PIXELS = max(
    1, int(getattr(flowsettings, "KH_CHAT_IMAGE_MAX_PIXELS", 25_000_000))
)
logger = logging.getLogger(__name__)
WebSearch = None
if KH_WEB_SEARCH_BACKEND:
    try:
        WebSearch = import_dotted_string(KH_WEB_SEARCH_BACKEND, safe=False)
    except (ImportError, AttributeError):
        logger.exception("Unable to load web search backend: %s", KH_WEB_SEARCH_BACKEND)

REASONING_LIMITS = 2 if KH_DEMO_MODE else 10
DEFAULT_SETTING = "(default)"
INFO_PANEL_SCALES = {True: 8, False: 4}
DEFAULT_QUESTION = "请总结这份文档。" if not KH_DEMO_MODE else "请总结这篇论文。"
DEFAULT_IMAGE_QUESTION = "请分析所附图片，并说明其中的关键信息。"
CHAT_IMAGE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


def validate_chat_images(file_paths) -> tuple[list[str], list[str]]:
    """Validate browser-uploaded images before they can reach a model API."""

    paths = [Path(path) for path in (file_paths or [])]
    if len(paths) > KH_CHAT_IMAGE_MAX_FILES:
        raise gr.Error(f"每次最多添加 {KH_CHAT_IMAGE_MAX_FILES} 张图片。")

    validated_paths = []
    display_names = []
    max_bytes = KH_CHAT_IMAGE_MAX_SIZE_MB * 1024 * 1024
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise gr.Error("图片文件不存在或已失效，请重新添加。")
        if path.stat().st_size > max_bytes:
            raise gr.Error(
                f"图片“{path.name}”超过 {KH_CHAT_IMAGE_MAX_SIZE_MB} MB 限制。"
            )
        try:
            with Image.open(path) as image:
                image_format = (image.format or "").upper()
                width, height = image.size
                if image_format not in CHAT_IMAGE_MIME_TYPES:
                    raise gr.Error("仅支持 PNG、JPEG 和 WebP 图片。")
                if width * height > KH_CHAT_IMAGE_MAX_PIXELS:
                    raise gr.Error(f"图片“{path.name}”像素过大，请压缩后重新添加。")
                image.verify()
        except gr.Error:
            raise
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
            raise gr.Error(f"无法读取图片“{path.name}”，请检查文件是否损坏。") from exc

        validated_paths.append(str(path))
        display_names.append(re.sub(r"[\x00-\x1f`]", "_", path.name))

    return validated_paths, display_names


def encode_chat_images(file_paths) -> list[str]:
    """Encode validated images as OpenAI-compatible data URLs."""

    paths, _ = validate_chat_images(file_paths)
    encoded_images = []
    for raw_path in paths:
        path = Path(raw_path)
        with Image.open(path) as image:
            mime_type = CHAT_IMAGE_MIME_TYPES[image.format.upper()]
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        encoded_images.append(f"data:{mime_type};base64,{encoded}")
    return encoded_images


chat_input_focus_js = """
function() {
    let chatInput = document.querySelector("#chat-input textarea");
    chatInput.focus();
}
"""

quick_urls_submit_js = """
function() {
    let urlInput = document.querySelector("#quick-url-demo textarea");
    console.log("URL input:", urlInput);
    urlInput.dispatchEvent(new KeyboardEvent('keypress', {'key': 'Enter'}));
}
"""

recommended_papers_js = """
function() {
    // Get all links and attach click event
    var links = document.querySelectorAll("#related-papers a");

    function submitPaper(event) {
        event.preventDefault();
        var target = event.currentTarget;
        var url = target.getAttribute("href");
        console.log("URL:", url);

        let newChatButton = document.querySelector("#new-conv-button");
        newChatButton.click();

        setTimeout(() => {
            let urlInput = document.querySelector("#quick-url-demo textarea");
            // Fill the URL input
            urlInput.value = url;
            urlInput.dispatchEvent(new Event("input", { bubbles: true }));
            urlInput.dispatchEvent(new KeyboardEvent('keypress', {'key': 'Enter'}));
            }, 500
        );
    }

    for (var i = 0; i < links.length; i++) {
        links[i].onclick = submitPaper;
    }
}
"""

clear_bot_message_selection_js = """
function() {
    var bot_messages = document.querySelectorAll(
        "div#main-chat-bot div.message-row.bot-row"
    );
    bot_messages.forEach(message => {
        message.classList.remove("text_selection");
    });
}
"""

pdfview_js = """
function() {
    setTimeout(fullTextSearch(), 100);

    // Get all links and attach click event
    var links = document.getElementsByClassName("pdf-link");
    for (var i = 0; i < links.length; i++) {
        links[i].onclick = openModal;
    }

    // Get all citation links and attach click event
    var links = document.querySelectorAll("a.citation");
    for (var i = 0; i < links.length; i++) {
        links[i].onclick = scrollToCitation;
    }

    var markmap_div = document.querySelector("div.markmap");
    var mindmap_el_script = document.querySelector('div.markmap script');

    if (mindmap_el_script) {
        markmap_div_html = markmap_div.outerHTML;
    }

    // render the mindmap if the script tag is present
    if (mindmap_el_script) {
        markmap.autoLoader.renderAll();
    }

    setTimeout(() => {
        var mindmap_el = document.querySelector('svg.markmap');

        var text_nodes = document.querySelectorAll("svg.markmap div");
        for (var i = 0; i < text_nodes.length; i++) {
            text_nodes[i].onclick = fillChatInput;
        }

        if (mindmap_el) {
            function on_svg_export(event) {
                html = "{html_template}";
                var renderedMarkmap = document.querySelector("div.markmap");
                html = html.replace(
                    "{markmap_div}",
                    renderedMarkmap ? renderedMarkmap.outerHTML : markmap_div_html
                );
                spawnDocument(html, {window: "width=1000,height=1000"});
            }

            var link = document.getElementById("mindmap-toggle");
            if (link) {
                link.onclick = function(event) {
                    event.preventDefault(); // Prevent the default link behavior
                    var div = document.querySelector("div.markmap");
                    if (div) {
                        var currentHeight = div.style.height;
                        if (currentHeight === '400px' || (currentHeight === '')) {
                            div.style.height = '650px';
                        } else {
                            div.style.height = '400px'
                        }
                    }
                };
            }

            if (markmap_div_html) {
                var link = document.getElementById("mindmap-export");
                if (link) {
                    link.addEventListener('click', on_svg_export);
                }
            }
        }
    }, 250);

    return [links.length]
}
""".replace(
    "{html_template}",
    MINDMAP_HTML_EXPORT_TEMPLATE.replace("\n", "").replace('"', '\\"'),
)

fetch_api_key_js = """
function(_, __) {
    api_key = getStorage('google_api_key', '');
    console.log('session API key:', api_key);
    return [api_key, _];
}
"""


class ChatPage(BasePage):
    def __init__(self, app):
        self._app = app
        self._indices_input = []

        self.on_building_ui()

        self._preview_links = gr.State(value=None)
        self._reasoning_type = gr.State(value=None)
        self._conversation_renamed = gr.State(value=False)
        self._use_suggestion = gr.State(
            value=getattr(flowsettings, "KH_FEATURE_CHAT_SUGGESTION", False)
        )
        self._info_panel_expanded = gr.State(value=True)
        self._command_state = gr.State(value=None)
        self._user_api_key = gr.Text(value="", visible=False)

    def on_building_ui(self):
        with gr.Row():
            self.state_chat = gr.State(STATE)
            self.state_retrieval_history = gr.State([])
            self.state_plot_history = gr.State([])
            self.state_plot_panel = gr.State(None)
            self.first_selector_choices = gr.State(None)

            with gr.Column(scale=1, elem_id="conv-settings-panel") as self.conv_column:
                self.chat_control = ConversationControl(self._app)

                for index_id, index in enumerate(self._app.index_manager.indices):
                    index.selector = None
                    index_ui = index.get_selector_component_ui()
                    if not index_ui:
                        # the index doesn't have a selector UI component
                        continue

                    index_ui.unrender()  # need to rerender later within Accordion
                    is_first_index = index_id == 0
                    index_name = index.name

                    if KH_DEMO_MODE and is_first_index:
                        index_name = "从论文库选择"

                    with gr.Accordion(
                        label=index_name,
                        open=is_first_index,
                        elem_id=f"index-{index_id}",
                    ):
                        index_ui.render()
                        gr_index = index_ui.as_gradio_component()

                        # get the file selector choices for the first index
                        if index_id == 0:
                            self.first_selector_choices = index_ui.selector_choices
                            self.first_indexing_url_fn = None

                        if gr_index:
                            if isinstance(gr_index, list):
                                index.selector = tuple(
                                    range(
                                        len(self._indices_input),
                                        len(self._indices_input) + len(gr_index),
                                    )
                                )
                                index.default_selector = index_ui.default()
                                self._indices_input.extend(gr_index)
                            else:
                                index.selector = len(self._indices_input)
                                index.default_selector = index_ui.default()
                                self._indices_input.append(gr_index)
                        setattr(self, f"_index_{index.id}", index_ui)

                self.chat_suggestion = ChatSuggestion(self._app)

                if len(self._app.index_manager.indices) > 0:
                    quick_upload_label = (
                        "快速上传" if not KH_DEMO_MODE else "输入新论文 URL"
                    )

                    with gr.Accordion(
                        label=quick_upload_label
                    ) as self.quick_upload_accordion:
                        self.quick_file_upload_status = gr.Markdown()
                        if not KH_DEMO_MODE:
                            self.quick_file_upload = File(
                                file_types=list(KH_DEFAULT_FILE_EXTRACTORS.keys()),
                                file_count="multiple",
                                container=True,
                                show_label=False,
                                elem_id="quick-file",
                            )
                        self.quick_urls = gr.Textbox(
                            placeholder=(
                                "粘贴 URL"
                                if not KH_DEMO_MODE
                                else "Paste Arxiv URLs\n(https://arxiv.org/abs/xxx)"
                            ),
                            lines=1,
                            container=False,
                            show_label=False,
                            visible=KH_DEMO_MODE or KH_ENABLE_URL_UPLOAD,
                            elem_id=(
                                "quick-url" if not KH_DEMO_MODE else "quick-url-demo"
                            ),
                        )

                if not KH_DEMO_MODE:
                    self.report_issue = ReportIssue(self._app)
                else:
                    with gr.Accordion(label="相关论文", open=False):
                        self.related_papers = gr.Markdown(elem_id="related-papers")

                    self.hint_page = HintPage(self._app)

            with gr.Column(scale=6, elem_id="chat-area"):
                if KH_DEMO_MODE:
                    self.paper_list = PaperListPage(self._app)

                self.chat_panel = ChatPanel(self._app)

                with gr.Accordion(
                    label="会话设置",
                    elem_id="chat-settings-expand",
                    open=False,
                    visible=not KH_DEMO_MODE,
                ) as self.chat_settings:
                    with gr.Row(elem_id="quick-setting-labels"):
                        gr.HTML("推理方法")
                        gr.HTML("模型", visible=not KH_DEMO_MODE and not KH_SSO_ENABLED)
                        gr.HTML("语言")

                    with gr.Row():
                        reasoning_setting = (
                            self._app.default_settings.reasoning.settings["use"]
                        )
                        model_setting = self._app.default_settings.reasoning.options[
                            "simple"
                        ].settings["llm"]
                        language_setting = (
                            self._app.default_settings.reasoning.settings["lang"]
                        )
                        citation_setting = self._app.default_settings.reasoning.options[
                            "simple"
                        ].settings["highlight_citation"]

                        self.reasoning_type = gr.Dropdown(
                            choices=reasoning_setting.choices[:REASONING_LIMITS],
                            value=reasoning_setting.value,
                            container=False,
                            show_label=False,
                        )
                        self.model_type = gr.Dropdown(
                            choices=model_setting.choices,
                            value=model_setting.value,
                            container=False,
                            show_label=False,
                            visible=not KH_DEMO_MODE and not KH_SSO_ENABLED,
                        )
                        self.language = gr.Dropdown(
                            choices=language_setting.choices,
                            value=language_setting.value,
                            container=False,
                            show_label=False,
                        )

                        self.citation = gr.Dropdown(
                            choices=citation_setting.choices,
                            value=citation_setting.value,
                            container=False,
                            show_label=False,
                            interactive=True,
                            elem_id="citation-dropdown",
                        )

                        if not config("USE_LOW_LLM_REQUESTS", default=False, cast=bool):
                            self.use_mindmap = gr.State(value=True)
                            self.use_mindmap_check = gr.Checkbox(
                                label="思维导图（开启）",
                                container=False,
                                elem_id="use-mindmap-checkbox",
                                value=True,
                            )
                        else:
                            self.use_mindmap = gr.State(value=False)
                            self.use_mindmap_check = gr.Checkbox(
                                label="思维导图（关闭）",
                                container=False,
                                elem_id="use-mindmap-checkbox",
                                value=False,
                            )

            with gr.Column(
                scale=INFO_PANEL_SCALES[False], elem_id="chat-info-panel"
            ) as self.info_column:
                with gr.Accordion(label="信息面板", open=True, elem_id="info-expand"):
                    self.modal = gr.HTML("<div id='pdf-modal'></div>")
                    self.plot_panel = gr.Plot(visible=False)
                    self.info_panel = gr.HTML(elem_id="html-info-panel")

        self.followup_questions = self.chat_suggestion.examples
        self.followup_questions_ui = self.chat_suggestion.accordion

    def _json_to_plot(self, json_dict: dict | None):
        if json_dict:
            plot = from_json(json_dict)
            plot = gr.update(visible=True, value=plot)
        else:
            plot = gr.update(visible=False)
        return plot

    def on_register_events(self):
        # first index paper recommendation
        if KH_DEMO_MODE and len(self._indices_input) > 0:
            self._indices_input[1].change(
                self.get_recommendations,
                inputs=[self.first_selector_choices, self._indices_input[1]],
                outputs=[self.related_papers],
            ).then(
                fn=None,
                inputs=None,
                outputs=None,
                js=recommended_papers_js,
            )

        submit_inputs = [
            self.chat_panel.text_input,
            self.chat_panel.chatbot,
            self._app.user_id,
            self._app.settings_state,
            self.chat_control.conversation_id,
            self.chat_control.conversation_rn,
            self.first_selector_choices,
        ]
        submit_outputs = [
            self.chat_panel.text_input,
            self.chat_panel.chatbot,
            self.chat_panel.pending_multimodal_input,
            self.chat_control.conversation_id,
            self.chat_control.conversation,
            self.chat_control.conversation_rn,
            # file selector from the first index
            self._indices_input[0],
            self._indices_input[1],
            self._command_state,
        ]

        submit_event = gr.on(
            triggers=[
                self.chat_panel.text_input.submit,
                self.chat_panel.submit_btn.click,
            ],
            fn=self.submit_msg,
            inputs=submit_inputs,
            outputs=submit_outputs,
            concurrency_limit=20,
            show_progress="hidden",
        )

        edit_event = self.chat_panel.edit_message_button.click(
            fn=self.edit_message,
            inputs=[self.chat_panel.message_action_payload]
            + submit_inputs[1:]
            + [self.state_retrieval_history, self.state_plot_history],
            outputs=submit_outputs
            + [self.state_retrieval_history, self.state_plot_history],
            concurrency_limit=20,
            show_progress="hidden",
        )
        onSuggestChatEvent = {
            "fn": self.suggest_chat_conv,
            "inputs": [
                self._app.settings_state,
                self.language,
                self.chat_panel.chatbot,
                self._use_suggestion,
            ],
            "outputs": [
                self.followup_questions_ui,
                self.followup_questions,
            ],
            "show_progress": "hidden",
        }

        def register_chat_pipeline(start_event):
            chat_event = (
                start_event.success(
                    fn=self.chat_fn,
                    inputs=[
                        self.chat_control.conversation_id,
                        self.chat_panel.chatbot,
                        self.chat_panel.pending_multimodal_input,
                        self._app.settings_state,
                        self.reasoning_type,
                        self.model_type,
                        self.use_mindmap,
                        self.citation,
                        self.language,
                        self.state_chat,
                        self._command_state,
                        self._app.user_id,
                    ]
                    + self._indices_input,
                    outputs=[
                        self.chat_panel.chatbot,
                        self.info_panel,
                        self.plot_panel,
                        self.state_plot_panel,
                        self.state_chat,
                    ],
                    concurrency_limit=20,
                    show_progress="minimal",
                )
                .then(
                    fn=lambda: True,
                    inputs=None,
                    outputs=[self._preview_links],
                    js=pdfview_js,
                )
                .success(
                    fn=self.check_and_suggest_name_conv,
                    inputs=self.chat_panel.chatbot,
                    outputs=[
                        self.chat_control.conversation_rn,
                        self._conversation_renamed,
                    ],
                )
                .success(
                    self.chat_control.rename_conv,
                    inputs=[
                        self.chat_control.conversation_id,
                        self.chat_control.conversation_rn,
                        self._conversation_renamed,
                        self._app.user_id,
                    ],
                    outputs=[
                        self.chat_control.conversation,
                        self.chat_control.conversation,
                        self.chat_control.conversation_rn,
                    ],
                    show_progress="hidden",
                )
            )

            # chat suggestion toggle
            chat_event = chat_event.success(**onSuggestChatEvent)

            # final data persist
            if not KH_DEMO_MODE:
                chat_event = chat_event.then(
                    fn=self.persist_data_source,
                    inputs=[
                        self.chat_control.conversation_id,
                        self._app.user_id,
                        self.info_panel,
                        self.state_plot_panel,
                        self.state_retrieval_history,
                        self.state_plot_history,
                        self.chat_panel.chatbot,
                        self.state_chat,
                    ]
                    + self._indices_input,
                    outputs=[
                        self.state_retrieval_history,
                        self.state_plot_history,
                    ],
                    concurrency_limit=20,
                )

            return chat_event

        register_chat_pipeline(submit_event)
        register_chat_pipeline(edit_event)

        self.chat_panel.delete_message_button.click(
            fn=self.delete_message,
            inputs=[
                self.chat_panel.message_action_payload,
                self.chat_panel.chatbot,
                self.chat_control.conversation_id,
                self._app.user_id,
                self.state_retrieval_history,
                self.state_plot_history,
            ],
            outputs=[
                self.chat_panel.chatbot,
                self.state_retrieval_history,
                self.state_plot_history,
                self.info_panel,
                self.state_plot_panel,
            ],
            show_progress="hidden",
        ).then(
            fn=self._json_to_plot,
            inputs=self.state_plot_panel,
            outputs=self.plot_panel,
        )

        if KH_ENABLE_ASR:
            begin_asr_event = self.chat_panel.asr_start_button.click(
                fn=self.begin_asr_session,
                inputs=[
                    self.chat_panel.chatbot,
                    self._app.user_id,
                    self.chat_control.conversation_id,
                    self.chat_control.conversation_rn,
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                outputs=[
                    self.chat_panel.asr_segments,
                    self.chat_panel.chatbot,
                    self.chat_panel.asr_message_index,
                    self.chat_panel.asr_start_button,
                    self.chat_panel.asr_stop_button,
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                show_progress="hidden",
                queue=False,
            )
            stream_asr_event = begin_asr_event.then(
                fn=self.chat_panel.stream_transcription,
                inputs=[
                    self.chat_panel.asr_segments,
                    self.chat_panel.chatbot,
                    self.chat_panel.asr_message_index,
                ],
                outputs=[
                    self.chat_panel.asr_segments,
                    self.chat_panel.chatbot,
                    self.chat_panel.asr_message_index,
                    self.chat_panel.asr_start_button,
                    self.chat_panel.asr_stop_button,
                ],
                show_progress="hidden",
                concurrency_limit=1,
            )
            stream_asr_event.success(
                fn=self.persist_asr_transcript,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self.chat_panel.chatbot,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.state_chat,
                ]
                + self._indices_input,
                outputs=[
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                show_progress="hidden",
            )
            self.chat_panel.asr_stop_button.click(
                fn=self.chat_panel.stop_transcription,
                inputs=[
                    self.chat_panel.asr_segments,
                    self.chat_panel.chatbot,
                    self.chat_panel.asr_message_index,
                ],
                outputs=[
                    self.chat_panel.chatbot,
                    self.chat_panel.asr_message_index,
                    self.chat_panel.asr_start_button,
                    self.chat_panel.asr_stop_button,
                ],
                cancels=[stream_asr_event],
                show_progress="hidden",
                queue=False,
            ).then(
                fn=self.persist_asr_transcript,
                inputs=[
                    self.chat_control.conversation_id,
                    self._app.user_id,
                    self.chat_panel.chatbot,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.state_chat,
                ]
                + self._indices_input,
                outputs=[
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                show_progress="hidden",
            )

        self.chat_control.btn_info_expand.click(
            fn=lambda is_expanded: (
                gr.update(scale=INFO_PANEL_SCALES[is_expanded]),
                not is_expanded,
            ),
            inputs=self._info_panel_expanded,
            outputs=[self.info_column, self._info_panel_expanded],
        )
        self.chat_control.btn_chat_expand.click(
            fn=None, inputs=None, js="function() {toggleChatColumn();}"
        )

        if KH_DEMO_MODE:
            self.chat_control.btn_demo_logout.click(
                fn=None,
                js=self.chat_control.logout_js,
            )
            self.chat_control.btn_new.click(
                fn=lambda: self.chat_control.select_conv("", None),
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
            ).then(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.paper_list.accordion, self.chat_settings],
            ).then(
                fn=None,
                inputs=None,
                js=chat_input_focus_js,
            )

        if not KH_DEMO_MODE:
            self.chat_control.btn_new.click(
                self.chat_control.new_conv,
                inputs=self._app.user_id,
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                ],
                show_progress="hidden",
            ).then(
                self.chat_control.select_conv,
                inputs=[self.chat_control.conversation, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
                show_progress="hidden",
            ).then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            ).then(
                fn=None,
                inputs=None,
                js=chat_input_focus_js,
            )

            self.chat_control.btn_del.click(
                lambda id: self.toggle_delete(id),
                inputs=[self.chat_control.conversation_id],
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            self.chat_control.btn_del_conf.click(
                self.chat_control.delete_conv,
                inputs=[self.chat_control.conversation_id, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                ],
                show_progress="hidden",
            ).then(
                self.chat_control.select_conv,
                inputs=[self.chat_control.conversation, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
                show_progress="hidden",
            ).then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            ).then(
                lambda: self.toggle_delete(""),
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            self.chat_control.btn_del_cnl.click(
                lambda: self.toggle_delete(""),
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
            self.chat_control.btn_conversation_rn.click(
                lambda: gr.update(visible=True),
                outputs=[
                    self.chat_control.conversation_rn,
                ],
            )
            self.chat_control.conversation_rn.submit(
                self.chat_control.rename_conv,
                inputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation_rn,
                    gr.State(value=True),
                    self._app.user_id,
                ],
                outputs=[
                    self.chat_control.conversation,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                ],
                show_progress="hidden",
            )

        onConvSelect = (
            self.chat_control.conversation.select(
                self.chat_control.select_conv,
                inputs=[self.chat_control.conversation, self._app.user_id],
                outputs=[
                    self.chat_control.conversation_id,
                    self.chat_control.conversation,
                    self.chat_control.conversation_rn,
                    self.chat_panel.chatbot,
                    self.followup_questions,
                    self.info_panel,
                    self.state_plot_panel,
                    self.state_retrieval_history,
                    self.state_plot_history,
                    self.chat_control.cb_is_public,
                    self.state_chat,
                ]
                + self._indices_input,
                show_progress="hidden",
            )
            .then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            )
            .then(
                lambda: self.toggle_delete(""),
                outputs=[
                    self.chat_control._new_delete,
                    self.chat_control._delete_confirm,
                ],
            )
        )

        if KH_DEMO_MODE:
            onConvSelect = onConvSelect.then(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.paper_list.accordion, self.chat_settings],
            )

        onConvSelect = (
            onConvSelect.then(
                fn=lambda: True,
                js=clear_bot_message_selection_js,
            )
            .then(
                fn=lambda: True,
                inputs=None,
                outputs=[self._preview_links],
                js=pdfview_js,
            )
            .then(fn=None, inputs=None, outputs=None, js=chat_input_focus_js)
        )

        if not KH_DEMO_MODE:
            # evidence display on message selection
            self.chat_panel.chatbot.select(
                self.message_selected,
                inputs=[
                    self.state_retrieval_history,
                    self.state_plot_history,
                ],
                outputs=[
                    self.info_panel,
                    self.state_plot_panel,
                ],
            ).then(
                fn=self._json_to_plot,
                inputs=self.state_plot_panel,
                outputs=self.plot_panel,
            ).then(
                fn=lambda: True,
                inputs=None,
                outputs=[self._preview_links],
                js=pdfview_js,
            )

        self.chat_control.cb_is_public.change(
            self.on_set_public_conversation,
            inputs=[self.chat_control.cb_is_public, self.chat_control.conversation],
            outputs=None,
            show_progress="hidden",
        )

        if not KH_DEMO_MODE:
            # user feedback events
            self.chat_panel.chatbot.like(
                fn=self.is_liked,
                inputs=[self.chat_control.conversation_id],
                outputs=None,
            )
            self.report_issue.report_btn.click(
                self.report_issue.report,
                inputs=[
                    self.report_issue.correctness,
                    self.report_issue.issues,
                    self.report_issue.more_detail,
                    self.chat_control.conversation_id,
                    self.chat_panel.chatbot,
                    self._app.settings_state,
                    self._app.user_id,
                    self.info_panel,
                    self.state_chat,
                ]
                + self._indices_input,
                outputs=None,
            )

        self.reasoning_type.change(
            self.reasoning_changed,
            inputs=[self.reasoning_type],
            outputs=[self._reasoning_type],
        )
        self.use_mindmap_check.change(
            lambda x: (
                x,
                gr.update(label="思维导图（" + ("开启" if x else "关闭") + "）"),
            ),
            inputs=[self.use_mindmap_check],
            outputs=[self.use_mindmap, self.use_mindmap_check],
            show_progress="hidden",
        )

        def toggle_chat_suggestion(current_state):
            return current_state, gr.update(visible=current_state)

        def raise_error_on_state(state):
            if not state:
                raise ValueError("Chat suggestion disabled")

        self.chat_control.cb_suggest_chat.change(
            fn=toggle_chat_suggestion,
            inputs=[self.chat_control.cb_suggest_chat],
            outputs=[self._use_suggestion, self.followup_questions_ui],
            show_progress="hidden",
        ).then(
            fn=raise_error_on_state,
            inputs=[self._use_suggestion],
            show_progress="hidden",
        ).success(
            **onSuggestChatEvent
        )
        self.chat_control.conversation_id.change(
            lambda: gr.update(visible=False),
            outputs=self.plot_panel,
        )

        self.followup_questions.select(
            self.chat_suggestion.select_example,
            outputs=[self.chat_panel.text_input],
            show_progress="hidden",
        ).then(
            fn=None,
            inputs=None,
            outputs=None,
            js=chat_input_focus_js,
        )

        if KH_DEMO_MODE:
            self.paper_list.examples.select(
                self.paper_list.select_example,
                inputs=[self.paper_list.papers_state],
                outputs=[self.quick_urls],
                show_progress="hidden",
            ).then(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.paper_list.accordion, self.chat_settings],
            ).then(
                fn=None,
                inputs=None,
                outputs=None,
                js=quick_urls_submit_js,
            )

    def submit_msg(
        self,
        chat_input,
        chat_history,
        user_id,
        settings,
        conv_id,
        conv_name,
        first_selector_choices,
        request: gr.Request,
    ):
        """Submit a message to the chatbot"""
        if KH_DEMO_MODE:
            sso_user_id = check_rate_limit("chat", request)
            print("User ID:", sso_user_id)

        if not chat_input:
            raise gr.Error("请输入问题后再发送。")

        chat_input_text = str(chat_input.get("text", "") or "")
        image_paths, image_names = validate_chat_images(chat_input.get("files", []))
        if not chat_input_text.strip() and not image_paths:
            raise gr.Error("请输入问题或添加图片后再发送。")
        display_chat_input_text = format_mentions_for_display(chat_input_text)
        file_ids = []
        used_command = None

        first_selector_choices_map = {
            item[0]: item[1] for item in first_selector_choices
        }

        # get all file names with pattern @"filename" in input_str
        mentions, chat_input_text = get_mentions_regex(chat_input_text)

        # check if web search command is in file_names
        if WEB_SEARCH_COMMAND and WEB_SEARCH_COMMAND in mentions:
            used_command = WEB_SEARCH_COMMAND

        # get all file names in input_str
        file_names = [
            mention for mention in mentions if mention not in (WEB_SEARCH_COMMAND,)
        ]
        if file_names:
            indexed_file_ids = [
                first_selector_choices_map.get(file_name) for file_name in file_names
            ]
            file_ids.extend(
                [file_id for file_id in indexed_file_ids if file_id is not None]
            )

        # get all urls in input_str
        urls, chat_input_text = get_urls(chat_input_text)
        if urls and self.first_indexing_url_fn:
            print("Detected URLs", urls)
            indexed_url_ids = self.first_indexing_url_fn(
                "\n".join(urls),
                True,
                settings,
                user_id,
                request=None,
            )
            file_ids.extend(indexed_url_ids)

            # Add new file ids to the first selector choices for display
            first_selector_choices.extend(zip(urls, indexed_url_ids))

        if not chat_input_text and image_paths:
            chat_input_text = DEFAULT_IMAGE_QUESTION
            display_chat_input_text = DEFAULT_IMAGE_QUESTION
        elif not chat_input_text and file_ids:
            chat_input_text = DEFAULT_QUESTION

        # if start of conversation and no query is specified
        if not chat_input_text and not chat_history:
            chat_input_text = DEFAULT_QUESTION

        if image_names:
            attachment_label = "、".join(f"`{name}`" for name in image_names)
            display_chat_input_text = (
                f"{display_chat_input_text.strip() or chat_input_text}"
                f"\n\n🖼️ 已添加图片：{attachment_label}"
            )

        if file_ids:
            selector_output = [
                "select",
                gr.update(value=file_ids, choices=first_selector_choices),
            ]
        else:
            selector_output = [gr.update(), gr.update()]

        # check if regen mode is active
        if chat_input_text:
            chat_history = chat_history + [(display_chat_input_text, None)]
        else:
            if not chat_history:
                raise gr.Error("当前会话没有可重新生成的内容。")

        if not conv_id:
            if not KH_DEMO_MODE:
                id_, update = self.chat_control.new_conv(user_id)
                with Session(engine) as session:
                    statement = select(Conversation).where(Conversation.id == id_)
                    name = session.exec(statement).one().name
                    new_conv_id = id_
                    conv_update = update
                    new_conv_name = name
            else:
                new_conv_id, new_conv_name, conv_update = None, None, gr.update()
        else:
            new_conv_id = conv_id
            conv_update = gr.update()
            new_conv_name = conv_name

        return (
            [
                {},
                chat_history,
                {"query": chat_input_text, "image_paths": image_paths},
                new_conv_id,
                conv_update,
                new_conv_name,
            ]
            + selector_output
            + [used_command]
        )

    @staticmethod
    def _parse_message_action(payload, chat_history):
        try:
            action = json.loads(payload or "{}")
            message_index = int(action["index"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise gr.Error("消息操作参数无效，请刷新页面后重试。") from exc

        if message_index < 0 or message_index >= len(chat_history or []):
            raise gr.Error("这条消息已发生变化，请刷新页面后重试。")
        if not chat_history[message_index][0]:
            raise gr.Error("只能修改或删除自己发送的问题。")
        return action, message_index

    def edit_message(
        self,
        payload,
        chat_history,
        user_id,
        settings,
        conv_id,
        conv_name,
        first_selector_choices,
        retrieval_history,
        plot_history,
        request: gr.Request,
    ):
        """Replace one user turn and regenerate from that point."""

        action, message_index = self._parse_message_action(payload, chat_history)
        edited_text = str(action.get("text", "")).strip()
        if not edited_text:
            raise gr.Error("修改后的问题不能为空。")

        result = self.submit_msg(
            {"text": edited_text, "files": []},
            list(chat_history[:message_index]),
            user_id,
            settings,
            conv_id,
            conv_name,
            first_selector_choices,
            request,
        )
        return result + [
            list((retrieval_history or [])[:message_index]),
            list((plot_history or [])[:message_index]),
        ]

    def delete_message(
        self,
        payload,
        chat_history,
        conv_id,
        user_id,
        retrieval_history,
        plot_history,
    ):
        """Delete one user/assistant turn and its evidence state."""

        _, message_index = self._parse_message_action(payload, chat_history)
        if not conv_id:
            raise gr.Error("当前会话尚未保存，无法删除消息。")

        messages = list(chat_history or [])
        messages.pop(message_index)
        retrieval_history = list(retrieval_history or [])
        plot_history = list(plot_history or [])
        if message_index < len(retrieval_history):
            retrieval_history.pop(message_index)
        if message_index < len(plot_history):
            plot_history.pop(message_index)

        with Session(engine) as session:
            conversation = session.exec(
                select(Conversation).where(Conversation.id == conv_id)
            ).one_or_none()
            if conversation is None or conversation.user != user_id:
                raise gr.Error("只有会话所有者可以删除消息。")
            data_source = deepcopy(conversation.data_source or {})
            data_source["messages"] = messages
            data_source["retrieval_messages"] = retrieval_history
            data_source["plot_history"] = plot_history
            updated_likes = []
            for like in data_source.get("likes", []):
                if not like or like[0] == message_index:
                    continue
                updated_like = list(like)
                if isinstance(updated_like[0], int) and updated_like[0] > message_index:
                    updated_like[0] -= 1
                updated_likes.append(updated_like)
            data_source["likes"] = updated_likes
            conversation.data_source = data_source
            session.add(conversation)
            session.commit()

        gr.Info("消息及对应回答已删除。")
        info_panel = (
            retrieval_history[-1]
            if retrieval_history
            else "<h5><b>未找到相关证据。</b></h5>"
        )
        plot_data = plot_history[-1] if plot_history else None
        return messages, retrieval_history, plot_history, info_panel, plot_data

    def begin_asr_session(
        self,
        chat_history,
        user_id,
        conv_id,
        conv_name,
        retrieval_history,
        plot_history,
    ):
        """Create a conversation if needed and append one ASR chat message."""

        if not conv_id:
            if KH_DEMO_MODE:
                new_conv_id, new_conv_name, conv_update = None, None, gr.update()
            else:
                new_conv_id, conv_update = self.chat_control.new_conv(user_id)
                with Session(engine) as session:
                    conversation = session.exec(
                        select(Conversation).where(Conversation.id == new_conv_id)
                    ).one()
                    new_conv_name = conversation.name
        else:
            new_conv_id = conv_id
            new_conv_name = conv_name
            conv_update = gr.update()

        (
            segments,
            messages,
            message_index,
            start_button,
            stop_button,
        ) = self.chat_panel.begin_transcription(chat_history)
        retrieval_history = list(retrieval_history or []) + [""]
        plot_history = list(plot_history or []) + [None]
        return (
            segments,
            messages,
            message_index,
            start_button,
            stop_button,
            new_conv_id,
            conv_update,
            new_conv_name,
            retrieval_history,
            plot_history,
        )

    def persist_asr_transcript(
        self,
        convo_id,
        user_id,
        messages,
        retrieval_history,
        plot_history,
        state,
        *selecteds,
    ):
        """Persist an ASR chat message without invoking the reasoning pipeline."""

        self._write_conversation_data(
            convo_id,
            user_id,
            messages,
            retrieval_history,
            plot_history,
            state,
            *selecteds,
        )
        return retrieval_history, plot_history

    def get_recommendations(self, first_selector_choices, file_ids):
        first_selector_choices_map = {
            item[1]: item[0] for item in first_selector_choices
        }
        file_names = [first_selector_choices_map[file_id] for file_id in file_ids]
        if not file_names:
            return ""

        first_file_name = file_names[0].split(".")[0].replace("_", " ")
        return get_recommended_papers(first_file_name)

    def toggle_delete(self, conv_id):
        if conv_id:
            return gr.update(visible=False), gr.update(visible=True)
        else:
            return gr.update(visible=True), gr.update(visible=False)

    def on_set_public_conversation(self, is_public, convo_id):
        if not convo_id:
            gr.Warning("未选择会话")
            return

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == convo_id)

            result = session.exec(statement).one()
            name = result.name

            if result.is_public != is_public:
                # Only trigger updating when user
                # select different value from the current
                result.is_public = is_public
                session.add(result)
                session.commit()

                gr.Info(f"会话“{name}”已设为{'公开' if is_public else '私有'}。")

    def on_subscribe_public_events(self):
        if self._app.f_user_management:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.chat_control.reload_conv,
                    "inputs": [self._app.user_id],
                    "outputs": [self.chat_control.conversation],
                    "show_progress": "hidden",
                },
            )

            self._app.subscribe_event(
                name="onSignOut",
                definition={
                    "fn": lambda: self.chat_control.select_conv("", None),
                    "outputs": [
                        self.chat_control.conversation_id,
                        self.chat_control.conversation,
                        self.chat_control.conversation_rn,
                        self.chat_panel.chatbot,
                        self.followup_questions,
                        self.info_panel,
                        self.state_plot_panel,
                        self.state_retrieval_history,
                        self.state_plot_history,
                        self.chat_control.cb_is_public,
                        self.state_chat,
                    ]
                    + self._indices_input,
                    "show_progress": "hidden",
                },
            )

            if hasattr(self, "quick_upload_accordion"):
                for event_name in ("onSignIn", "onSignOut"):
                    self._app.subscribe_event(
                        name=event_name,
                        definition={
                            "fn": self.toggle_quick_upload_visibility,
                            "inputs": [self._app.user_id],
                            "outputs": [self.quick_upload_accordion],
                            "show_progress": "hidden",
                        },
                    )

    def toggle_quick_upload_visibility(self, user_id):
        """Only administrators can add documents to the shared collection."""
        if not user_id:
            return gr.update(visible=False)

        from ktem.db.models import User

        with Session(engine) as session:
            user = session.exec(select(User).where(User.id == user_id)).first()
        return gr.update(visible=bool(user and user.admin))

    def _on_app_created(self):
        if KH_DEMO_MODE:
            self._app.app.load(
                fn=lambda x: x,
                inputs=[self._user_api_key],
                outputs=[self._user_api_key],
                js=fetch_api_key_js,
            ).then(
                fn=self.chat_control.toggle_demo_login_visibility,
                inputs=[self._user_api_key],
                outputs=[
                    self.chat_control.cb_suggest_chat,
                    self.chat_control.btn_new,
                    self.chat_control.btn_demo_logout,
                    self.chat_control.btn_demo_login,
                ],
            ).then(
                fn=None,
                inputs=None,
                js=chat_input_focus_js,
            )

    def _write_conversation_data(
        self,
        convo_id,
        user_id,
        messages,
        retrieval_history,
        plot_history,
        state,
        *selecteds,
    ):
        """Write one complete, already-aligned conversation snapshot."""

        if not convo_id:
            gr.Warning("请先选择一个会话。")
            return

        selecteds_ = {}
        for index in self._app.index_manager.indices:
            if index.selector is None:
                continue
            if isinstance(index.selector, int):
                selecteds_[str(index.id)] = selecteds[index.selector]
            else:
                selecteds_[str(index.id)] = [selecteds[i] for i in index.selector]

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == convo_id)
            result = session.exec(statement).one()

            data_source = result.data_source
            old_selecteds = data_source.get("selected", {})
            is_owner = result.user == user_id

            # Write down to db
            result.data_source = {
                "selected": selecteds_ if is_owner else old_selecteds,
                "messages": messages,
                "retrieval_messages": retrieval_history,
                "plot_history": plot_history,
                "state": state,
                "likes": deepcopy(data_source.get("likes", [])),
            }
            session.add(result)
            session.commit()

    def persist_data_source(
        self,
        convo_id,
        user_id,
        retrieval_msg,
        plot_data,
        retrival_history,
        plot_history,
        messages,
        state,
        *selecteds,
    ):
        """Update the data source after one reasoning response."""

        if not convo_id:
            gr.Warning("请先选择一个会话。")
            return

        # if not regen, then append the new message
        if not state["app"].get("regen", False):
            retrival_history = retrival_history + [retrieval_msg]
            plot_history = plot_history + [plot_data]
        elif retrival_history:
            print("Updating retrieval history (regen=True)")
            retrival_history[-1] = retrieval_msg
            plot_history[-1] = plot_data

        # reset regen state
        state["app"]["regen"] = False
        self._write_conversation_data(
            convo_id,
            user_id,
            messages,
            retrival_history,
            plot_history,
            state,
            *selecteds,
        )

        return retrival_history, plot_history

    def reasoning_changed(self, reasoning_type):
        if reasoning_type != DEFAULT_SETTING:
            # override app settings state (temporary)
            gr.Info(f"本次会话已切换推理方法：{reasoning_type}")
        return reasoning_type

    def is_liked(self, convo_id, liked: gr.LikeData):
        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == convo_id)
            result = session.exec(statement).one()

            data_source = deepcopy(result.data_source)
            likes = data_source.get("likes", [])
            likes.append([liked.index, liked.value, liked.liked])
            data_source["likes"] = likes

            result.data_source = data_source
            session.add(result)
            session.commit()

    def message_selected(self, retrieval_history, plot_history, msg: gr.SelectData):
        index = msg.index[0]
        try:
            retrieval_content, plot_content = (
                retrieval_history[index],
                plot_history[index],
            )
        except IndexError:
            retrieval_content, plot_content = gr.update(), None

        return retrieval_content, plot_content

    def create_pipeline(
        self,
        settings: dict,
        session_reasoning_type: str,
        session_llm: str,
        session_use_mindmap: bool | str,
        session_use_citation: str,
        session_language: str,
        state: dict,
        command_state: str | None,
        user_id: int,
        *selecteds,
    ):
        """Create the pipeline from settings

        Args:
            settings: the settings of the app
            state: the state of the app
            selected: the list of file ids that will be served as context. If None, then
                consider using all files

        Returns:
            - the pipeline objects
        """
        # override reasoning_mode by temporary chat page state
        print(
            "Session reasoning type",
            session_reasoning_type,
            "use mindmap",
            session_use_mindmap,
            "use citation",
            session_use_citation,
            "language",
            session_language,
        )
        print("Session LLM", session_llm)
        reasoning_mode = (
            settings["reasoning.use"]
            if session_reasoning_type in (DEFAULT_SETTING, None)
            else session_reasoning_type
        )
        reasoning_cls = reasonings[reasoning_mode]
        print("Reasoning class", reasoning_cls)
        reasoning_id = reasoning_cls.get_info()["id"]

        settings = deepcopy(settings)
        llm_setting_key = f"reasoning.options.{reasoning_id}.llm"
        if llm_setting_key in settings and session_llm not in (
            DEFAULT_SETTING,
            None,
            "",
        ):
            settings[llm_setting_key] = session_llm

        if session_use_mindmap not in (DEFAULT_SETTING, None):
            settings["reasoning.options.simple.create_mindmap"] = session_use_mindmap

        if session_use_citation not in (DEFAULT_SETTING, None):
            settings["reasoning.options.simple.highlight_citation"] = (
                session_use_citation
            )

        if session_language not in (DEFAULT_SETTING, None):
            settings["reasoning.lang"] = session_language

        # get retrievers
        retrievers = []

        if WEB_SEARCH_COMMAND and command_state == WEB_SEARCH_COMMAND:
            # set retriever for web search
            if not WebSearch:
                raise ValueError("Web search back-end is not available.")

            web_search = WebSearch()
            retrievers.append(web_search)
        else:
            for index in self._app.index_manager.indices:
                index_selected = []
                if isinstance(index.selector, int):
                    index_selected = selecteds[index.selector]
                if isinstance(index.selector, tuple):
                    for i in index.selector:
                        index_selected.append(selecteds[i])
                iretrievers = index.get_retriever_pipelines(
                    settings, user_id, index_selected
                )
                retrievers += iretrievers

        # prepare states
        reasoning_state = {
            "app": deepcopy(state["app"]),
            "pipeline": deepcopy(state.get(reasoning_id, {})),
        }

        pipeline = reasoning_cls.get_pipeline(settings, reasoning_state, retrievers)

        return pipeline, reasoning_state

    def _has_selected_files(self, user_id: int, *selecteds) -> bool:
        """Return True if any index file selector has documents selected."""
        for index in self._app.index_manager.indices:
            if index.selector is None:
                continue
            index_ui = getattr(self, f"_index_{index.id}", None)
            if index_ui is None or not hasattr(index_ui, "get_selected_ids"):
                continue
            if isinstance(index.selector, int):
                components = (selecteds[index.selector],)
            else:
                components = tuple(selecteds[i] for i in index.selector)
            if index_ui.get_selected_ids(components):
                return True
        return False

    @staticmethod
    def _reasoning_history(chat_history):
        """Exclude assistant-only ASR display turns from LLM prompt history."""

        return [
            (human, assistant)
            for human, assistant in chat_history or []
            if isinstance(human, str) and human.strip()
        ]

    def chat_fn(
        self,
        conversation_id,
        chat_history,
        multimodal_input,
        settings,
        reasoning_type,
        llm_type,
        use_mind_map,
        use_citation,
        language,
        chat_state,
        command_state,
        user_id,
        *selecteds,
    ):
        """Chat function"""
        display_input, chat_output = chat_history[-1]
        chat_history = chat_history[:-1]

        # if chat_input is empty, assume regen mode
        if chat_output:
            chat_state["app"]["regen"] = True

        multimodal_input = multimodal_input or {}
        llm_query = str(multimodal_input.get("query", "") or "").strip()
        if not llm_query:
            llm_query = prepare_llm_query(
                display_input,
                has_selected_files=self._has_selected_files(user_id, *selecteds),
                default_question=DEFAULT_QUESTION,
            )
        user_images = encode_chat_images(multimodal_input.get("image_paths", []))

        queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

        # construct the pipeline
        pipeline, reasoning_state = self.create_pipeline(
            settings,
            reasoning_type,
            llm_type,
            use_mind_map,
            use_citation,
            language,
            chat_state,
            command_state,
            user_id,
            *selecteds,
        )
        print("Reasoning state", reasoning_state)
        pipeline.set_output_queue(queue)

        text, refs, plot, plot_gr = "", "", None, gr.update(visible=False)
        msg_placeholder = getattr(
            flowsettings, "KH_CHAT_MSG_PLACEHOLDER", "Thinking ..."
        )
        print(msg_placeholder)
        yield (
            chat_history + [(display_input, text or msg_placeholder)],
            refs,
            plot_gr,
            plot,
            chat_state,
        )

        try:
            for response in pipeline.stream(
                llm_query,
                conversation_id,
                self._reasoning_history(chat_history),
                user_images=user_images,
            ):
                if not isinstance(response, Document):
                    continue

                if response.channel is None:
                    continue

                if response.channel == "chat":
                    if response.content is None:
                        text = ""
                    else:
                        text += response.content

                if response.channel == "info":
                    if response.content is None:
                        refs = ""
                    else:
                        refs += response.content

                if response.channel == "plot":
                    plot = response.content
                    plot_gr = self._json_to_plot(plot)

                chat_state[pipeline.get_info()["id"]] = reasoning_state["pipeline"]

                yield (
                    chat_history + [(display_input, text or msg_placeholder)],
                    refs,
                    plot_gr,
                    plot,
                    chat_state,
                )
        except Exception as exc:  # noqa: BLE001 - keep the chat stream recoverable
            notice = notify_exception("chat-answer", exc, logger=logger)
            if text:
                text = f"{text}\n\n> ⚠️ {notice.display_message}"
            else:
                text = f"⚠️ {notice.display_message}"
            yield (
                chat_history + [(display_input, text)],
                refs,
                plot_gr,
                plot,
                chat_state,
            )
            return

        if not text:
            empty_msg = getattr(
                flowsettings, "KH_CHAT_EMPTY_MSG_PLACEHOLDER", "(Sorry, I don't know)"
            )
            print(f"Generate nothing: {empty_msg}")
            yield (
                chat_history + [(display_input, text or empty_msg)],
                refs,
                plot_gr,
                plot,
                chat_state,
            )

    def check_and_suggest_name_conv(self, chat_history):
        suggest_pipeline = SuggestConvNamePipeline()
        new_name = gr.update()
        renamed = False
        reasoning_history = self._reasoning_history(chat_history)

        # check if this is a newly created conversation
        if len(reasoning_history) == 1:
            try:
                suggested_name = suggest_pipeline(reasoning_history).text
                suggested_name = strip_think_tag(suggested_name)
                suggested_name = suggested_name.replace('"', "").replace("'", "")[:40]
                new_name = gr.update(value=suggested_name)
                renamed = True
            except Exception as exc:  # noqa: BLE001 - title is an optional feature
                notify_exception(
                    "conversation-title",
                    exc,
                    logger=logger,
                    fallback_message="回答已生成，但自动命名会话失败，您可以稍后手动重命名。",
                )

        return new_name, renamed

    def suggest_chat_conv(
        self,
        settings,
        session_language,
        chat_history,
        use_suggestion,
    ):
        chat_history = self._reasoning_history(chat_history)
        target_language = (
            session_language
            if session_language not in (DEFAULT_SETTING, None)
            else settings["reasoning.lang"]
        )
        if use_suggestion:
            suggested_questions = [[each] for each in ChatSuggestion.CHAT_SAMPLES]
            try:
                suggest_pipeline = SuggestFollowupQuesPipeline()
                suggest_pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(
                    target_language, "English"
                )

                if len(chat_history) >= 1:
                    suggested_resp = suggest_pipeline(chat_history).text
                    if ques_res := re.search(
                        r"\[(.*?)\]", re.sub("\n", "", suggested_resp)
                    ):
                        ques_res_str = ques_res.group()
                        try:
                            suggested_questions = json.loads(ques_res_str)
                            suggested_questions = [[x] for x in suggested_questions]
                        except (TypeError, ValueError, json.JSONDecodeError):
                            logger.warning("Model returned invalid follow-up questions")
            except Exception as exc:  # noqa: BLE001 - suggestions must fail open
                notify_exception(
                    "follow-up-suggestions",
                    exc,
                    logger=logger,
                    fallback_message="回答已生成，但暂时无法生成推荐追问。",
                )

            return gr.update(visible=True), suggested_questions

        return gr.update(visible=False), gr.update()
