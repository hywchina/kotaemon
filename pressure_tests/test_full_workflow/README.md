# 全流程压力测试

该脚本通过 Gradio API 模拟“登录 → 提交问题 → 生成回答 → 保存会话”的完整
流程，可分别测试普通问答和挂载共享知识库文件的问答。

## 运行

在仓库根目录启动应用后执行：

```bash
source venv/bin/activate
cd pressure_tests/test_full_workflow
locust -f locustfile.py --headless --users 3 --spawn-rate 1 --run-time 5m
```

也可以省略 `--headless`，然后访问 `http://localhost:8089` 配置并发参数。

脚本支持以下环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `KH_PRESSURE_TEST_BASE_URL` | `http://localhost:7860/` | 被测 Gradio 服务 |
| `KH_PRESSURE_TEST_USERNAME` | `admin` | 测试登录用户 |
| `KH_PRESSURE_TEST_PASSWORD` | `admin` | 测试登录密码 |
| `KH_PRESSURE_TEST_USE_KB` | `false` | 是否执行知识库问答任务 |

例如，开启知识库场景：

```bash
KH_PRESSURE_TEST_USE_KB=true \
KH_PRESSURE_TEST_PASSWORD='your-password' \
locust -f locustfile.py --headless --users 3 --spawn-rate 1 --run-time 5m
```

## 测试逻辑

- 普通模式执行单轮问答和两轮上下文问答。
- 知识库模式从索引 `1` 的 Source 表读取共享文件，向 `/submit_msg` 传递
  selector choices，并在 `/chat_fn` 中以 `select` 模式显式传入文件 ID。
- 每个任务创建独立会话，避免并发任务复用同一会话。
- 测试结果写入 `pressure_output/full_workflow_results_*.csv`，该目录不提交到
  Git。
- `verify_results.py` 会检查最近一小时的会话，并读取最新一份结果 CSV。

## 指标说明

CSV 包含提交耗时、AI 生成耗时、总耗时、估算 tokens/s、成功状态、知识库
文件和持久化状态。脚本结束时会追加一行聚合结果。

历史 `dev` 环境在 2025-12-07 的结果仅适合参考：单用户无知识库/有知识库
平均 AI 耗时约为 9.9 秒/32.7 秒；10 并发时约为 85.0 秒/274.1 秒。模型、
硬件和新基线均会显著影响结果，迁移后应重新建立性能基线。

## 注意事项

- 知识库模式要求索引 `1` 已有可检索文件；没有文件时相应任务会跳过。
- 该脚本包含数据库结果检查逻辑，因此应从本仓库环境运行。
- 不要在源码或命令历史中写入生产密码；通过环境变量注入。
