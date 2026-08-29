from copy import deepcopy

import gradio as gr
import pandas as pd
import yaml
from ktem.app import BasePage
from ktem.utils.file import YAMLNoDateSafeLoader
from theflow.utils.modules import deserialize

from .manager import embedding_models_manager


def format_description(cls):
    params = cls.describe()["params"]
    params_lines = ["| 参数 | 类型 | 说明 |", "| --- | --- | --- |"]
    for key, value in params.items():
        if isinstance(value["auto_callback"], str):
            continue
        params_lines.append(f"| {key} | {value['type']} | {value['help']} |")
    return f"{cls.__doc__}\n\n" + "\n".join(params_lines)


class EmbeddingManagement(BasePage):
    def __init__(self, app):
        self._app = app
        self.spec_desc_default = (
            "# 配置说明\n\n请选择一个嵌入模型查看配置说明。"
        )
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Tab(label="查看"):
            self.emb_list = gr.DataFrame(
                headers=["名称", "供应商", "是否默认"],
                interactive=False,
                column_widths=[30, 40, 30],
            )

            with gr.Column(visible=False) as self._selected_panel:
                self.selected_emb_name = gr.Textbox(value="", visible=False)
                with gr.Row():
                    with gr.Column():
                        self.edit_default = gr.Checkbox(
                            label="设为默认",
                            info=(
                                "将此模型设为系统默认嵌入模型。"
                            ),
                        )
                        self.edit_name = gr.Textbox(
                            label="名称",
                            info="修改嵌入模型在系统中的显示名称。",
                        )
                        self.edit_spec = gr.Textbox(
                            label="配置规格",
                            info="嵌入模型的 YAML 配置。",
                            lines=10,
                        )

                        with gr.Accordion(
                            label="测试连接", visible=False, open=False
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
                                self.btn_close = gr.Button("关闭", min_width=10)

                    with gr.Column():
                        self.edit_spec_desc = gr.Markdown("# 配置说明")

        with gr.Tab(label="新增"):
            with gr.Row():
                with gr.Column(scale=2):
                    self.name = gr.Textbox(
                        label="嵌入模型名称",
                        info="名称必须唯一且非空，用于在系统中识别该嵌入模型。",
                    )
                    self.emb_choices = gr.Dropdown(
                        label="供应商",
                        info="选择嵌入模型供应商，不同供应商使用不同配置。",
                    )
                    self.spec = gr.Textbox(
                        label="配置规格",
                        info="嵌入模型的 YAML 配置。",
                    )
                    self.default = gr.Checkbox(
                        label="设为默认",
                        info="将此模型设为系统默认嵌入模型。",
                    )
                    self.btn_new = gr.Button("添加嵌入模型", variant="primary")

                with gr.Column(scale=3):
                    self.spec_desc = gr.Markdown(self.spec_desc_default)

    def _on_app_created(self):
        """Called when the app is created"""
        self._app.app.load(
            self.list_embeddings,
            inputs=[],
            outputs=[self.emb_list],
        )
        self._app.app.load(
            lambda: gr.update(choices=list(embedding_models_manager.vendors().keys())),
            outputs=[self.emb_choices],
        )

    def on_emb_vendor_change(self, vendor):
        vendor = embedding_models_manager.vendors()[vendor]

        required: dict = {}
        desc = vendor.describe()
        for key, value in desc["params"].items():
            if value.get("required", False):
                required[key] = value.get("default", None)

        return yaml.dump(required), format_description(vendor)

    def on_register_events(self):
        self.emb_choices.select(
            self.on_emb_vendor_change,
            inputs=[self.emb_choices],
            outputs=[self.spec, self.spec_desc],
        )
        self.btn_new.click(
            self.create_emb,
            inputs=[self.name, self.emb_choices, self.spec, self.default],
            outputs=None,
        ).success(self.list_embeddings, inputs=[], outputs=[self.emb_list]).success(
            lambda: ("", None, "", False, self.spec_desc_default),
            outputs=[
                self.name,
                self.emb_choices,
                self.spec,
                self.default,
                self.spec_desc,
            ],
        )
        self.emb_list.select(
            self.select_emb,
            inputs=self.emb_list,
            outputs=[self.selected_emb_name],
            show_progress="hidden",
        )
        self.selected_emb_name.change(
            self.on_selected_emb_change,
            inputs=[self.selected_emb_name],
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
            self.delete_emb,
            inputs=[self.selected_emb_name],
            outputs=[self.selected_emb_name],
            show_progress="hidden",
        ).then(
            self.list_embeddings,
            inputs=[],
            outputs=[self.emb_list],
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
            self.save_emb,
            inputs=[
                self.selected_emb_name,
                self.edit_name,
                self.edit_default,
                self.edit_spec,
            ],
            outputs=[self.selected_emb_name],
            show_progress="hidden",
        ).then(
            self.list_embeddings,
            inputs=[],
            outputs=[self.emb_list],
        )
        self.btn_close.click(
            lambda: "",
            outputs=[self.selected_emb_name],
        )

        self.btn_test_connection.click(
            self.check_connection,
            inputs=[self.selected_emb_name, self.edit_spec],
            outputs=[self.connection_logs],
        )

    def create_emb(self, name, choices, spec, default):
        try:
            name = name.strip()
            spec = yaml.load(spec, Loader=YAMLNoDateSafeLoader)
            spec["__type__"] = (
                embedding_models_manager.vendors()[choices].__module__
                + "."
                + embedding_models_manager.vendors()[choices].__qualname__
            )

            embedding_models_manager.add(name, spec=spec, default=default)
            gr.Info(f"嵌入模型“{name}”已创建。")
        except ValueError as e:
            raise gr.Error(str(e))
        except Exception as e:
            raise gr.Error(f"创建嵌入模型“{name}”失败：{e}")

    def list_embeddings(self):
        """List the Embedding models"""
        items = []
        for item in embedding_models_manager.info().values():
            record = {}
            record["名称"] = item["name"]
            record["供应商"] = item["spec"].get("__type__", "-").split(".")[-1]
            record["是否默认"] = item["default"]
            items.append(record)

        if items:
            emb_list = pd.DataFrame.from_records(items)
        else:
            emb_list = pd.DataFrame.from_records(
                [{"名称": "-", "供应商": "-", "是否默认": "-"}]
            )

        return emb_list

    def select_emb(self, emb_list, ev: gr.SelectData):
        if ev.value == "-" and ev.index[0] == 0:
            gr.Info("尚未配置嵌入模型，请先添加。")
            return ""

        if not ev.selected:
            return ""

        return emb_list["名称"][ev.index[0]]

    def on_selected_emb_change(self, selected_emb_name):
        if selected_emb_name == "":
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

            info = deepcopy(embedding_models_manager.info()[selected_emb_name])
            vendor_str = info["spec"].pop("__type__", "-").split(".")[-1]
            vendor = embedding_models_manager.vendors()[vendor_str]

            edit_name = selected_emb_name
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

    def check_connection(self, selected_emb_name, selected_spec):
        log_content: str = ""
        try:
            log_content += f"- 正在测试模型：{selected_emb_name}<br>"
            yield log_content

            # Parse content & init model
            info = deepcopy(embedding_models_manager.info()[selected_emb_name])

            # Parse content & create dummy embedding
            spec = yaml.load(selected_spec, Loader=YAMLNoDateSafeLoader)
            info["spec"].update(spec)

            emb = deserialize(info["spec"], safe=False)

            if emb is None:
                raise ValueError(f"找不到模型：{selected_emb_name}")

            log_content += "- 正在发送测试文本<br>"
            yield log_content
            _ = emb("Hi")

            log_content += (
                "<mark>- 连接成功。</mark><br>"
            )
            yield log_content

            gr.Info(f"嵌入模型“{selected_emb_name}”连接成功。")
        except Exception as e:
            print(e)
            log_content += (
                f"<mark>- 连接失败：\n {e}</mark>"
            )
            yield log_content

        return log_content

    def save_emb(self, selected_emb_name, edit_name, default, spec):
        try:
            new_name = edit_name.strip()
            spec = yaml.load(spec, Loader=YAMLNoDateSafeLoader)
            spec["__type__"] = embedding_models_manager.info()[selected_emb_name][
                "spec"
            ]["__type__"]
            embedding_models_manager.update(
                selected_emb_name, spec=spec, default=default, new_name=new_name
            )
            final_name = (
                new_name if new_name != selected_emb_name else selected_emb_name
            )
            gr.Info(f"嵌入模型“{final_name}”已保存。")
            return final_name
        except ValueError as e:
            raise gr.Error(str(e))
        except Exception as e:
            raise gr.Error(f"保存嵌入模型“{selected_emb_name}”失败：{e}")

    def delete_emb(self, selected_emb_name):
        try:
            embedding_models_manager.delete(selected_emb_name)
        except Exception as e:
            gr.Error(f"删除嵌入模型“{selected_emb_name}”失败：{e}")
            return selected_emb_name

        return ""
