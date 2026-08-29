# AI 辅助诊断系统

本项目基于 Kotaemon `v0.12.0`，保留上游的文档问答、MCP 与 PaddleOCR
能力，并增加医疗场景中文界面、共享知识库权限、本地模型配置和语音助手。

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

默认使用 OpenAI 兼容的本地 LLM/Embedding 服务。本地重排服务默认不自动启动；
准备好模型后，将 `KH_START_LOCAL_RERANK` 设为 `true`。完整迁移说明见
[`docs/development/fork-migration-v0.12.md`](docs/development/fork-migration-v0.12.md)。
