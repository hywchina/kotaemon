# AI 辅助诊断系统

本项目基于 Kotaemon `v0.12.0`，保留上游的文档问答、MCP 与 PaddleOCR
能力，并增加医疗场景中文界面、共享知识库权限、模型配置和语音助手。

首次运行前复制环境变量模板并按实际模型服务修改：

```bash
cp .env.example .env
uv sync --frozen
./run.sh start
```

常用命令：

| 命令 | 说明 |
| --- | --- |
| `./run.sh start [端口]` | 后台启动，默认端口 7860 |
| `./run.sh foreground [端口]` | 前台启动，适合 Docker |
| `./run.sh stop` | 仅停止由该脚本启动的进程 |
| `./run.sh restart [端口]` | 重启服务 |
| `./run.sh status` | 查看应用与本地重排服务状态 |
| `./run.sh logs` | 查看应用与重排日志 |

默认使用 GeekAI 的 `qwen3-vl-flash`、`qwen3-vl-embedding` 和
`qwen3-rerank`。在 `.env` 中配置 `GEEKAI_API_KEY` 后即可使用；Embedding 与
Rerank 使用项目内的 GeekAI 协议适配器。ASR 不属于本次模型接入，可通过
`KH_ENABLE_ASR=false` 关闭。将 `KH_MODEL_PROFILE` 改为 `lmstudio` 可切换回原本
的本地模型配置。完整迁移说明见
[`docs/development/fork-migration-v0.12.md`](docs/development/fork-migration-v0.12.md)。
