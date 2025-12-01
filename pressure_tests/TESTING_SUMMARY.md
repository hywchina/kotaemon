# 压力测试方案总结

## ✅ 可用方案: test_chat_fn_api

**状态**: 已验证可用  
**推荐指数**: ⭐⭐⭐⭐⭐

### 使用方法
```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_chat_fn_api
source /home/huyanwei/projects/kotaemon/venv/bin/activate
pip install -r requirements.txt
./run_test.sh
```

### 特点
- ✅ 无状态 API，适合压力测试
- ✅ 已验证可正常工作（响应时间 3-5 秒）
- ✅ 可获得完整 AI 回复
- ✅ 配置简单，易于使用

### 测试场景
1. 简单问题（权重 3）- 单轮对话
2. 上下文对话（权重 2）- 多轮对话

---

## ❌ 不可用方案: test_submit_msg

**状态**: API 限制，无法使用  
**推荐指数**: ⭐☆☆☆☆

### 问题原因

`/submit_msg` API 在设计上需要 Web UI 的会话状态：
- 需要 `user_id` 参数（用户 ID）
- 需要 `settings` 参数（设置状态）
- 需要 `conv_id` 参数（会话 ID）
- 需要 `request` 对象（Gradio Request）

这些参数在 Web UI 中通过 Gradio 状态组件自动注入，但在 API 调用时无法提供，导致服务端抛出异常。

### 技术细节

查看源码 `/home/huyanwei/projects/kotaemon/libs/ktem/ktem/pages/chat/__init__.py` 第 880 行：

```python
def submit_msg(
    self,
    chat_input,
    chat_history,
    user_id,        # ← 需要但 API 无法提供
    settings,       # ← 需要但 API 无法提供
    conv_id,        # ← 需要但 API 无法提供
    conv_name,
    first_selector_choices,
    request: gr.Request,  # ← 需要但 API 无法提供
):
```

### 验证结果
```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_submit_msg
python verify_locust.py
# 输出: 预期失败 - API 需要会话状态
```

---

## 📊 对比总结

| 特性 | test_chat_fn_api | test_submit_msg |
|------|------------------|-----------------|
| **可用性** | ✅ 可用 | ❌ 不可用 |
| **会话状态** | 不需要 | 需要（无法提供） |
| **API 调用** | 1 次 | 2 次（理论上） |
| **响应时间** | 3-5 秒 | N/A |
| **测试难度** | 简单 | 不可行 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐☆☆☆☆ |

---

## 🎯 最终建议

**使用 `test_chat_fn_api` 进行所有压力测试。**

这是唯一经过验证可正常工作的方案，能够模拟真实用户对话场景并获得完整的 AI 回复。

### 快速开始
```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_chat_fn_api
./run_test.sh
# 选择模式 1，访问 http://localhost:8089
```

---

## 📝 未来改进建议

如果需要测试 `/submit_msg` API，需要：
1. 修改服务端代码，使这些状态参数可选
2. 或在 `app.py` 中启用 `show_error=True` 查看详细错误
3. 或通过 Web UI 自动化（如 Selenium）模拟真实用户操作

但这些方案都比直接使用 `/chat_fn` API 复杂得多。
