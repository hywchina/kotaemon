# 完整用户流程压力测试

## 测试说明

此测试模拟真实用户使用 Kotaemon AI 辅助诊断系统的**完整会话流程**，包括：

1. **用户登录** (`/login_1`)
2. **提交消息** (`/submit_msg`) - 创建对话/会话，准备问题
3. **AI 生成回复** (`/chat_fn`) - 获取诊断建议
4. **数据持久化** - 保存完整对话到数据库（前端可见）

## 核心概念

### 会话 (Session/Conversation)
- **定义**: 一个用户在一个聊天窗口中的所有交互
- **特征**: 有唯一的 `conversation_id`，可包含多轮对话
- **前端表现**: 左侧历史记录中的一条记录
- **数据库**: `Conversation` 表中的一条记录

### 对话 (Dialog/Turn)
- **定义**: 用户提问一次 + AI 回答一次
- **特征**: 一个 `[question, answer]` 对
- **关系**: 一个会话包含多个对话
- **数据存储**: `Conversation.data_source['messages']` 数组中的一个元素

### 示例
```
会话 1: "病例分析-20231202"  (conversation_id: abc123)
  ├─ 对话 1: ["患者男性65岁", "建议检查心电图..."]
  ├─ 对话 2: ["有胸闷症状", "可能是冠心病..."]
  └─ 对话 3: ["既往病史高血压", "需要控制血压..."]

会话 2: "药物咨询-20231202"  (conversation_id: def456)
  └─ 对话 1: ["降压药副作用", "常见副作用包括..."]
```

## 与其他测试的区别

| 测试目录 | 测试内容 | 用途 |
|---------|---------|------|
| `test_chat_fn_api` | 仅测试 `/chat_fn` API | 测试 AI 生成性能 |
| `test_submit_msg_api` | 仅测试 `/submit_msg` API | 测试消息提交性能 |
| **`test_full_workflow`** | **完整用户流程** | **测试真实用户体验** |

## 测试场景

### 场景1: 简单问答（权重3）
- 用户提交单个问题
- AI 生成回复
- 保存到数据库
- **一个会话，一轮对话**

### 场景2: 多轮对话（权重2）
- 第一轮：用户提交初始问题 → AI 回复
- 第二轮：基于第一轮回复继续追问 → AI 结合上下文回复
- 保存完整对话历史
- **一个会话，两轮对话**（测试上下文理解能力）

## 为什么前端能看到历史记录？

### 数据流程
```
1. submit_msg → 创建 Conversation 记录（messages=[]）
2. chat_fn → 生成 AI 回复
3. _persist_to_db → 更新 Conversation.data_source['messages']
4. 前端刷新 → 从数据库读取对话列表
```

### 数据库结构
```python
Conversation:
  - id: "13aca8ade8fd4a33a3b7bb620cef1df6"
  - name: "病例分析-20231202"
  - user: "7edf5e4d99124b748b71337cf4f1dc0b"
  - data_source: {
      "messages": [
          ["患者男性65岁", "建议检查心电图..."],
          ["有胸闷症状", "可能是冠心病..."]
      ],
      "retrieval_messages": ["<h5>Evidence...</h5>", ...],
      "state": {...}
    }
```

### 前端查看
1. 打开 http://localhost:7860
2. 左侧"聊天会话"面板显示所有会话
3. 点击会话名称可查看完整对话历史
4. 测试产生的会话名称格式：
   - `Untitled - 2025-12-02 HH:MM:SS`（默认格式）
   - `压测_user_XXXX_时间戳`（自定义格式，如修改了 conv_name）

## 运行方式

### 1. 启动 Kotaemon 服务
```bash
cd /home/huyanwei/projects/kotaemon
python app.py
```

### 2. 运行压力测试

**Web UI 方式（推荐）：**
```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
locust -f locustfile.py --host=http://localhost:7860
```
然后访问 http://localhost:8089 设置参数：
- **Number of users**: 并发用户数（建议从 2-5 开始）
- **Spawn rate**: 每秒启动用户数
- **Host**: http://localhost:7860

**命令行方式：**
```bash
# 5个并发用户，每秒启动1个，运行60秒
locust -f locustfile.py --host=http://localhost:7860 \
  --users 5 --spawn-rate 1 --run-time 60s --headless
```

### Locust 参数说明

| 参数 | 说明 | 示例 |
|-----|------|------|
| `-f locustfile.py` | 指定测试脚本文件 | 必须参数 |
| `--host` | 目标服务器地址 | `http://localhost:7860` |
| `--users` | **总并发用户数** | `10` = 10个用户同时在线 |
| `--spawn-rate` | **每秒启动用户数** | `2` = 每秒启动2个用户 |
| `--run-time` | **测试运行时长** | `60s`, `5m`, `2h` |
| `--headless` | 无界面模式（纯命令行） | 适合自动化测试 |

### 常见测试场景

#### 场景1: 10个用户同时使用系统（持续运行）
```bash
# 10个用户，每秒启动2个，运行5分钟
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 2 --run-time 5m --headless
```
- 第1秒：启动 user_1, user_2
- 第2秒：启动 user_3, user_4
- 第3秒：启动 user_5, user_6
- ...
- 第5秒：全部10个用户启动完毕
- 之后持续运行5分钟，每个用户会根据权重随机执行任务

#### 场景2: 10个用户各执行一次测试（快速测试）
```bash
# 10个用户，快速启动，运行30秒后停止
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 5 --run-time 30s --headless
```

#### 场景3: 每个用户执行固定次数的对话
**当前脚本不支持控制具体次数**，因为 Locust 按时间运行，不按次数。

**如需每人恰好2轮对话，需要修改脚本：**
1. 移除 `@task` 装饰器的权重
2. 在 `on_start` 中执行固定任务
3. 使用 `--users 10` 但不设置 `--run-time`

**推荐方式（不修改代码）：**
```bash
# 10个用户，快速启动，运行20秒
# 由于场景2（多轮对话）权重是2，平均每个用户会执行1-2次多轮对话
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 5 --run-time 20s --headless
```

### 任务执行逻辑

当前脚本配置：
- **场景1（简单问答）**: 权重3 → 60%概率被选中
- **场景2（多轮对话）**: 权重2 → 40%概率被选中
- 每个用户在 `wait_time = between(2, 5)` 秒后执行下一个任务

**执行示例（1个用户运行30秒）：**
```
0s:  用户启动
2s:  执行简单问答（场景1）→ 耗时3秒
5s:  等待3秒
8s:  执行多轮对话（场景2）→ 耗时6秒
14s: 等待4秒
18s: 执行简单问答（场景1）→ 耗时3秒
21s: 等待2秒
...
30s: 测试结束
```

### 针对你的需求

> **需求: 10个用户同时使用，每人新建一次会话，每次会话2轮对话**

#### 方案A: 使用现有脚本（推荐）
```bash
# 10个用户，每人会执行场景2（多轮对话），大约20-30秒完成
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 10 --run-time 30s --headless
```

**预期结果：**
- 10个用户几乎同时启动（1秒内）
- 由于场景2权重为2，大部分用户会执行多轮对话
- 每个多轮对话包含2轮对话
- 30秒内每个用户至少执行1次，部分用户可能执行2-3次

#### 方案B: 精确控制（需要修改代码）
如果需要**每个用户恰好执行1次、恰好2轮对话**，创建新脚本：

```bash
# 创建精确测试脚本
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
cat > locustfile_exact.py << 'EOF'
# 每个用户恰好执行一次2轮对话
from locust import User, events
from gradio_client import Client
import time

class OneTimeUser(User):
    def on_start(self):
        """每个用户启动时执行一次"""
        client = Client("http://localhost:7860/")
        client.predict(usn="admin", pwd="admin", api_name="/login_1")
        
        # 第一轮对话
        submit1 = client.predict(
            chat_input={"text": "患者男性65岁", "files": []},
            chat_history=[],
            conv_name=f"精确测试_{time.time()}",
            first_selector_choices=[],
            api_name="/submit_msg"
        )
        chat1 = client.predict(
            chat_history=submit1[1],
            llm_type="", use_citation="highlight",
            language="zh", param_11="disabled", param_12=[],
            api_name="/chat_fn"
        )
        
        # 第二轮对话
        submit2 = client.predict(
            chat_input={"text": "有胸闷症状", "files": []},
            chat_history=chat1[0],
            conv_name=f"精确测试_{time.time()}",
            first_selector_choices=[],
            api_name="/submit_msg"
        )
        chat2 = client.predict(
            chat_history=submit2[1],
            llm_type="", use_citation="highlight",
            language="zh", param_11="disabled", param_12=[],
            api_name="/chat_fn"
        )
        
        print(f"✓ 用户完成2轮对话")
        self.environment.runner.quit()  # 完成后退出
EOF

# 运行精确测试
locust -f locustfile_exact.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 2 --headless
```

### 推荐设置总结

根据不同测试目标，推荐以下配置：

| 测试目标 | 命令示例 | 说明 |
|---------|---------|------|
| **快速验证** | `--users 2 --spawn-rate 1 --run-time 20s` | 2个用户测试基本功能 |
| **轻度负载** | `--users 5 --spawn-rate 1 --run-time 2m` | 5个用户模拟正常使用 |
| **中度负载** | `--users 10 --spawn-rate 2 --run-time 5m` | 10个用户测试并发性能 |
| **重度负载** | `--users 20 --spawn-rate 2 --run-time 10m` | 20个用户压力测试 |
| **极限测试** | `--users 50 --spawn-rate 5 --run-time 5m` | 找出系统瓶颈 |
| **精确测试** | `--users 10 --spawn-rate 10 --run-time 30s` | 10个用户同时执行 |

**参数选择建议：**
- `spawn-rate` 不要设置太大，避免瞬间压力导致全部失败
- 首次测试从小规模开始（2-5用户），逐步增加
- 观察 CPU/GPU 使用率和响应时间，找到系统最佳并发数
- 如需精确控制执行次数，使用方案B创建自定义脚本

## 结果分析

### 1. Locust Web 界面
- 查看实时请求统计
- 观察响应时间分布
- 监控失败率

### 2. CSV 文件分析
结果保存在 `full_workflow_results.csv`，包含：

| 列名 | 说明 |
|-----|------|
| `user_id` | 模拟用户 ID |
| `user_input` | 用户提交的问题 |
| `ai_response` | AI 的回复内容（前200字） |
| `submit_duration_s` | 提交消息耗时 |
| `ai_duration_s` | AI 生成回复耗时 |
| `total_duration_s` | 总耗时（端到端） |
| `tokens_per_s` | 生成速度（估算） |
| `status` | success / failure |
| `note` | 备注信息（如 conv_id） |

最后一行是统计汇总：
- 平均提交时间
- 平均 AI 响应时间
- 平均总时间
- 平均生成速度
- 成功率

### 3. 验证数据持久化

**使用验证工具（推荐）：**
```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
python verify_results.py
```

验证工具会自动检查：
- 数据库中的测试会话记录
- CSV 文件中的测试结果
- 提供详细的数据统计和前端查看指引

**手动验证：**
访问前端 http://localhost:7860 检查：
- 左侧是否出现测试对话记录
- 对话历史是否正确保存
- 可以打开历史对话查看内容
- 记录中应包含测试问题和 AI 的完整回复

## 性能指标参考

根据不同硬件配置，参考值如下：

| 指标 | 良好 | 可接受 | 需优化 |
|-----|------|--------|--------|
| 平均总响应时间 | < 5s | 5-10s | > 10s |
| 成功率 | > 95% | 85-95% | < 85% |
| 平均生成速度 | > 30 tokens/s | 15-30 tokens/s | < 15 tokens/s |

## 注意事项

1. **系统要求**：确保 Kotaemon 服务正常运行（http://localhost:7860）
2. **并发控制**：首次测试建议从 2-5 个用户开始，避免系统过载
3. **登录凭据**：默认使用 admin/admin，如有修改请更新脚本
4. **AI 模型**：测试时长受 AI 模型响应速度影响，确保模型服务正常
5. **数据库**：多轮测试会产生大量对话记录，定期清理数据库
6. **Python 路径**：脚本会自动添加项目路径到 `sys.path`，确保能导入数据库模块
7. **数据持久化**：测试会直接操作数据库保存对话，确保有数据库写权限

## 故障排查

### 问题1: NoResultFound 错误
**原因**: 数据库中没有用户记录  
**解决**: 确保已登录（脚本会自动处理）

### 问题2: 响应时间过长
**原因**: AI 模型性能不足或并发过高  
**解决**: 
- 减少并发用户数
- 检查 GPU/CPU 使用率
- 优化 AI 模型配置

### 问题3: 数据未保存到数据库
**原因**: 数据库模块导入失败或连接问题  
**解决**: 
- 检查日志中是否有 "✓ 数据库模块导入成功" 消息
- 如显示 "数据库不可用"，检查项目路径是否正确
- 查看 CSV 中 `note` 列是否包含 `persisted=yes`
- 运行 `verify_results.py` 验证数据库状态
- 确认数据库文件有写权限

### 问题4: CSV 文件为空或缺失
**原因**: 测试未正常完成或文件权限问题  
**解决**: 
- 确保测试运行完成（Ctrl+C 前等待统计）
- 检查目录写权限
- 查看终端日志确认记录操作

## 扩展测试

### 测试文件上传功能
修改 `chat_input` 参数：
```python
chat_input={
    "text": question,
    "files": ["/path/to/test/document.pdf"]
}
```

### 测试不同 AI 参数
修改 `chat_fn` 参数：
```python
settings={"temperature": 0.7, "max_tokens": 2048},
reasoning_type="chain_of_thought",
```

### 测试更复杂的对话
在 `conversation_templates` 中添加更多模板，模拟真实医疗咨询场景。

## 测试成功示例

### 日志输出
```
[INFO] ✓ 数据库模块导入成功
[INFO] ✓ 用户 user_4389 登录成功
[INFO] 开始保存对话 13aca8ade8fd4a33a3b7bb620cef1df6，消息数: 2
[INFO] 找到对话记录，当前消息数: 0
[INFO] ✓ 成功保存对话 13aca8ade8fd4a33a3b7bb620cef1df6，新消息数: 2
[INFO] ✓ user_4389 完成上下文对话 | 提交:135ms + AI:5.86s = 总计:6.02s | 116.1 tokens/s
```

### CSV 记录示例
```csv
user_id,user_input,ai_response,submit_duration_s,ai_duration_s,total_duration_s,tokens_per_s,status,note
user_4389,既往有高血压病史10年...,根据提供的额外信息...,0.135,5.862,6.016,116.06,success,"conv_id=13aca8ade8fd4a33a3b7bb620cef1df6,persisted=yes"
```

### 验证工具输出
```
✓ 数据库有效会话: 5
✓ CSV 测试记录: 102
🎉 测试数据已成功保存，前端应该能看到历史记录！
```

### 前端效果
- 左侧会话列表显示：`Untitled - 2025-12-02 17:43:47`
- 点击后显示完整对话：
  - 问："既往有高血压病史10年，服药不规律。"
  - 答：完整的 AI 医疗建议内容

## 联系与反馈

如有问题或建议，请查看项目文档或提交 Issue。


------
### 最终性能指标测试：
技术服务工作成果的验收标准： 
（1）功能完整性标准：系统软件功能需100%覆盖附件一所列功能，可实现病例数据录入、统计分析模型运行、科研报告生成等核心功能。自定义功能模块需满足甲方要求，无功能缺失或逻辑错误。 
（2）性能指标标准：单用户操作核心功能的平均响应时间≤5秒。支持≥10个科研用户同时在线操作，且系统无卡顿，数据无丢失。对10条医学样本数据（含结构化病例数据、影像数据、脑电数据等）的批量导入时间≤3分钟，数据解析准确率≥99.9%。 
（3）数据安全与合规性标准：患者隐私数据需采用加密算法存储，传输过程也需加密，符合《中华人民共和国个人信心保护法》和《信息安全技术-健康医疗数据安全指南》（GB/T39725-2020）的要求。实现三级用户权限的精准管控，权限配置需按甲方需求一致，无越权访问漏洞。软件数据接口需通过甲方科研伦理委员会的合规性审核。
（4）兼容性和稳定性标准：支持在Windows 10/11、macOS12及以上系统运行，兼容Chromem 90+、Edge 90+浏览器。连续72小时满负荷运行无崩溃、无数据异常、系统日志无ERROR级别错误记录。 
（5）文档完整性标准：交付的技术文档需包含：可运行软件安装包（含版本号）及完整源代码（需注释率≥80%）；《软件测试报告》（含500条测试用例及通过率100%的验证记录）；《用户操作手册》（含医学科研场景下的操作流程图、常见问题解答）；《数据安全维护手册》（含数据备份、应急处理流程）。


目标1：单用户核心功能平均响应时间 ≤ 5 秒
目标2：≥10 个科研用户同时在线操作，系统无卡顿、数据无丢失
测试命令

单用户时延基线（核心功能端到端）
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
locust -f locustfile.py --host=http://localhost:7860 \
  --users 1 --spawn-rate 1 --run-time 60s --headless

10用户并发（稳定长测，推荐）
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 2 --run-time 5m --headless

10用户并发（快速验证）
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 10 --run-time 60s --headless

10用户持续测试（更强置信度）
cd /home/huyanwei/projects/kotaemon/pressure_tests/test_full_workflow
locust -f locustfile.py --host=http://localhost:7860 \
  --users 10 --spawn-rate 2 --run-time 10m --headless
  
通过标准（检查项）

时延：CSV full_workflow_results.csv 中 total_duration_s 平均值 ≤ 5.00（单用户与10用户）
稳定性：Locust汇总“# fails”为0或＜5%；CSV“AVERAGE”行成功率 ≥ 95%
数据无丢失：CSV note 列均含 persisted=yes；verify_results.py 能列出最近会话且每个会话 messages ≥ 1
验证步骤（运行后执行）