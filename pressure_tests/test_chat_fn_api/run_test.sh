#!/bin/bash
# 压力测试启动脚本

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Kotaemon 压力测试启动脚本 ===${NC}"
echo ""

# 检查服务是否运行
echo -e "${YELLOW}检查服务状态...${NC}"
if ! curl -s http://localhost:7860 > /dev/null; then
    echo -e "${RED}错误: Kotaemon 服务未运行！${NC}"
    echo "请先启动服务: http://localhost:7860"
    exit 1
fi
echo -e "${GREEN}✓ 服务正常运行${NC}"
echo ""

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
VENV_PATH="/home/huyanwei/projects/kotaemon/venv/bin/activate"
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
    echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
else
    echo -e "${RED}警告: 虚拟环境不存在，尝试使用系统 Python${NC}"
fi
echo ""

# 检查并安装依赖
echo -e "${YELLOW}检查测试依赖...${NC}"
if ! python -c "import locust" 2>/dev/null; then
    echo "安装 Locust 依赖..."
    pip install -r requirements.txt
fi
echo -e "${GREEN}✓ 依赖检查完成${NC}"
echo ""

# 获取运行模式
echo -e "${YELLOW}选择运行模式:${NC}"
echo "1) Web UI 模式 (默认，推荐) - 可视化界面"
echo "2) 命令行模式 - 快速测试"
echo "3) 无头模式 - 自动运行 5 分钟"
echo ""
read -p "请选择 [1/2/3，默认: 1]: " mode
mode=${mode:-1}

case $mode in
    1)
        echo -e "${GREEN}启动 Web UI 模式...${NC}"
        echo "访问 http://localhost:8089 查看测试界面"
        echo "默认配置: 10 个并发用户，每秒孵化 2 个用户"
        echo ""
        locust -f locustfile.py --config=locust.conf
        ;;
    2)
        echo -e "${GREEN}启动命令行模式...${NC}"
        echo "测试配置: 10 个并发用户，每秒孵化 2 个，运行 2 分钟"
        echo ""
        locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 2m --host http://localhost:7860
        ;;
    3)
        echo -e "${GREEN}启动无头模式...${NC}"
        echo "测试配置: 10 个并发用户，每秒孵化 2 个，运行 5 分钟"
        echo ""
        locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 5m --host http://localhost:7860 --html report.html
        echo -e "${GREEN}测试完成！报告已保存到 report.html${NC}"
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac
