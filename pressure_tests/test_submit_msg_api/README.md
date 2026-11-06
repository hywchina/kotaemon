# Kotaemon /submit_msg API 压力测试

## 快速运行

```bash
# 启动压力测试（3个并发用户，持续30秒）
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_submit_msg_api
locust -f locustfile.py --headless --users 3 --spawn-rate 1 --run-time 30s --host http://localhost:7860

# 查看测试结果
cat submit_msg_results.csv
```

## 测试说明

此脚本**专门测试 `/submit_msg` API**，这是一个异步消息提交接口。

### API 特性

- **接口名称**: `/submit_msg`
- **类型**: 异步接口
- **功能**: 提交用户消息到系统，立即返回（不等待 AI 生成回复）
- **需要登录**: 是（admin/admin）
- **返回内容**: 会话ID、更新后的聊天历史等元数据

### 测试内容

1. **简单问题提交**（权重3）
   - 测试单次消息提交
   - 记录提交响应时间
   - 验证会话创建

2. **上下文对话提交**（权重2）
   - 测试多轮对话的会话持续性
   - 验证带历史记录的消息提交
   - 检查会话状态管理

### CSV 输出格式

文件名：`submit_msg_results.csv`

```csv
user_id, user_input, submit_duration_s, status, note
```

**字段说明：**
- `user_id`: 模拟用户ID
- `user_input`: 用户输入的问题（截断到100字符）
- `submit_duration_s`: 提交耗时（秒）
- `status`: success/failure
- `note`: 备注信息（如 conv_id、错误信息等）

### 重要说明

⚠️ **此测试只测量消息提交速度，不测量 AI 回复生成时间**

`/submit_msg` 是异步接口：
- ✅ 可测试：消息提交速度、会话管理、并发处理能力
- ❌ 不测试：AI 回复生成时间、回复内容质量

如需测试完整的对话流程（包括 AI 回复），请使用 `test_chat_fn_api`。

### 与 /chat_fn 的区别

| 特性 | /submit_msg | /chat_fn |
|-----|------------|----------|
| 类型 | 异步 | 同步 |
| 响应时间 | 快（仅提交） | 慢（等待AI生成） |
| AI回复 | 不包含 | 包含完整回复 |
| 适用场景 | 测试提交性能 | 测试端到端性能 |
| 需要登录 | 是 | 是 |

## 完整命令示例

```bash
# 小规模测试（3用户，30秒）
locust -f locustfile.py --headless --users 3 --spawn-rate 1 --run-time 30s --host http://localhost:7860

# 中规模测试（10用户，2分钟）
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 2m --host http://localhost:7860

# 高压测试（50用户，5分钟）
locust -f locustfile.py --headless --users 50 --spawn-rate 5 --run-time 5m --host http://localhost:7860

# Web UI 模式（可视化调整参数）
locust -f locustfile.py
# 访问 http://localhost:8089
```

## 测试结果示例

```csv
user_id,user_input,submit_duration_s,status,note
user_1234,你好，请介绍一下你的功能。,0.145,success,conv_id=abc123
user_5678,伴有气促，活动后加重。,0.132,success,conv_id=def456,context=yes
user_9012,如何使用这个系统？,0.158,success,conv_id=ghi789
AVERAGE,100 samples,0.145,98✓/2✗,success_rate=98.0%
```

## 性能指标

测试关注以下指标：

1. **提交响应时间**：消息提交到收到确认的时间
2. **成功率**：成功提交的请求占比
3. **并发能力**：系统能同时处理的提交请求数
4. **会话管理**：多轮对话的会话状态正确性

## 故障排查

### 常见错误

1. **NoResultFound 错误**
   - 原因：会话创建失败或数据库查询问题
   - 解决：检查登录状态、数据库连接

2. **登录失败**
   - 原因：用户名或密码错误
   - 解决：确认 admin/admin 凭据正确

3. **连接超时**
   - 原因：服务未启动或端口错误
   - 解决：确认 http://localhost:7860 可访问
