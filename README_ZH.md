| 命令                         | 说明               |
| -------------------------- | ---------------- |
| `bash run.sh --start`      | 启动服务，默认端口 7860   |
| `bash run.sh --start 8001` | 启动服务并指定端口        |
| `bash run.sh --stop`       | 停止正在运行的服务        |
| `bash run.sh --restart`    | 重启服务             |
| `bash run.sh --status`     | 查看服务是否运行、PID、端口  |
| `bash run.sh --log`        | 查看实时日志（自动选取当天日志） |
| `bash run.sh --help`       | 查看帮助菜单           |

ai-diagnosis 3个模型
1. lm，flowsettings.py 设置默认的
2. embedding ，flowsettings.py 设置默认的
3. rerank ，写死的

parse-data 1 个模型
1. lm ，通过 conf 配置的