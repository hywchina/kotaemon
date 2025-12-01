# Kotaemon 压力测试

本目录包含针对 Kotaemon AI 辅助诊断系统的压力测试工具。

## 测试目标

模拟 **10 个并发用户**同时使用系统，对 `/chat_fn` 接口进行压力测试。

## 文件说明

- `locustfile.py` - Locust 压力测试脚本
- `locust.conf` - Locust 配置文件
- `requirements.txt` - 测试依赖项
- `run_test.sh` - 一键启动测试脚本
- `README_PRESSURE_TEST.md` - 本文档
- `test_api.py` - API 参数格式测试脚本
- `test_simple.py` - 简单 API 测试脚本
- `test_chat_fn.py` - chat_fn 接口测试脚本

## 快速开始

### 1. 确保服务运行

确保 Kotaemon 服务已启动并运行在 `http://localhost:7860`

### 2. 安装依赖

```bash
# 激活虚拟环境
source /home/huyanwei/projects/kotaemon/venv/bin/activate

# 安装测试依赖
pip install -r requirements.txt
```

### 3. 运行测试

#### 方式 1: 使用启动脚本（推荐）

```bash
chmod +x run_test.sh
./run_test.sh
```

然后选择运行模式：
- **模式 1 (Web UI)**: 打开 http://localhost:8089 进行可视化测试
- **模式 2 (命令行)**: 快速运行 2 分钟测试
- **模式 3 (无头模式)**: 自动运行 5 分钟并生成 HTML 报告

#### 方式 2: 手动运行

**Web UI 模式（推荐）:**
```bash
locust -f locustfile.py --config=locust.conf
```
访问 http://localhost:8089，在界面中设置用户数和孵化速率。

**命令行模式:**
```bash
# 运行 10 个用户，每秒孵化 2 个，持续 5 分钟
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host http://localhost:7860
```

**生成 HTML 报告:**
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host http://localhost:7860 --html report.html
```

## 测试场景

### 任务 1: 简单问题 (权重: 3)
模拟用户发送简单的问题并获取AI回复。

示例问题：
- "你好，请介绍一下你的功能。"
- "你能帮我做什么？"
- "如何使用这个系统？"

### 任务 2: 带上下文对话 (权重: 2)
模拟用户进行多轮对话，测试系统处理上下文的能力。

示例对话：
- 第一轮："患者男性，65岁，主诉胸闷3天。" 
  回复："请问有其他症状吗？"
- 第二轮："伴有气促，活动后加重。"
  (获取AI分析)

## 自定义配置

### 修改并发用户数

编辑 `locust.conf`:
```conf
users = 20  # 修改为 20 个并发用户
spawn-rate = 5  # 每秒孵化 5 个用户
```

或在命令行中指定：
```bash
locust -f locustfile.py --users 20 --spawn-rate 5
```

### 修改测试消息

编辑 `locustfile.py` 中的 `test_questions` 和 `conversation_templates` 列表，添加或修改测试问题和对话模板。

### 修改等待时间

在 `locustfile.py` 的 `GradioUser` 类中修改：
```python
wait_time = between(1, 3)  # 用户任务间隔 1-3 秒
```

## 监控指标

测试过程中可以观察以下指标：

- **请求数 (Requests)**: 总请求次数
- **失败数 (Failures)**: 失败请求次数
- **响应时间 (Response Time)**: 
  - 平均响应时间
  - 中位数
  - 95百分位
  - 99百分位
- **RPS (Requests Per Second)**: 每秒请求数
- **并发用户数 (Users)**: 当前活跃用户数

## 测试结果分析

### 成功标准
- ✅ 失败率 < 1%
- ✅ 平均响应时间 < 10秒
- ✅ 95百分位响应时间 < 20秒
- ✅ 所有用户能够正常完成对话

### 常见问题

**Q: 测试时出现大量失败**
A: 检查服务是否正常运行，检查系统资源（CPU、内存、GPU）是否充足。

**Q: 响应时间过长**
A: 可能是 LLM 推理速度较慢，考虑：
- 优化模型配置
- 使用更强的硬件
- 减少并发用户数

**Q: 连接被拒绝**
A: 确保 Gradio 服务在 http://localhost:7860 上运行。

## API 接口说明

### /chat_fn

本测试使用 `/chat_fn` 接口，这是一个完整的聊天接口，可以处理对话历史并返回AI响应。

**请求参数:**
- `chat_history`: List[Tuple] - 对话历史记录，格式为 [(用户消息, AI回复), ...]
  - 最后一条可以是 (用户消息, None) 表示等待AI回复
- `llm_type`: str - 语言模型类型（留空使用默认模型）
- `use_citation`: str - 引用样式 ('highlight', 'inline', 'off')
- `language`: str - 语言 ('zh', 'en')
- `param_11`: str - 选择器状态
- `param_12`: List - 文件列表

**返回值:**
返回包含 3 个元素的元组：
1. 更新后的对话历史（包含AI回复）
2. HTML格式的检索信息
3. 可视化图表数据

### 为什么使用 /chat_fn 而不是 /submit_msg？

`/submit_msg` 接口需要更多的会话状态管理，包括 user_id、settings 等参数。这些参数在Web界面中由Gradio自动管理，但在API调用时可能导致问题。

`/chat_fn` 接口更加独立，只需要对话历史和配置参数，更适合压力测试场景。

## 高级用法

### 分布式测试

如需更大规模测试，可以使用 Locust 的分布式模式：

```bash
# Master 节点
locust -f locustfile.py --master --master-bind-host=0.0.0.0

# Worker 节点（可在多台机器运行）
locust -f locustfile.py --worker --master-host=<master-ip>
```

### 自定义测试场景

在 `locustfile.py` 中添加新的 `@task` 方法来定义更多测试场景。

### 性能基准测试

运行多次测试并记录结果，建立性能基准：

```bash
for i in {1..5}; do
    echo "运行第 $i 次测试..."
    locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 3m --host http://localhost:7860 --html report_$i.html
    sleep 10
done
```

## 注意事项

1. 测试前确保系统资源充足
2. 不要在生产环境运行高强度压力测试
3. 注意观察服务器日志和系统监控
4. 测试结束后检查生成的报告文件
5. 根据实际业务场景调整测试参数

## 技术支持

如有问题，请参考：
- Locust 官方文档: https://docs.locust.io/
- Gradio Client 文档: https://www.gradio.app/docs/python-client
