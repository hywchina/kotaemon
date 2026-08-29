# /chat_fn 压力测试（精简）

此目录保留用于对 Kotaemon 服务的 `/chat_fn` 接口进行简单压力测试。

保留文件：

- `locustfile.py` — Locust 测试脚本（主脚本）
- `README.md` — 本说明（此文件）

已移除其它辅助脚本和多个文档文件以保持目录简洁。

## 快速运行

1. 激活虚拟环境：

```bash
source venv/bin/activate
```

2. 安装必要依赖：

```bash
pip install locust gradio-client
```

可用 `KH_PRESSURE_TEST_BASE_URL` 指定被测服务；结果写入
`pressure_output/chat_fn_results.csv`。

3. 启动 Locust Web UI：

```bash
locust -f locustfile.py
```

打开 `http://localhost:8089`，填写：

- Number of users: `10`
- Spawn rate: `2`
- Host: `http://localhost:7860`

或使用无头模式运行 2 分钟：

```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 2m --host http://localhost:7860
```

## 脚本说明

`locustfile.py` 使用 `gradio_client.Client` 直接调用 `/chat_fn`，包含两类任务：

- 简单单轮提问（权重 3）
- 带上下文的多轮对话（权重 2）

测试参数（并发用户数、孵化速率、运行时长）可在运行时调整。

## 验证服务连通性（可选）

在 Python 中快速验证：

```python
from gradio_client import Client
client = Client("http://localhost:7860/")
res = client.predict(chat_history=[("你好", None)], api_name="/chat_fn")
print(res)
```
