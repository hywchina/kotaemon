# ASR 服务部署、模型下载与 Kotaemon 接入手册

本文面向需要在另一台服务器部署整套 Kotaemon 的开发、实施和运维人员。文中命令
默认从 Kotaemon 仓库根目录执行，生产服务器以 Linux x86_64 为例。

> 重要：Git 仓库只包含 ASR 源码、锁定依赖、下载脚本和测试，不包含模型权重、
> `.env`、虚拟环境和声纹数据库。新服务器必须按本文下载模型，或从已联网构建机
> 复制模型包。

## 1. 服务边界与数据流

```text
浏览器麦克风
    │ Gradio 音频块
    ▼
Kotaemon :7860
    │ 带 X-ASR-API-Key 的 WebSocket/HTTP（仅服务端持有密钥）
    ▼
ASR API :8002
    ├── 流式 Paraformer：实时临时文本
    ├── 离线 Paraformer + FSMN-VAD + CT-Punc：最终文本和标点
    ├── CAM++：说话人向量
    ├── 会话内余弦聚类：speaker_00、speaker_01……
    └── SQLite 声纹库：把说话人编号映射为已注册姓名
```

ASR 是独立 FastAPI 服务，不依赖 Kotaemon 的 Python 包。接口契约见
[API.md](API.md)。Kotaemon 通过 `libs/ktem/ktem/asr/` 中的适配器调用该服务。

当前实现是“转写 + 说话人日志/聚类 + 声纹识别”，不是将重叠语音还原成多条独立
音轨的语音源分离。浏览器端静音检测负责提交话轮；一个提交的话轮对应一次说话人
向量和最终分段。多人同时说话、强混响和远场噪声仍需专项数据评估。

## 2. 资源要求

已验证的基线为 Python 3.10、FunASR 1.4.11、ModelScope 1.39.1 和 PyTorch 2.x。

| 项目 | 最低建议 | 同机运行整套 Kotaemon 的建议 |
| --- | --- | --- |
| CPU | 4 核 x86_64 | 8 核以上 |
| 内存 | ASR 独占 8 GB | 16 GB 以上 |
| 可用磁盘 | ASR 6 GB | 10 GB 以上，另计知识库数据 |
| GPU | 非必需，CPU 可运行 | 并发较高时使用经验证的 NVIDIA GPU |
| 音频输入 | 16 kHz、单声道、PCM16LE | 浏览器需允许麦克风权限 |

当前五套模型快照共 `2,107,861,851` 字节，约 1.963 GiB；加上 manifest 后整个
`models/` 目录约 2.0 GiB，ASR Python 环境约 1.2 GiB。CPU 运行时实测进程常驻
内存约 4 GiB，因此不要按模型文件大小估算内存。
模型首次加载可能需要数分钟，健康检查的启动宽限期应至少设为 180 秒。

GPU 部署需按服务器驱动和 CUDA 版本安装匹配的 PyTorch，不要直接复用其他机器的
`.venv`。当前 Dockerfile 是 CPU 基线，GPU 镜像应使用经过审批的 CUDA/PyTorch
基础镜像，并在上线前重新执行本手册的完整验证。

## 3. 模型清单

下载脚本 [scripts/preload_models.py](scripts/preload_models.py) 已固定模型 ID 和
revision，避免新服务器无意中获取不同版本。

| 目录 | 用途 | ModelScope 模型 ID | revision | 当前大小 |
| --- | --- | --- | --- | --- |
| `models/streaming-asr` | 实时临时文本 | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online` | `v2.0.4` | 889,359,342 B |
| `models/offline-asr` | 最终文本 | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | `v2.0.4` | 889,146,303 B |
| `models/vad` | 最终识别 VAD | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` | `v2.0.4` | 4,030,689 B |
| `models/punctuation` | 中文标点 | `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch` | `v2.0.4` | 296,363,070 B |
| `models/speaker` | CAM++ 说话人向量 | `iic/speech_campplus_sv_zh-cn_16k-common` | `v2.0.2` | 28,962,447 B |

模型来源和许可证链接见 [MODEL_LICENSES.md](MODEL_LICENSES.md)。每次重新下载后，
脚本都会生成未纳入 Git 的 `models/manifest.json`，记录依赖版本、模型 revision、
文件大小和 SHA-256。模型权重必须与该 manifest 一起归档。

## 4. 路线 A：联网服务器原生部署（推荐先走通）

### 4.1 获取指定代码

```bash
git clone --branch codex/migrate-dev-to-v0.12 \
  git@github.com:hywchina/kotaemon.git
cd kotaemon
git status --short --branch
```

没有仓库 SSH 权限时，使用组织批准的 HTTPS 地址或由发布人员提供的源码归档。部署
时应记录实际 commit：

```bash
git rev-parse HEAD
```

### 4.2 安装系统依赖

Ubuntu/Debian 示例：

```bash
sudo apt-get update
sudo apt-get install -y git curl ffmpeg libsndfile1 build-essential
```

安装 `uv` 后确认版本。生产环境也可以从内网软件源安装，但应固定并记录版本：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

### 4.3 创建独立 ASR 环境

```bash
cd asr_service
uv sync --frozen --extra funasr --no-dev
.venv/bin/python --version
```

`--frozen` 强制使用仓库中的 `uv.lock`。不要把 macOS、其他 CPU 架构或其他路径下
生成的 `.venv` 复制到服务器。

### 4.4 创建服务配置

```bash
umask 077
cp .env.example .env
openssl rand -hex 32
```

把最后一条命令生成的随机值填入 `ASR_API_KEY`。同机原生部署可保持以下关键值：

```dotenv
ASR_BACKEND=funasr
ASR_API_KEY=<随机生成的内部密钥>
ASR_HOST=127.0.0.1
ASR_PORT=8002
ASR_DATA_DIR=./data
ASR_OFFLINE=true
ASR_DEVICE=cpu
```

不要提交 `.env`。如果 ASR 与 Kotaemon 分开部署，将 `ASR_HOST` 改为受控内网监听
地址或 `0.0.0.0`，并使用防火墙只允许 Kotaemon 主机访问 8002；跨主机生产部署应
通过反向代理启用 TLS。

### 4.5 下载并校验模型

首次下载需要访问 ModelScope：

```bash
uv run --frozen --env-file .env python scripts/preload_models.py
```

该命令会依次下载五套固定 revision、生成 `models/manifest.json`，并实际加载所有
本地模型。只下载、不加载可执行：

```bash
uv run --frozen --env-file .env \
  python scripts/preload_models.py --download-only
```

确认目录和总体积：

```bash
du -sh models
find models -maxdepth 2 -type f \( -name 'model.pt' -o -name '*.bin' \) -ls
test -f models/manifest.json
```

完全断网条件下再次加载验证：

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --frozen --env-file .env \
  python scripts/preload_models.py --verify-only
```

只有看到五个本地目录全部加载成功，才能进入启动步骤。运行时的
[scripts/start_offline.sh](scripts/start_offline.sh) 会强制设置 Hugging Face 和
Transformers 离线模式，且 `ASR_OFFLINE=true` 时配置校验会拒绝缺失的模型目录。

### 4.6 启动服务

前台启动便于首次观察模型加载：

```bash
./scripts/start_offline.sh
```

另开终端检查：

```bash
curl --fail http://127.0.0.1:8002/health/live
curl --fail http://127.0.0.1:8002/health/ready
```

`/health/ready` 应返回 `status=ready`、`backend=funasr`，且五个模型字段都指向
`asr_service/models/` 下的本地绝对路径。该健康接口不需要密钥，但转写和声纹接口
需要密钥。

## 5. 路线 B：联网构建机下载，离线服务器部署

模型未进入 Git，离线服务器不能只执行 `git clone`。请在与目标机安全策略相符的
联网构建机完成第 4.1 至 4.5 节，然后打包模型。无需打包 `model-cache/` 和 `.venv/`。

### 5.1 构建模型传输包

在仓库根目录执行：

```bash
tar -C asr_service -czf asr-models-v2.0.4.tar.gz models
sha256sum asr-models-v2.0.4.tar.gz \
  > asr-models-v2.0.4.tar.gz.sha256
```

macOS 没有 `sha256sum` 时使用：

```bash
shasum -a 256 asr-models-v2.0.4.tar.gz \
  > asr-models-v2.0.4.tar.gz.sha256
```

传输物应包括：

- 与目标服务器架构匹配的源码 commit 或源码归档；
- `asr-models-v2.0.4.tar.gz` 及其 SHA-256 文件；
- Python/系统依赖的内网源、wheelhouse 或预构建 ASR 镜像；
- 模型卡、许可证审批记录和发布清单；
- 不含真实密钥的配置模板。

`.env`、患者音频和生产声纹数据库不得放入通用发布包。

### 5.2 离线服务器恢复模型

```bash
cd /opt/kotaemon
sha256sum -c asr-models-v2.0.4.tar.gz.sha256
tar -C asr_service -xzf asr-models-v2.0.4.tar.gz
test -f asr_service/models/manifest.json
```

通过批准的离线 Python 源安装锁定依赖，创建新的 `.env`，然后执行：

```bash
cd asr_service
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  uv run --frozen --env-file .env \
  python scripts/preload_models.py --verify-only
./scripts/start_offline.sh
```

不要在不同操作系统、CPU 架构或安装路径之间复制 `.venv`。如果使用离线
wheelhouse，应在与目标服务器相同的平台提前运行一次 `uv sync --offline` 和模型
加载测试。

## 6. Docker 部署 ASR

Dockerfile 是 CPU 基线。镜像只包含代码与 Python 依赖，`models/` 在运行时只读
挂载，因此更换权重不需要重建 2 GB 以上的镜像。

先按第 4.5 节在宿主机准备 `asr_service/models/` 和 `.env`，再执行：

```bash
cd asr_service
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f --tail=200 asr
```

验证宿主机发布端口：

```bash
curl --fail http://127.0.0.1:${ASR_PORT:-8002}/health/ready
```

停止服务不会删除权重和声纹库：

```bash
docker compose down
```

不要执行 `docker compose down -v` 删除生产持久化数据。当前 Compose 使用宿主机
目录 `./data` 保存声纹 SQLite，使用 `./models` 保存模型。若 Kotaemon 也运行在
容器中，`127.0.0.1` 指向 Kotaemon 容器自身，不能作为 ASR 地址。应把两个服务
加入同一私有 Docker 网络，并将 Kotaemon 的地址配置为 `http://asr:8002`；或通过
受控宿主机内网地址访问已发布的 8002 端口。

## 7. 使用 systemd 管理原生 ASR

确认前台启动和健康检查通过后，再创建 `/etc/systemd/system/kotaemon-asr.service`：

```ini
[Unit]
Description=Kotaemon local FunASR service
After=network.target

[Service]
Type=simple
User=<运行用户>
Group=<运行组>
WorkingDirectory=/opt/kotaemon/asr_service
ExecStart=/opt/kotaemon/asr_service/scripts/start_offline.sh
Restart=on-failure
RestartSec=5
TimeoutStartSec=300
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

路径和用户必须替换为服务器真实值。然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kotaemon-asr
sudo systemctl status kotaemon-asr
sudo journalctl -u kotaemon-asr -f
```

## 8. Kotaemon 接入

### 8.1 新部署、尚未初始化 Kotaemon 数据库

回到仓库根目录，把同一个 API Key 填入 Kotaemon 的 `.env`：

```dotenv
KH_ENABLE_ASR=true
KH_ASR_PROVIDER=local-funasr
KH_ASR_API_BASE_URL=http://127.0.0.1:8002
KH_ASR_API_KEY=<与 asr_service/.env 完全一致>
KH_ASR_MODEL=paraformer-campplus
KH_ASR_TIMEOUT=60
KH_ASR_VAD_RMS_THRESHOLD=500
KH_ASR_VAD_SILENCE_MS=700
KH_ASR_MIN_SPEECH_MS=400
```

先启动 ASR，再启动 Kotaemon：

```bash
curl --fail http://127.0.0.1:8002/health/ready
uv sync --frozen
./run.sh doctor
./run.sh start
```

Kotaemon 启动预检中的 ASR 项应显示 `[PASS]`。同机原生部署使用
`http://127.0.0.1:8002`；分机部署使用 ASR 的受控内网 URL；两个 Docker 容器使用
同一网络中的服务名，例如 `http://asr:8002`。

### 8.2 已经运行过 Kotaemon 或恢复了 `ktem_app_data`

ASR Provider 首次运行后会持久化到 Kotaemon 数据库，后续数据库配置优先于 `.env`。
仅修改 `.env` 可能不会切换当前 Provider。管理员需登录页面：

1. 打开“资源管理 → 语音识别模型”；
2. 供应商选择“本地 FunASR + 3D-Speaker”；
3. 模型名称填写 `paraformer-campplus`；
4. 接口地址填写可从 Kotaemon 服务端访问的 ASR URL；
5. 接口密钥填写 `asr_service/.env` 中的 `ASR_API_KEY`；
6. 点击“测试当前配置”，应提示本地 FunASR 已就绪；
7. 保存配置并重启 Kotaemon。

### 8.3 声纹注册

管理员在“资源管理 → 声纹库”中录制或上传样本。服务端只接受未压缩、16-bit PCM
WAV；单声道或双声道、8–96 kHz 均可，服务会转为 16 kHz 单声道。每个样本至少
1 秒，实际建议提供 3–10 秒、单人、无背景音乐的清晰语音。

声纹有两份关联数据，迁移时必须同时备份：

- `asr_service/data/voiceprints.sqlite3`：真实 CAM++ 向量和样本计数；
- `ktem_app_data/` 中的 Kotaemon 数据库：页面展示的姓名、Provider ID 和权限元数据。

只恢复其中一份会导致页面记录与 ASR 侧声纹不一致。

## 9. API 和端到端验证

先载入 ASR 密钥：

```bash
cd asr_service
set -a
source .env
set +a
```

### 9.1 鉴权和声纹 REST 接口

```bash
curl --fail \
  -H "X-ASR-API-Key: $ASR_API_KEY" \
  http://127.0.0.1:8002/v1/voiceprints
```

注册测试声纹（请替换为合规 WAV）：

```bash
curl --fail -X POST \
  -H "X-ASR-API-Key: $ASR_API_KEY" \
  -F 'display_name=部署测试人员' \
  -F 'files=@/path/to/voiceprint.wav;type=audio/wav' \
  http://127.0.0.1:8002/v1/voiceprints
```

测试完成后用返回的 ID 删除测试声纹：

```bash
curl --fail -X DELETE \
  -H "X-ASR-API-Key: $ASR_API_KEY" \
  http://127.0.0.1:8002/v1/voiceprints/<VOICEPRINT_ID>
```

### 9.2 WebSocket 转写

下载后的模型目录自带 16 kHz 单声道示例：

```bash
.venv/bin/python scripts/ws_client.py \
  models/offline-asr/example/asr_example.wav
```

应依次看到 `session_started`、若干 `segment` 和 `session_ended`，最终 segment 的
`is_final` 为 `true`。

多人评估脚本和已纳入仓库的 3D-Speaker 测试音频：

```bash
uv sync --frozen --extra funasr --group dev
uv run --frozen --env-file .env python scripts/evaluate_multispeaker_api.py
```

### 9.3 自动化测试

测试使用 mock backend，不加载真实模型：

```bash
uv sync --frozen --extra funasr --group dev
uv run --frozen pytest -q
```

Kotaemon 适配层测试在仓库根目录执行：

```bash
PYTHONPATH=. .venv/bin/pytest -q libs/ktem/ktem_tests/test_asr.py
```

最后在浏览器完成：麦克风授权、实时临时文本、停止后的最终文本、不同说话人编号、
已注册姓名匹配、声纹增删以及无权限用户不可维护声纹等检查。

## 10. 配置项说明

| 变量 | 默认/示例 | 说明 |
| --- | --- | --- |
| `ASR_BACKEND` | `funasr` | 生产必须为 `funasr`；`mock` 仅用于协议测试 |
| `ASR_API_KEY` | 无 | REST/WebSocket 共享密钥，不能为空 |
| `ASR_HOST` | `127.0.0.1` | 原生监听地址 |
| `ASR_PORT` | `8002` | 服务端口 |
| `ASR_DATA_DIR` | `./data` | 声纹 SQLite 目录，必须持久化并限制权限 |
| `ASR_OFFLINE` | `true` | 为 true 时所有模型配置必须是现存本地目录 |
| `ASR_DEVICE` | `cpu` | 可选 `cpu` 或已正确安装的 `cuda` 设备 |
| `ASR_SAMPLE_RATE` | `16000` | 当前管线固定为 16 kHz，不应修改 |
| `ASR_MAX_SPEAKERS` | `8` | 单会话最多聚类说话人数 |
| `ASR_CLUSTER_THRESHOLD` | `0.62` | 会话内说话人聚类余弦阈值 |
| `ASR_VOICEPRINT_THRESHOLD` | `0.72` | 已注册声纹匹配阈值 |
| `ASR_MAX_VOICEPRINT_SECONDS` | `60` | 单个声纹样本最大时长 |
| `ASR_ENCODER_CHUNK_LOOK_BACK` | `4` | 流式编码器回看块数 |
| `ASR_DECODER_CHUNK_LOOK_BACK` | `1` | 流式解码器回看块数 |

阈值是工程初始值，不是医疗场景验收结论。上线前应使用已授权、去标识化的本地数据
评估中文 CER、说话人 DER/聚类准确率、声纹 FAR/FRR、首字延迟、最终延迟和并发
资源占用，再冻结配置。

## 11. 备份、升级与回滚

备份前停止写入，至少备份两类数据：

```bash
sudo systemctl stop kotaemon-asr
tar -czf asr-data-backup.tar.gz asr_service/data
tar -czf kotaemon-data-backup.tar.gz ktem_app_data
sudo systemctl start kotaemon-asr
```

模型可以通过固定 revision 重新下载，但正式环境仍建议保存已审批的模型包、manifest
和整包 SHA-256。升级步骤：

1. 记录当前 Git commit、镜像标签、模型 manifest 和配置；
2. 备份 ASR 与 Kotaemon 两侧数据库；
3. 在脱敏测试环境安装新代码并执行所有测试；
4. 使用 `--verify-only` 加载模型；
5. 先启动 ASR 并通过 `/health/ready`，再启动 Kotaemon；
6. 失败时恢复旧代码/镜像及两侧匹配的数据库备份。

## 12. 常见故障

### `Offline model directories are missing`

`models/` 未下载、解压位置错误或 `.env` 的五个模型路径不正确。路径相对于
`asr_service/` 解析；执行 `find models -maxdepth 2 -type f` 和 `--verify-only` 检查。

### `/health/ready` 长时间连接失败

先查看进程日志。首次加载 CPU 模型较慢；确认内存没有被 OOM killer 回收、端口未
占用，且没有把 macOS/其他架构的虚拟环境复制过来。

### Kotaemon 提示 ASR 鉴权失败

确认 `KH_ASR_API_KEY` 与 `ASR_API_KEY` 完全一致，没有多余引号或空格。若 Kotaemon
已运行过，检查管理员页面中持久化的密钥，而不只是根目录 `.env`。

### 健康检查通过，但 Kotaemon 仍显示 Mock

数据库中仍是 `mock`。按第 8.2 节在管理员页面保存 `local-funasr`，然后重启
Kotaemon；运行中的 Provider 有进程级缓存，不重启不会完全切换。

### Docker 中无法访问 `127.0.0.1:8002`

容器的回环地址只指向自身。将服务加入同一 Docker 网络并使用 `http://asr:8002`，
或使用防火墙受控的宿主机内网地址。

### 有 speaker 编号但没有姓名

说话人聚类工作正常，但没有声纹达到 `ASR_VOICEPRINT_THRESHOLD`。检查声纹是否注册
在真实 Provider、录音是否清晰，并用验证集调参。不要为了让姓名出现而直接大幅
降低阈值，否则会增加误认风险。

### 同一人被分成多个 speaker，或多人被合并

检查话筒距离、环境噪声、话轮切分和 `ASR_CLUSTER_THRESHOLD`。该阈值越高，通常
越容易拆成更多说话人；越低，通常越容易合并。必须基于本地多人录音评估后调整。

## 13. 生产安全清单

- ASR 端口不暴露公网，只允许 Kotaemon 服务端访问；跨主机使用 TLS。
- 两边 `.env` 权限为 `600`，密钥不写入浏览器 JavaScript、日志或 Git。
- `data/voiceprints.sqlite3` 属于生物特征数据，应加密存储、审计增删并明确授权和
  保留周期。
- 模型权重、manifest、源码 commit、依赖锁文件和许可证审批必须可追溯。
- 备份和恢复时保证 Kotaemon 声纹元数据与 ASR 向量数据库成对一致。
- 上线前完成无效密钥、ASR 停机、模型加载失败、磁盘只读和内存不足演练。
- 生产阈值必须来自本地验证数据，不得把默认值当作医疗准确性承诺。
