# Kotaemon 压力测试

本目录包含 Kotaemon AI 辅助诊断系统的压力测试工具。

## 目录结构

```
pressure_tests/
├── README.md                    # 本文件
├── test_chat_fn_api/           # /chat_fn API 压力测试（推荐）
│   ├── locustfile.py           # Locust 测试脚本
│   ├── locust.conf             # 配置文件
│   ├── requirements.txt        # 依赖项
│   ├── run_test.sh             # 启动脚本
│   ├── verify_locust.py        # 验证脚本
│   ├── README.md               # 说明文档
│   ├── README_PRESSURE_TEST.md # 详细文档
│   ├── QUICKSTART.md           # 快速开始
│   └── IMPLEMENTATION_NOTES.md # 实现说明
└── test_submit_msg/            # /submit_msg API 压力测试
    ├── locustfile.py           # Locust 测试脚本
    ├── locust.conf             # 配置文件
    ├── requirements.txt        # 依赖项
    ├── run_test.sh             # 启动脚本
    ├── verify_locust.py        # 验证脚本
    └── README.md               # 说明文档
```

## 快速开始

### 测试 /chat_fn API（推荐）

```bash
cd test_chat_fn_api
source /home/huyanwei/projects/kotaemon/venv/bin/activate
pip install -r requirements.txt
./run_test.sh
```

### 测试 /submit_msg API（不推荐 - 有限制）

⚠️ **注意**: `/submit_msg` API 需要 Web UI 会话状态，无法通过 API 直接调用。

```bash
cd test_submit_msg
# 查看限制说明
cat README.md
```

**建议使用 `test_chat_fn_api` 代替。**

详细说明请查看各子目录的 README 文件。

## 测试目标

模拟 **10 个并发用户**同时使用系统，评估系统性能和稳定性。

## API 接口说明

查看 Gradio API 文档：http://localhost:7860/?view=api

**可用的测试接口：**
- ✅ `/chat_fn` - 聊天对话接口（**推荐**，已验证可用）

**不可用的接口：**
- ❌ `/submit_msg` - 提交消息接口（需要 Web UI 会话状态，API 调用会失败）

## 推荐方案

**强烈建议使用 `test_chat_fn_api`** 进行压力测试：
- ✅ 无状态 API，适合压力测试
- ✅ 已验证可正常工作
- ✅ 可获得完整 AI 回复
- ✅ 响应时间更快