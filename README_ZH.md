# AI 辅助诊断系统

本项目基于 Kotaemon `v0.12.0`，保留上游的文档问答与 PaddleOCR 能力，并增加
医疗场景中文界面、共享知识库权限、模型配置和语音助手。

医院环境首次运行前复制专用模板，替换管理员密码和模型密钥，并先执行自检：

```bash
cp .env.hospital.example .env
# 编辑 .env 后继续
uv sync --frozen
./run.sh doctor
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
| `./run.sh doctor` | 检查模型出口、密钥占位符、离线资源和数据目录 |

`start`、`restart` 和 `foreground` 会先运行不访问模型接口的 `doctor`，检查首次
管理员、网络出口、离线资源和数据目录；通过后再依次向当前默认的 LLM、Embedding
和 Rerank 发起最小测试请求。任一必需检查失败都会阻止页面启动，ASR 当前为 Mock
Provider，启动时会明确显示跳过。后台启动还会等待页面 HTTP 就绪，默认最长 90 秒，
可通过 `KH_APP_START_TIMEOUT` 调整。

默认使用 GeekAI 的 `qwen3-vl-flash`、`qwen3-vl-embedding` 和
`qwen3-rerank`。在 `.env` 中配置 `GEEKAI_API_KEY` 后即可使用；Embedding 与
Rerank 使用项目内的 GeekAI 协议适配器。ASR 当前使用 Mock Provider 演示实时
多说话人转写，可通过 `KH_ENABLE_ASR=false` 关闭。将 `KH_MODEL_PROFILE` 改为
`lmstudio` 可切换回原本的本地模型配置。完整迁移说明见
[`docs/development/fork-migration-v0.12.md`](docs/development/fork-migration-v0.12.md)，
医院离线构建、部署、备份和回滚见
[`docs/deployment/hospital-intranet.md`](docs/deployment/hospital-intranet.md)。
