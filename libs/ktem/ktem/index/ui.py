import gradio as gr
import pandas as pd
import yaml
from ktem.app import BasePage
from ktem.utils.file import YAMLNoDateSafeLoader
from ktem.utils.i18n import translate_ui_text

from .manager import IndexManager


# UGLY way to restart gradio server by updating atime
def update_current_module_atime():
    import os
    import time

    # Define the file path
    file_path = __file__
    print("Updating atime for", file_path)

    # Get the current time
    current_time = time.time()
    # Set the modified time (and access time) to the current time
    os.utime(file_path, (current_time, current_time))


def format_description(cls):
    user_settings = cls.get_admin_settings()
    params_lines = ["| 参数 | 默认值 | 说明 |", "| --- | --- | --- |"]
    for key, value in user_settings.items():
        params_lines.append(
            f"| {key} | {value.get('value', '')} | {value.get('info', '')} |"
        )
    return f"{cls.__doc__}\n\n" + "\n".join(params_lines)


class IndexManagement(BasePage):
    def __init__(self, app):
        self._app = app
        self.manager: IndexManager = app.index_manager
        self.spec_desc_default = (
            "# 配置说明\n\n请选择一个索引查看配置说明。"
        )
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Tab(label="查看"):  # View
            self.index_list = gr.DataFrame(
                headers=["ID", "名称", "索引类型"],
                interactive=False,
                column_widths=[10, 30, 60],
            )

            with gr.Column(visible=False) as self._selected_panel:
                self.selected_index_id = gr.Number(value=-1, visible=False)
                with gr.Row():
                    with gr.Column():
                        self.edit_name = gr.Textbox(
                            label="索引名称",  # Index name
                        )
                        self.edit_spec = gr.Textbox(
                            label="索引配置",  # Index config
                            info="管理员配置，使用YAML格式",  # Admin configuration of the Index in YAML format
                            lines=10,
                        )

                        gr.Markdown(
                            "**注意：** 修改或删除索引后需要重启系统；部分配置变更"
                            "还需要重新构建索引才能生效。"
                        )
                        with gr.Row():
                            self.btn_edit_save = gr.Button(
                                "保存",
                                min_width=10,
                                variant="primary",  # Save
                            )
                            self.btn_delete = gr.Button(
                                "删除",
                                min_width=10,
                                variant="stop",  # Delete
                            )
                            with gr.Row(visible=False) as self._delete_confirm:
                                self.btn_delete_yes = gr.Button(
                                    "确认删除",  # Confirm Delete
                                    variant="stop",
                                    min_width=10,
                                )
                                self.btn_delete_no = gr.Button(
                                    "取消", min_width=10
                                )  # Cancel
                            self.btn_close = gr.Button("关闭", min_width=10)  # Close

                    with gr.Column():
                        self.edit_spec_desc = gr.Markdown(
                            "# 规格描述"
                        )  # Spec description

        with gr.Tab(label="新增") as self._add_tab:  # Add
            with gr.Row():
                with gr.Column(scale=2):
                    self.name = gr.Textbox(
                        label="索引名称",  # Index name
                        info="必须唯一且非空。",  # Must be unique and non-empty.
                    )
                    self.index_type = gr.Dropdown(label="索引类型")  # Index type
                    self.spec = gr.Textbox(
                        label="配置规格",  # Specification
                        info="索引配置，使用YAML格式",  # Specification of the index in YAML format.
                    )
                    gr.Markdown(
                        "<mark>提示</mark>：创建索引后请重启应用。"
                    )
                    self.btn_new = gr.Button("添加", variant="primary")  # Add

                with gr.Column(scale=3):
                    self.spec_desc = gr.Markdown(self.spec_desc_default)

    def _on_app_created(self):
        """Called when the app is created"""
        self._app.app.load(
            self.list_indices,
            inputs=[],
            outputs=[self.index_list],
        )
        self._app.app.load(
            lambda: gr.update(
                choices=[
                    (translate_ui_text(key.split(".")[-1]), key)
                    for key in self.manager.index_types.keys()
                ]
            ),
            outputs=[self.index_type],
        )

    def on_register_events(self):
        self.index_type.select(
            self.on_index_type_change,
            inputs=[self.index_type],
            outputs=[self.spec, self.spec_desc],
        )
        self.btn_new.click(
            self.create_index,
            inputs=[self.name, self.index_type, self.spec],
            outputs=None,
        ).success(self.list_indices, inputs=[], outputs=[self.index_list]).success(
            lambda: ("", None, "", self.spec_desc_default),
            outputs=[
                self.name,
                self.index_type,
                self.spec,
                self.spec_desc,
            ],
        ).success(update_current_module_atime)
        self.index_list.select(
            self.select_index,
            inputs=self.index_list,
            outputs=[self.selected_index_id],
            show_progress="hidden",
        )

        self.selected_index_id.change(
            self.on_selected_index_change,
            inputs=[self.selected_index_id],
            outputs=[
                self._selected_panel,
                # edit section
                self.edit_spec,
                self.edit_spec_desc,
                self.edit_name,
            ],
            show_progress="hidden",
        )
        self.btn_delete.click(
            lambda: (
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
            ),
            inputs=[],
            outputs=[
                self.btn_edit_save,
                self.btn_delete,
                self.btn_close,
                self._delete_confirm,
            ],
            show_progress="hidden",
        )
        self.btn_delete_yes.click(
            self.delete_index,
            inputs=[self.selected_index_id],
            outputs=[self.selected_index_id],
            show_progress="hidden",
        ).then(
            self.list_indices,
            inputs=[],
            outputs=[self.index_list],
        ).success(update_current_module_atime)
        self.btn_delete_no.click(
            lambda: (
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=False),
            ),
            inputs=[],
            outputs=[
                self.btn_edit_save,
                self.btn_delete,
                self.btn_close,
                self._delete_confirm,
            ],
            show_progress="hidden",
        )
        self.btn_edit_save.click(
            self.update_index,
            inputs=[
                self.selected_index_id,
                self.edit_name,
                self.edit_spec,
            ],
            show_progress="hidden",
        ).then(
            self.list_indices,
            inputs=[],
            outputs=[self.index_list],
        )
        self.btn_close.click(
            lambda: -1,
            outputs=[self.selected_index_id],
        )

    def on_subscribe_public_events(self):
        # subscribe to sign in/out events to toggle index create/edit permissions
        try:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.toggle_index_permissions,
                    "inputs": [self._app.user_id],
                    "outputs": [
                        # btn_new, selected panel, edit/save, delete, delete_yes, delete_no
                        self.btn_new,
                        self._selected_panel,
                        self.btn_edit_save,
                        self.btn_delete,
                        self.btn_delete_yes,
                        self.btn_delete_no,
                        self._add_tab,
                    ],
                    "show_progress": "hidden",
                },
            )

            self._app.subscribe_event(
                name="onSignOut",
                definition={
                    "fn": self.toggle_index_permissions,
                    "inputs": [self._app.user_id],
                    "outputs": [
                        self.btn_new,
                        self._selected_panel,
                        self.btn_edit_save,
                        self.btn_delete,
                        self.btn_delete_yes,
                        self.btn_delete_no,
                        self._add_tab,
                    ],
                    "show_progress": "hidden",
                },
            )
        except Exception:
            # no-op if event system not ready
            pass

    def toggle_index_permissions(self, user_id):
        # default: hide create/edit controls
        visible_for_admin = False
        if not user_id:
            visible_for_admin = False
        else:
            try:
                from ktem.db.models import User, engine
                from sqlmodel import Session, select

                with Session(engine) as session:
                    user = session.exec(select(User).where(User.id == user_id)).first()
                    if user and user.admin:
                        visible_for_admin = True
            except Exception:
                visible_for_admin = False

        btn_new = gr.update(visible=visible_for_admin)
        selected_panel = gr.update(visible=visible_for_admin)
        btn_edit_save = gr.update(visible=visible_for_admin)
        btn_delete = gr.update(visible=visible_for_admin)
        btn_delete_yes = gr.update(visible=False)
        btn_delete_no = gr.update(visible=False)
        add_tab = gr.update(visible=visible_for_admin)

        return (
            btn_new,
            selected_panel,
            btn_edit_save,
            btn_delete,
            btn_delete_yes,
            btn_delete_no,
            add_tab,
        )

    def on_index_type_change(self, index_type: str):
        """Update the spec description and pre-fill the default values

        Args:
            index_type: the name of the index type, this is usually the class name

        Returns:
            A tuple of the default spec and the description
        """
        index_type_cls = self.manager.index_types[index_type]
        required: dict = {
            key: value.get("value", None)
            for key, value in index_type_cls.get_admin_settings().items()
        }

        return yaml.dump(required, sort_keys=False), format_description(index_type_cls)

    def create_index(self, name: str, index_type: str, config: str):
        """Create the index"""
        name = name.strip()
        if not name:
            raise gr.Error("索引名称不能为空。")

        existing_names = {idx.name for idx in self.manager.indices}
        if name in existing_names:
            raise gr.Error(f"索引“{name}”已存在，请使用其他名称。")

        try:
            self.manager.build_index(
                name=name,
                config=yaml.load(config, Loader=YAMLNoDateSafeLoader),
                index_type=index_type,
            )
            gr.Info(f"索引“{name}”已创建，请重启应用。")
        except Exception as e:
            raise gr.Error(f"创建索引“{name}”失败：{e}")

    def list_indices(self):
        """List the indices constructed by the user"""
        items = []
        for item in self.manager.indices:
            record = {}
            record["ID"] = item.id
            record["名称"] = item.name
            record["索引类型"] = translate_ui_text(item.__class__.__name__)
            items.append(record)

        if items:
            indices_list = pd.DataFrame.from_records(items)
        else:
            indices_list = pd.DataFrame.from_records(
                [{"ID": "-", "名称": "-", "索引类型": "-"}]
            )

        return indices_list

    def select_index(self, index_list, ev: gr.SelectData) -> int:
        """Return the index id"""
        if ev.value == "-" and ev.index[0] == 0:
            gr.Info("尚未创建索引，请先添加。")
            return -1

        if not ev.selected:
            return -1

        return int(index_list["ID"][ev.index[0]])

    def on_selected_index_change(self, selected_index_id: int):
        """Show the relevant index as user selects it on the UI

        Args:
            selected_index_id: the id of the selected index
        """
        if selected_index_id == -1:
            _selected_panel = gr.update(visible=False)
            edit_spec = gr.update(value="")
            edit_spec_desc = gr.update(value="")
            edit_name = gr.update(value="")
        else:
            _selected_panel = gr.update(visible=True)
            index = self.manager.info()[selected_index_id]
            edit_spec = yaml.dump(index.config)
            edit_spec_desc = format_description(index.__class__)
            edit_name = index.name

        return (
            _selected_panel,
            edit_spec,
            edit_spec_desc,
            edit_name,
        )

    def update_index(self, selected_index_id: int, name: str, config: str):
        name = name.strip()
        if not name:
            raise gr.Error("索引名称不能为空。")

        # Check uniqueness (excluding current index)
        for idx in self.manager.indices:
            if idx.name == name and idx.id != selected_index_id:
                raise gr.Error(
                    f"索引“{name}”已存在，请使用其他名称。"
                )

        try:
            spec = yaml.load(config, Loader=YAMLNoDateSafeLoader)
            self.manager.update_index(selected_index_id, name, spec)
            gr.Info(f"索引“{name}”已更新，请重启应用。")
        except gr.Error:
            raise
        except Exception as e:
            raise gr.Error(f"保存索引“{name}”失败：{e}")

    def delete_index(self, selected_index_id):
        try:
            self.manager.delete_index(selected_index_id)
            gr.Info("索引已删除，请重启应用。")
        except Exception as e:
            gr.Warning(f"删除索引失败：{e}")
            return selected_index_id

        return -1
