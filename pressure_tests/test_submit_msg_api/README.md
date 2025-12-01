# ⚠️ /submit_msg API 限制说明

## 重要提示

经过测试，`/submit_msg` API 在无状态调用时会失败，原因如下：

1. **需要会话状态**: 服务端的 `submit_msg` 函数需要 `user_id`、`settings`、`conv_id` 等参数
2. **状态注入问题**: 这些参数在 Web UI 中通过 Gradio 状态自动注入，但 API 调用无法提供
3. **服务端异常**: 调用时服务端抛出异常但未启用详细错误报告

## 推荐方案

**请使用 `test_chat_fn_api`** 进行压力测试，该方案：
- ✅ 无需会话状态
- ✅ 已验证可正常工作
- ✅ 适合无状态 API 压力测试
- ✅ 可以获得完整的 AI 回复

```bash
cd ../test_chat_fn_api
./run_test.sh
```

---

## 技术说明（仅供参考）

以下是 `/submit_msg` API 的技术细节，但由于上述限制，**不建议用于压力测试**。

## 快速开始

```bash
# 1. 激活虚拟环境
source /home/huyanwei/projects/kotaemon/venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 验证 API（重要！）
python verify_locust.py

# 4. 如果验证通过，运行压力测试
./run_test.sh
```

## 测试场景

### 任务 1: 简单消息工作流（权重 3）
完整流程测试，不含历史记录。

流程:
1. submit_msg: 提交 "你好，请介绍一下你的功能。"
2. chat_fn: 获取 AI 回复

### 任务 2: 带历史记录的工作流（权重 2）
在已有对话基础上继续。

流程:
1. submit_msg: 提交新消息（带历史）
2. chat_fn: 获取 AI 回复

## 文件说明

| 文件 | 说明 |
|------|------|
| `locustfile.py` | Locust 压力测试脚本 |
| `locust.conf` | Locust 配置文件 |
| `requirements.txt` | Python 依赖 |
| `run_test.sh` | 一键启动脚本 |
| `verify_locust.py` | API 验证脚本 |

## 测试配置

- **并发用户数:** 10
- **孵化速率:** 2 用户/秒
- **测试接口:** `/submit_msg` + `/chat_fn`（组合工作流）
- **目标服务:** http://localhost:7860

## API 工作流说明

### 步骤 1: 提交消息
```python
submit_result = client.predict(
    chat_input={"text": "消息内容", "files": []},
    chat_history=[],  # 对话历史
    conv_name="会话名称",
    first_selector_choices=[],
    api_name="/submit_msg"
)
# 返回: [input_box, chat_history, conv_list, conv_name, radio, files]
```

### 步骤 2: 获取 AI 回复
```python
chat_result = client.predict(
    chat_history=submit_result[1],  # 使用返回的对话历史
    llm_type="",
    use_citation="highlight",
    language="zh",
    param_11="disabled",
    param_12=[],
    api_name="/chat_fn"
)
# 返回: [chat_history_with_reply, evidence_html, visualization]
```

## 故障排除

### 问题: 工作流调用失败

**检查点:**
1. 运行 `python verify_locust.py` 验证工作流
2. 检查服务器日志
3. 确认两个 API 都可用

### 问题: submit_msg 返回格式不对

代码会自动处理并fallback到手动构建对话历史。

### 问题: 连接被拒绝

确保 Kotaemon 服务运行在 http://localhost:7860

## 运行模式

### 1. Web UI 模式（推荐）
```bash
./run_test.sh
# 选择 1，访问 http://localhost:8089
```

### 2. 命令行模式
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 2m --host http://localhost:7860
```

### 3. 生成报告
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host http://localhost:7860 --html report.html
```

## 成功标准

- ✅ 失败率 < 1%
- ✅ 平均响应时间 < 15秒（包含两次 API 调用）
- ✅ 95% 响应时间 < 30秒
- ✅ 系统稳定无崩溃

## 对比说明

### test_chat_fn_api vs test_submit_msg

| 特性 | test_chat_fn_api | test_submit_msg |
|------|------------------|-----------------|
| API 数量 | 1 个 | 2 个（组合） |
| 工作流 | 直接获取回复 | 提交 → 获取回复 |
| 响应时间 | 较快 | 较慢（两次调用） |
| 真实度 | 中等 | 高（模拟真实流程） |
| 推荐度 | ✅ 简单测试 | ✅ 完整测试 |

**选择建议:**
- 快速性能测试 → 使用 `test_chat_fn_api`
- 完整流程测试 → 使用 `test_submit_msg`
