from copy import deepcopy

import gradio as gr
import pandas as pd
import yaml
from ktem.app import BasePage
from ktem.utils.file import YAMLNoDateSafeLoader
from theflow.utils.modules import deserialize

from .manager import llms


def format_description(cls):
    params = cls.describe()["params"]
    params_lines = ["| 参数 | 类型 | 说明 |", "| --- | --- | --- |"]
    for key, value in params.items():
        if isinstance(value["auto_callback"], str):
            continue
        params_lines.append(f"| {key} | {value['type']} | {value['help']} |")
    return f"{cls.__doc__}\n\n" + "\n".join(params_lines)


class LLMManagement(BasePage):
    def __init__(self, app):
        self._app = app
        self.spec_desc_default = (
            "# 配置说明\n\n请选择一个语言模型查看配置说明。"
        )
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Tab(label="查看"):  # View
            self.llm_list = gr.DataFrame(
                headers=["名称", "供应商", "是否默认"],
                interactive=False,
                column_widths=[30, 40, 30],
            )

            with gr.Column(visible=False) as self._selected_panel:
                self.selected_llm_name = gr.Textbox(value="", visible=False)
                with gr.Row():
                    with gr.Column():
                        self.edit_default = gr.Checkbox(
                            label="设为默认",  # Set default
                            info=(
                                "将此模型设为系统默认语言模型。建议始终明确设置一个"
                                "默认模型。"
                            ),
                        )
                        self.edit_name = gr.Textbox(
                            label="名称",
                            info="修改语言模型在系统中的显示名称。",
                        )
                        self.edit_spec = gr.Textbox(
                            label="配置规格",  # Specification
                            info="YAML格式的语言模型配置",  # Specification of the LLM in YAML format
                            lines=10,
                        )

                        with gr.Accordion(
                            label="测试连接",
                            visible=False,
                            open=False,  # Test connection
                        ) as self._check_connection_panel:
                            with gr.Row():
                                with gr.Column(scale=1):
                                    self.btn_test_connection = gr.Button("测试")
                                with gr.Column(scale=4):
                                    self.connection_logs = gr.HTML("连接测试日志")

                        with gr.Row(visible=False) as self._selected_panel_btn:
                            with gr.Column():
                                self.btn_edit_save = gr.Button(
                                    "保存", min_width=10, variant="primary"
                                )
                            with gr.Column():
                                self.btn_delete = gr.Button(
                                    "删除", min_width=10, variant="stop"
                                )
                                with gr.Row():
                                    self.btn_delete_yes = gr.Button(
                                        "确认删除",
                                        variant="stop",
                                        visible=False,
                                        min_width=10,
                                    )
                                    self.btn_delete_no = gr.Button(
                                        "取消", visible=False, min_width=10
                                    )
                            with gr.Column():
                                self.btn_close = gr.Button(
                                    "关闭", min_width=10
                                )  # Close

                    with gr.Column():
                        self.edit_spec_desc = gr.Markdown(
                            "# 规格描述"
                        )  # Spec description

        with gr.Tab(label="新增"):  # Add
            with gr.Row():
                with gr.Column(scale=2):
                    self.name = gr.Textbox(
                        label="语言模型名称",  # LLM name
                        info="名称必须唯一，用于在系统中识别该语言模型。",
                    )
                    self.llm_choices = gr.Dropdown(
                        label="语言模型供应商",  # LLM vendors
                        info=(
                            "选择语言模型供应商。每个供应商有不同的配置规格。"  # Choose the vendor for the LLM. Each vendor has different specification.
                        ),
                    )
                    self.spec = gr.Textbox(
                        label="配置规格",  # Specification
                        info="YAML格式的配置",  # Specification of the LLM in YAML format
                    )
                    self.default = gr.Checkbox(
                        label="设为默认",  # Set default
                        info=(
                            "设为默认语言模型。该模型将用于推理。"  # Set this LLM as default. This default LLM will be used for reasoning
                            "by default across the application."
                        ),
                    )
                    self.btn_new = gr.Button(
                        "添加语言模型", variant="primary"
                    )  # Add LLM

                with gr.Column(scale=3):
                    self.spec_desc = gr.Markdown(self.spec_desc_default)

    def _on_app_created(self):
        """Called when the app is created"""
        self._app.app.load(
            self.list_llms,
            inputs=[],
            outputs=[self.llm_list],
        )
        self._app.app.load(
            lambda: gr.update(choices=list(llms.vendors().keys())),
            outputs=[self.llm_choices],
        )

    def on_llm_vendor_change(self, vendor):
        vendor = llms.vendors()[vendor]

        required: dict = {}
        desc = vendor.describe()
        for key, value in desc["params"].items():
            if value.get("required", False):
                required[key] = None

        return yaml.dump(required), format_description(vendor)

    def on_register_events(self):
        self.llm_choices.select(
            self.on_llm_vendor_change,
            inputs=[self.llm_choices],
            outputs=[self.spec, self.spec_desc],
        )
        self.btn_new.click(
            self.create_llm,
            inputs=[self.name, self.llm_choices, self.spec, self.default],
            outputs=[],
        ).success(self.list_llms, inputs=[], outputs=[self.llm_list]).success(
            lambda: ("", None, "", False, self.spec_desc_default),
            outputs=[
                self.name,
                self.llm_choices,
                self.spec,
                self.default,
                self.spec_desc,
            ],
        )
        self.llm_list.select(
            self.select_llm,
            inputs=self.llm_list,
            outputs=[self.selected_llm_name],
            show_progress="hidden",
        )
        self.selected_llm_name.change(
            self.on_selected_llm_change,
            inputs=[self.selected_llm_name],
            outputs=[
                self._selected_panel,
                self._selected_panel_btn,
                self._check_connection_panel,
                # delete section
                self.btn_delete,
                self.btn_delete_yes,
                self.btn_delete_no,
                # edit section
                self.edit_name,
                self.edit_spec,
                self.edit_spec_desc,
                self.edit_default,
            ],
            show_progress="hidden",
        ).success(lambda: gr.update(value=""), outputs=[self.connection_logs])

        self.btn_delete.click(
            self.on_btn_delete_click,
            inputs=[],
            outputs=[self.btn_delete, self.btn_delete_yes, self.btn_delete_no],
            show_progress="hidden",
        )
        self.btn_delete_yes.click(
            self.delete_llm,
            inputs=[self.selected_llm_name],
            outputs=[self.selected_llm_name],
            show_progress="hidden",
        ).then(
            self.list_llms,
            inputs=[],
            outputs=[self.llm_list],
        )
        self.btn_delete_no.click(
            lambda: (
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
            ),
            inputs=[],
            outputs=[self.btn_delete, self.btn_delete_yes, self.btn_delete_no],
            show_progress="hidden",
        )
        self.btn_edit_save.click(
            self.save_llm,
            inputs=[
                self.selected_llm_name,
                self.edit_name,
                self.edit_default,
                self.edit_spec,
            ],
            outputs=[self.selected_llm_name],
            show_progress="hidden",
        ).then(
            self.list_llms,
            inputs=[],
            outputs=[self.llm_list],
        )
        self.btn_close.click(
            lambda: "",
            outputs=[self.selected_llm_name],
        )

        self.btn_test_connection.click(
            self.check_connection,
            inputs=[self.selected_llm_name, self.edit_spec],
            outputs=[self.connection_logs],
        )

    def create_llm(self, name, choices, spec, default):
        try:
            name = name.strip()
            spec = yaml.load(spec, Loader=YAMLNoDateSafeLoader)
            spec["__type__"] = (
                llms.vendors()[choices].__module__
                + "."
                + llms.vendors()[choices].__qualname__
            )

            llms.add(name, spec=spec, default=default)
            gr.Info(f"语言模型“{name}”已创建。")
        except ValueError as e:
            raise gr.Error(str(e))
        except Exception as e:
            raise gr.Error(f"创建语言模型“{name}”失败：{e}")

    def list_llms(self):
        """List the LLMs"""
        items = []
        for item in llms.info().values():
            record = {}
            record["名称"] = item["name"]
            record["供应商"] = item["spec"].get("__type__", "-").split(".")[-1]
            record["是否默认"] = item["default"]
            items.append(record)

        if items:
            llm_list = pd.DataFrame.from_records(items)
        else:
            llm_list = pd.DataFrame.from_records(
                [{"名称": "-", "供应商": "-", "是否默认": "-"}]
            )

        return llm_list

    def select_llm(self, llm_list, ev: gr.SelectData):
        if ev.value == "-" and ev.index[0] == 0:
            gr.Info("尚未配置语言模型，请先添加。")
            return ""

        if not ev.selected:
            return ""

        return llm_list["名称"][ev.index[0]]

    def on_selected_llm_change(self, selected_llm_name):
        if selected_llm_name == "":
            _selected_panel = gr.update(visible=False)
            _selected_panel_btn = gr.update(visible=False)
            _check_connection_panel = gr.update(visible=False)
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)
            edit_name = gr.update(value="")
            edit_spec = gr.update(value="")
            edit_spec_desc = gr.update(value="")
            edit_default = gr.update(value=False)
        else:
            _selected_panel = gr.update(visible=True)
            _selected_panel_btn = gr.update(visible=True)
            _check_connection_panel = gr.update(visible=True, open=False)
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)

            info = deepcopy(llms.info()[selected_llm_name])
            vendor_str = info["spec"].pop("__type__", "-").split(".")[-1]
            vendor = llms.vendors()[vendor_str]

            edit_name = selected_llm_name
            edit_spec = yaml.dump(info["spec"])
            edit_spec_desc = format_description(vendor)
            edit_default = info["default"]

        return (
            _selected_panel,
            _selected_panel_btn,
            _check_connection_panel,
            btn_delete,
            btn_delete_yes,
            btn_delete_no,
            edit_name,
            edit_spec,
            edit_spec_desc,
            edit_default,
        )

    def on_btn_delete_click(self):
        btn_delete = gr.update(visible=False)
        btn_delete_yes = gr.update(visible=True)
        btn_delete_no = gr.update(visible=True)

        return btn_delete, btn_delete_yes, btn_delete_no

    def check_connection(self, selected_llm_name: str, selected_spec):
        log_content: str = ""

        try:
            log_content += f"- 正在测试模型：{selected_llm_name}<br>"
            yield log_content

            # Parse content & init model
            info = deepcopy(llms.info()[selected_llm_name])

            # Parse content & create dummy embedding
            spec = yaml.load(selected_spec, Loader=YAMLNoDateSafeLoader)
            info["spec"].update(spec)

            llm = deserialize(info["spec"], safe=False)

            if llm is None:
                raise ValueError(f"找不到模型：{selected_llm_name}")

            log_content += "- 正在发送测试消息<br>"
            yield log_content
            respond = llm("Hi")

            log_content += (
                f"<mark>- 连接成功，模型返回：\n {respond}</mark><br>"
            )
            yield log_content

            gr.Info(f"语言模型“{selected_llm_name}”连接成功。")
        except Exception as e:
            log_content += (
                f"<mark>- 连接失败：\n {e}</mark>"
            )
            yield log_content

        return log_content

    def save_llm(self, selected_llm_name, edit_name, default, spec):
        try:
            new_name = edit_name.strip()
            spec = yaml.load(spec, Loader=YAMLNoDateSafeLoader)
            spec["__type__"] = llms.info()[selected_llm_name]["spec"]["__type__"]
            llms.update(
                selected_llm_name, spec=spec, default=default, new_name=new_name
            )
            final_name = (
                new_name if new_name != selected_llm_name else selected_llm_name
            )
            gr.Info(f"语言模型“{final_name}”已保存。")
            return final_name
        except ValueError as e:
            raise gr.Error(str(e))
        except Exception as e:
            raise gr.Error(f"保存语言模型“{selected_llm_name}”失败：{e}")

    def delete_llm(self, selected_llm_name):
        try:
            llms.delete(selected_llm_name)
        except Exception as e:
            gr.Error(f"删除语言模型“{selected_llm_name}”失败：{e}")
            return selected_llm_name

        return ""
