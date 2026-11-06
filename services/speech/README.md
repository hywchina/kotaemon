# 聊天框实时语音转写

聊天框的麦克风按钮在发送按钮左侧。录音期间显示临时转写，停止后根据整段录音
标注说话人编号。同一段录音内会复用同一说话人的编号。点击「保存转写」才将文本
写入当前会话。如果还没有会话，则在保存时新建。已保存的转写在对应会话下方查看，
并随会话删除。转写有独立记录，保存操作不会提交问答。

浏览器通过 Kotaemon 转发实时音频，ASR 服务通过内存接收单声道 16 kHz PCM。
首版支持单人或双人交替，每次录音上限为 5 分钟。服务端使用 Sherpa-ONNX 的中文 Zipformer 生成临时文本，
使用 Pyannote 分段和 3D-Speaker 嵌入在停止后确定说话人，再转写各段。
原始音频和待保存文本按临时状态处理，服务不会写入音频文件。

## 1. 准备运行环境和模型

在仓库根目录执行：

```bash
uv venv --python 3.10 services/speech/.venv
uv pip install --python services/speech/.venv/bin/python -r services/speech/requirements.txt
export SPEECH_MODEL_DIR="$PWD/services/speech/models"
mkdir -p "$SPEECH_MODEL_DIR/zipformer-zh"

zipformer_url=https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23/resolve/main
for file in tokens.txt {encoder,decoder,joiner}-epoch-99-avg-1.int8.onnx; do
  curl -fL "$zipformer_url/$file" -o "$SPEECH_MODEL_DIR/zipformer-zh/$file"
done

release_url=https://github.com/k2-fsa/sherpa-onnx/releases/download
curl -fL "$release_url/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2" |
  tar -xj -C "$SPEECH_MODEL_DIR"
file=3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
curl -fL "$release_url/speaker-recongition-models/$file" -o "$SPEECH_MODEL_DIR/$file"
```

这些模型文件的 SHA-256 如下。离线部署可在联网机器完成下载并校验后复制目录。
运行阶段只读取本地模型。

```text
8b294db9045d6e5f94647f4c1eec1af4da143a75053c399611444b378ff966ac  zipformer-zh/tokens.txt
1c556ea57cec304e55ec4b72e52c1cc098bb01476ed7d90f3de939fe126487b1  zipformer-zh/encoder-epoch-99-avg-1.int8.onnx
22f123bb8cba9b38974b3df18a3f45e7081f4985ebb2e075d9f21f618c468bbf  zipformer-zh/decoder-epoch-99-avg-1.int8.onnx
a7cf9d82757bdcf786059454495a9ca95e4bd7347f72473fc08d794475c36169  zipformer-zh/joiner-epoch-99-avg-1.int8.onnx
220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079  sherpa-onnx-pyannote-segmentation-3-0/model.onnx
1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b  3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
```

## 2. 启动和接入

在启动 ASR 的环境中配置至少 24 个字符的随机 `SPEECH_API_KEY`，并保留上一步的
`SPEECH_MODEL_DIR`。同机部署时可运行：

```bash
services/speech/.venv/bin/uvicorn services.speech.server:app \
  --host 127.0.0.1 --port 8002 --ws-max-size 65536
curl http://127.0.0.1:8002/health/ready
```

为 Kotaemon 设置 `KH_SPEECH_URL=ws://127.0.0.1:8002/recognize` 和与 ASR
一致的 `KH_SPEECH_API_KEY`，然后通过 `uv run --frozen python app.py` 或现有
启动脚本启动。浏览器需用本机地址或 HTTPS 并允许麦克风。反向代理需把
`/asr/live` 的 WebSocket 转发给 Kotaemon，SSO 的对应路径为 `/app/asr/live`。
浏览器使用一次性录音票据，服务密钥只配置在服务端。Kotaemon 的录音票据保存在
进程内，部署时使用单进程，或将同一浏览器会话的请求路由到同一实例。

## 3. 验收

使用两位说话人交替的连续录音，从浏览器麦克风录入或在测试中通过 ASR WebSocket
连续发送 PCM。包含至少一次无明显停顿的换人和同一人再次发言。停止后核对编号、
转写内容、最后一句和保存行为。保存前后分别切换会话，检查预览和已保存转写。
说话人编号是单次录音内的标签。
