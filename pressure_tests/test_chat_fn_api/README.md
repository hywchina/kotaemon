# /chat_fn API 压力测试

测试 Kotaemon AI 辅助诊断系统的 `/chat_fn` 接口性能。

## 快速开始

```bash
# 1. 激活虚拟环境
source /home/huyanwei/projects/kotaemon/venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 验证测试（可选）
python verify_locust.py

# 4. 运行压力测试
./run_test.sh
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `locustfile.py` | Locust 压力测试脚本 |
| `locust.conf` | Locust 配置文件 |
| `requirements.txt` | Python 依赖 |
| `run_test.sh` | 一键启动脚本 |
| `verify_locust.py` | 验证脚本 |
| `README_PRESSURE_TEST.md` | 详细文档 |
| `QUICKSTART.md` | 快速开始指南 |
| `IMPLEMENTATION_NOTES.md` | 实现说明 |

## 测试配置

- **并发用户数:** 10
- **孵化速率:** 2 用户/秒
- **测试接口:** `/chat_fn`
- **目标服务:** http://localhost:7860

## 更多信息

详细文档请查看：
- [详细使用文档](./README_PRESSURE_TEST.md)
- [快速开始指南](./QUICKSTART.md)
- [实现说明](./IMPLEMENTATION_NOTES.md)
