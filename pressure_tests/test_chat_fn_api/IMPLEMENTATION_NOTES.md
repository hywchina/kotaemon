# 压力测试方案说明

## 概述

已为 Kotaemon AI 辅助诊断系统创建完整的压力测试方案，模拟 10 个并发用户同时使用系统。

## 核心变更

### 1. 选择了正确的 API 接口

**最初尝试：** `/submit_msg`
- 问题：需要会话状态（user_id, settings等），API调用时会出错
- 错误：`The upstream Gradio app has raised an exception`

**最终方案：** `/chat_fn`
- ✅ 无需复杂的会话状态管理
- ✅ 直接接受对话历史进行处理
- ✅ 返回完整的AI回复
- ✅ 更适合无状态的压力测试

### 2. 测试场景设计

**任务 1：简单问题（权重 3）**
- 单轮对话测试
- 测试基本响应能力
- 响应时间：约 3-5 秒

**任务 2：上下文对话（权重 2）**
- 多轮对话测试
- 测试上下文理解能力
- 模拟真实医疗对话场景

### 3. 文件结构

```
pressure_tests/
├── locustfile.py          # 主测试脚本
├── locust.conf            # 配置文件
├── requirements.txt       # 依赖项
├── run_test.sh           # 一键启动脚本
├── README_PRESSURE_TEST.md # 详细文档
├── QUICKSTART.md         # 快速开始指南
├── verify_locust.py      # 验证脚本
├── test_api.py           # API测试
├── test_simple.py        # 简单测试
├── test_chat_fn.py       # chat_fn接口测试
└── inspect_api.py        # API检查工具
```

## 测试配置

- **并发用户数：** 10
- **孵化速率：** 2 用户/秒
- **任务权重：** 简单问题(3) : 上下文对话(2)
- **等待时间：** 1-3 秒（任务之间）
- **目标服务：** http://localhost:7860

## 关键指标

监控以下指标评估系统性能：
1. **RPS** - 每秒请求数
2. **响应时间** - 中位数、95%、99%分位
3. **失败率** - 应低于 1%
4. **并发处理能力** - 10个用户同时使用

## 成功验证

已通过 `verify_locust.py` 验证：
- ✅ 简单问题测试通过（响应时间 ~4.6秒）
- ✅ 上下文对话测试通过（响应时间 ~3.6秒）
- ✅ API 调用格式正确
- ✅ 返回数据解析正常

## 使用方法

### 快速测试（推荐新手）
```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests
source /home/huyanwei/projects/kotaemon/venv/bin/activate
./run_test.sh
```

### Web UI 模式（推荐）
```bash
locust -f locustfile.py
# 访问 http://localhost:8089
```

### 命令行模式
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host http://localhost:7860 --html report.html
```

## 技术栈

- **Locust** - 负载测试框架
- **gradio_client** - Gradio API 客户端
- **Python** - 脚本语言

## 注意事项

1. 测试前确保 Kotaemon 服务正常运行
2. 注意观察系统资源使用情况（CPU、内存、GPU）
3. 首次测试建议从小规模开始（5个用户）
4. LLM 响应时间取决于模型和硬件配置
5. 测试期间避免其他重度任务

## 未来改进

1. 添加文件上传测试
2. 测试不同的 LLM 模型
3. 添加更复杂的对话场景
4. 集成性能监控（CPU、内存、GPU使用率）
5. 添加分布式测试支持（多机压测）

## 问题排查

如遇到问题，请：
1. 检查 `verify_locust.py` 是否通过
2. 查看 Kotaemon 服务日志
3. 检查系统资源是否充足
4. 阅读 `README_PRESSURE_TEST.md` 常见问题部分
