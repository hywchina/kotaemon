| 命令                         | 说明               |
| -------------------------- | ---------------- |
| `bash run.sh --start`      | 启动服务，默认端口 7860   |
| `bash run.sh --start 7861` | 启动服务并指定端口        |
| `bash run.sh --stop`       | 停止正在运行的服务        |
| `bash run.sh --restart`    | 重启服务             |
| `bash run.sh --status`     | 查看服务是否运行、PID、端口  |
| `bash run.sh --log`        | 查看实时日志（自动选取当天日志） |
| `bash run.sh --help`       | 查看帮助菜单           |

## 本地安装

使用 Python 3.10 和 uv。在仓库根目录执行 `uv sync --frozen`，再用 `bash run.sh --start` 启动。
直接运行应用可用 `uv run --frozen python app.py`，并配置一个可用的重排序服务。

聊天和嵌入默认使用 LM Studio。本机运行时可将 `LM_STUDIO_BASE_URL` 设为
`http://127.0.0.1:1234/v1`。模型名和密钥可按 `.env.example` 配置。
本地重排通过 `RERANK_MODEL_PATH` 指定模型目录，或使用 `conf/rerank_models.json`。
部署时保留仓库内的 PDF.js、NLTK 和 Tiktoken 资源，以便加载对应功能。
