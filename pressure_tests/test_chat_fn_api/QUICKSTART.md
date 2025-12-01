# 快速开始指南

## 1. 安装依赖

```bash
cd /home/huyanwei/projects/kotaemon/pressure_tests
source /home/huyanwei/projects/kotaemon/venv/bin/activate
pip install -r requirements.txt
```

## 2. 验证 API 连接

```bash
python verify_locust.py
```

应该看到两个测试都通过。

## 3. 运行压力测试

### 方式 A: 使用启动脚本（推荐）

```bash
./run_test.sh
```

选择模式 1（Web UI）并访问 http://localhost:8089

### 方式 B: 直接运行 Locust

**Web UI 模式：**
```bash
locust -f locustfile.py
```
访问 http://localhost:8089，输入：
- Number of users: 10
- Spawn rate: 2
- Host: http://localhost:7860

**命令行模式（运行 2 分钟）：**
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 2m --host http://localhost:7860
```

**生成 HTML 报告：**
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host http://localhost:7860 --html report.html
```

## 4. 观察测试结果

Web UI 中可以看到：
- **RPS** (每秒请求数)
- **Response Time** (响应时间)
  - Median (中位数)
  - 95th percentile
  - 99th percentile
- **Failures** (失败率)
- **Current Users** (当前用户数)

## 5. 成功标准

- ✅ 失败率 < 1%
- ✅ 平均响应时间 < 10秒
- ✅ 95% 响应时间 < 20秒
- ✅ 系统稳定无崩溃

## 故障排除

**问题：连接被拒绝**
- 确保 Kotaemon 服务运行在 http://localhost:7860

**问题：响应时间过长**
- 检查 LLM 模型性能
- 检查系统资源（CPU、内存、GPU）
- 减少并发用户数

**问题：大量失败**
- 查看服务器日志
- 检查系统资源是否充足
- 降低并发用户数和孵化速率
