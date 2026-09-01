"""Administrator UI for voiceprint registration and deletion."""

from __future__ import annotations

import gradio as gr
import pandas as pd

from ktem.app import BasePage

from .service import (
    ASRModelConfig,
    ASRModelManager,
    ASRService,
    create_asr_provider,
    get_asr_model_manager,
    get_asr_service,
)


class ASRModelManagement(BasePage):
    """Configure the realtime speech recognition service separately from LLMs."""

    def __init__(self, app, manager: ASRModelManager | None = None):
        self._app = app
        self._manager = manager or get_asr_model_manager()
        self.on_building_ui()

    def on_building_ui(self):
        gr.Markdown(
            "## 语音识别模型\n\n"
            "语音识别与大语言模型相互独立。本地 FunASR 模式通过 Kotaemon "
            "服务端连接离线 ASR，接口密钥不会发送到浏览器。保存配置后需重启 "
            "Kotaemon 才会切换运行中的 Provider。"
        )
        self.provider = gr.Dropdown(
            label="语音识别供应商",
            choices=[
                ("本地 FunASR + 3D-Speaker", "local-funasr"),
                ("模拟服务（仅开发测试）", "mock"),
            ],
            value="mock",
            interactive=True,
        )
        self.model = gr.Textbox(
            label="模型名称",
            placeholder="真实 ASR 服务部署后填写",
        )
        self.api_base_url = gr.Textbox(
            label="接口地址",
            placeholder="例如：http://asr.internal.example/v1",
        )
        self.api_key = gr.Textbox(
            label="接口密钥",
            type="password",
            placeholder="内网服务无需鉴权时可留空",
        )
        self.timeout = gr.Number(
            label="请求超时（秒）",
            value=60,
            minimum=1,
            precision=0,
        )
        with gr.Row():
            self.save_button = gr.Button("保存配置", variant="primary")
            self.test_button = gr.Button("测试当前配置")
        self.test_result = gr.Markdown()

    def load_config(self, user_id):
        try:
            self._manager.voiceprints.assert_admin(user_id)
        except PermissionError:
            return "mock", "", "", "", 60
        config = self._manager.get()
        return (
            config.provider,
            config.model,
            config.api_base_url,
            config.api_key,
            config.timeout,
        )

    def save_config(self, user_id, provider, model, api_base_url, api_key, timeout):
        try:
            self._manager.update(
                user_id,
                provider,
                api_base_url,
                api_key,
                model,
                float(timeout),
            )
        except (PermissionError, TypeError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info("语音识别模型配置已保存。")

    def test_config(self, provider, model, api_base_url, api_key, timeout):
        if provider == "mock":
            return "✅ 模拟 ASR 可用，可测试实时分段、说话人分离与声纹显示。"
        try:
            config = ASRModelConfig(
                provider=provider,
                api_base_url=api_base_url,
                api_key=api_key,
                model=model,
                timeout=float(timeout),
            )
            create_asr_provider(config).healthcheck()
        except Exception as exc:
            return f"❌ 本地 ASR 不可用：{exc}"
        return "✅ 本地 FunASR 已就绪，模型已加载，可接受实时转写请求。"

    def on_register_events(self):
        self.save_button.click(
            self.save_config,
            inputs=[
                self._app.user_id,
                self.provider,
                self.model,
                self.api_base_url,
                self.api_key,
                self.timeout,
            ],
            show_progress="hidden",
        )
        self.test_button.click(
            self.test_config,
            inputs=[
                self.provider,
                self.model,
                self.api_base_url,
                self.api_key,
                self.timeout,
            ],
            outputs=[self.test_result],
            show_progress="hidden",
        )

    def on_subscribe_public_events(self):
        if not self._app.f_user_management:
            return
        self._app.subscribe_event(
            name="onSignIn",
            definition={
                "fn": self.load_config,
                "inputs": [self._app.user_id],
                "outputs": [
                    self.provider,
                    self.model,
                    self.api_base_url,
                    self.api_key,
                    self.timeout,
                ],
                "show_progress": "hidden",
            },
        )
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: ("mock", "", "", "", 60),
                "outputs": [
                    self.provider,
                    self.model,
                    self.api_base_url,
                    self.api_key,
                    self.timeout,
                ],
                "show_progress": "hidden",
            },
        )

    def _on_app_created(self):
        if self._app.f_user_management:
            return
        self._app.app.load(
            self.load_config,
            inputs=[self._app.user_id],
            outputs=[
                self.provider,
                self.model,
                self.api_base_url,
                self.api_key,
                self.timeout,
            ],
            show_progress="hidden",
        )


class VoiceprintManagement(BasePage):
    """Manage the identity library used by speaker verification."""

    def __init__(self, app, service: ASRService | None = None):
        self._app = app
        self._service = service or get_asr_service()
        self.on_building_ui()

    def on_building_ui(self):
        mode = "模拟服务" if self._service.is_mock else self._service.provider.name
        gr.Markdown(
            "## 声纹库\n\n"
            "只有管理员可以维护。实时转写会先进行说话人分离，再使用这里的"
            f"声纹将说话人编号映射为人员姓名。当前：**{mode}**。"
        )

        self.voiceprint_table = gr.DataFrame(
            headers=["ID", "姓名", "样本数", "来源", "创建时间"],
            datatype=["str", "str", "number", "str", "str"],
            interactive=False,
            column_widths=[0, 25, 15, 15, 30],
            label="已注册声纹",
            height=240,
        )

        with gr.Accordion("注册新声纹", open=True):
            self.display_name = gr.Textbox(
                label="人员姓名",
                placeholder="例如：张三",
                max_lines=1,
                elem_id="voiceprint-display-name",
            )
            gr.Markdown(
                "请使用同一人的清晰语音，建议 5–15 秒；避免背景音乐、混响和多人同时说话。",
                elem_classes=["voiceprint-guidance"],
            )
            with gr.Tabs(elem_id="voiceprint-sample-tabs"):
                with gr.Tab("录制声纹"):
                    self.recorded_voice_sample = gr.Audio(
                        label="现场录音",
                        sources=["microphone"],
                        type="filepath",
                        format="wav",
                        editable=False,
                        show_download_button=False,
                        show_share_button=False,
                        min_length=3,
                        max_length=30,
                        elem_id="voiceprint-recorded-sample",
                    )
                    with gr.Row(elem_classes=["voiceprint-action-row"]):
                        self.register_recording_button = gr.Button(
                            "使用录音注册",
                            variant="primary",
                            interactive=False,
                            elem_id="voiceprint-register-recording",
                        )
                with gr.Tab("上传声纹"):
                    self.uploaded_voice_sample = gr.Audio(
                        label="上传音频",
                        sources=["upload"],
                        type="filepath",
                        format="wav",
                        editable=False,
                        show_download_button=False,
                        show_share_button=False,
                        min_length=3,
                        max_length=30,
                        elem_id="voiceprint-uploaded-sample",
                    )
                    with gr.Row(elem_classes=["voiceprint-action-row"]):
                        self.register_upload_button = gr.Button(
                            "使用文件注册",
                            variant="primary",
                            interactive=False,
                            elem_id="voiceprint-register-upload",
                        )

            # Compatibility aliases for extensions that accessed the original fields.
            self.voice_sample = self.uploaded_voice_sample
            self.register_button = self.register_upload_button

        with gr.Accordion("删除声纹", open=False):
            self.delete_choice = gr.Dropdown(
                label="选择人员",
                choices=[],
                interactive=True,
                elem_id="voiceprint-delete-choice",
            )
            with gr.Row(elem_classes=["voiceprint-action-row"]):
                self.delete_button = gr.Button(
                    "删除",
                    variant="stop",
                    elem_id="voiceprint-delete",
                )
                self.delete_confirm = gr.Button(
                    "确认删除",
                    variant="stop",
                    visible=False,
                    elem_id="voiceprint-delete-confirm",
                )
                self.delete_cancel = gr.Button(
                    "取消",
                    visible=False,
                    elem_id="voiceprint-delete-cancel",
                )

    def _empty_table(self):
        return pd.DataFrame(columns=["ID", "姓名", "样本数", "来源", "创建时间"])

    def list_voiceprints(self, user_id):
        try:
            items = self._service.voiceprints.list_for_admin(
                user_id, is_mock=self._service.is_mock
            )
        except PermissionError:
            return self._empty_table(), gr.update(choices=[], value=None)

        records = [
            {
                "ID": item.id,
                "姓名": item.display_name,
                "样本数": item.sample_count,
                "来源": "模拟" if item.is_mock else self._service.provider.name,
                "创建时间": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for item in items
        ]
        table = pd.DataFrame.from_records(records) if records else self._empty_table()
        choices = [(item.display_name, item.id) for item in items]
        return table, gr.update(choices=choices, value=None)

    def register_voiceprint(self, user_id, display_name, audio_path):
        try:
            self._service.register_voiceprint(user_id, display_name, audio_path)
        except (PermissionError, RuntimeError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info(f"已注册“{display_name.strip()}”的声纹")
        return "", None

    def register_voiceprint_from_form(self, user_id, display_name, audio_path):
        self.register_voiceprint(user_id, display_name, audio_path)
        return (
            "",
            None,
            None,
            gr.update(interactive=False),
            gr.update(interactive=False),
        )

    @staticmethod
    def update_register_actions(display_name, recorded_audio, uploaded_audio):
        has_name = bool((display_name or "").strip())
        return (
            gr.update(interactive=has_name and bool(recorded_audio)),
            gr.update(interactive=has_name and bool(uploaded_audio)),
        )

    def delete_voiceprint(self, user_id, voiceprint_id):
        if not voiceprint_id:
            raise gr.Error("请先选择要删除的人员")
        try:
            self._service.delete_voiceprint(user_id, voiceprint_id)
        except (PermissionError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc
        gr.Info("声纹已删除")

    @staticmethod
    def toggle_delete_confirmation():
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=True),
        )

    @staticmethod
    def reset_delete_confirmation():
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    def on_register_events(self):
        register_inputs = [
            self.display_name,
            self.recorded_voice_sample,
            self.uploaded_voice_sample,
        ]
        register_buttons = [
            self.register_recording_button,
            self.register_upload_button,
        ]
        for trigger in (
            self.display_name.input,
            self.recorded_voice_sample.change,
            self.uploaded_voice_sample.change,
        ):
            trigger(
                self.update_register_actions,
                inputs=register_inputs,
                outputs=register_buttons,
                show_progress="hidden",
                queue=False,
            )

        register_outputs = [
            self.display_name,
            self.recorded_voice_sample,
            self.uploaded_voice_sample,
            self.register_recording_button,
            self.register_upload_button,
        ]
        for button, audio_input in (
            (self.register_recording_button, self.recorded_voice_sample),
            (self.register_upload_button, self.uploaded_voice_sample),
        ):
            button.click(
                self.register_voiceprint_from_form,
                inputs=[self._app.user_id, self.display_name, audio_input],
                outputs=register_outputs,
            ).success(
                self.list_voiceprints,
                inputs=[self._app.user_id],
                outputs=[self.voiceprint_table, self.delete_choice],
            )

        self.delete_button.click(
            self.toggle_delete_confirmation,
            outputs=[self.delete_button, self.delete_confirm, self.delete_cancel],
            show_progress="hidden",
        )
        self.delete_cancel.click(
            self.reset_delete_confirmation,
            outputs=[self.delete_button, self.delete_confirm, self.delete_cancel],
            show_progress="hidden",
        )
        self.delete_confirm.click(
            self.delete_voiceprint,
            inputs=[self._app.user_id, self.delete_choice],
            outputs=[self.delete_choice],
            show_progress="hidden",
        ).success(
            self.list_voiceprints,
            inputs=[self._app.user_id],
            outputs=[self.voiceprint_table, self.delete_choice],
        ).then(
            self.reset_delete_confirmation,
            outputs=[self.delete_button, self.delete_confirm, self.delete_cancel],
            show_progress="hidden",
        )

    def on_subscribe_public_events(self):
        if not self._app.f_user_management:
            return
        self._app.subscribe_event(
            name="onSignIn",
            definition={
                "fn": self.list_voiceprints,
                "inputs": [self._app.user_id],
                "outputs": [self.voiceprint_table, self.delete_choice],
                "show_progress": "hidden",
            },
        )
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: (
                    self._empty_table(),
                    gr.update(choices=[], value=None),
                ),
                "outputs": [self.voiceprint_table, self.delete_choice],
                "show_progress": "hidden",
            },
        )

    def _on_app_created(self):
        if not self._app.f_user_management:
            self._app.app.load(
                self.list_voiceprints,
                inputs=[self._app.user_id],
                outputs=[self.voiceprint_table, self.delete_choice],
            )
