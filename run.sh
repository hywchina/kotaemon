#!/bin/bash
# ============================================
# 通用应用启动管理脚本（稳定版）
# 支持 start / stop / restart / status / log / help
# ============================================

set -euo pipefail

APP_NAME="app.py"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs/system"
RERANK_LOG_DIR="$APP_DIR/logs/services"
PID_FILE="$LOG_DIR/app.pid"
PIPE_FILE="$LOG_DIR/app.pipe"
ROTATE_PID_FILE="$LOG_DIR/rotate.pid"
RERANK_PID_FILE="$RERANK_LOG_DIR/rerank.pid"

DEFAULT_PORT=7860
PORT="${2:-$DEFAULT_PORT}"

# Rerank 服务配置
RERANK_HOST="0.0.0.0"
RERANK_PORT="8001"
RERANK_URL="http://127.0.0.1:${RERANK_PORT}/rerank"
RERANK_APP="services.local_rerank_server:app"

# 环境变量配置
export USE_GLOBAL_GRAPHRAG=False
export USE_MS_GRAPHRAG=False
export USE_NANO_GRAPHRAG=False
export USE_LIGHTRAG=False

mkdir -p "$LOG_DIR" "$RERANK_LOG_DIR"

# ========== 函数定义 ==========

start_rerank_service() {
    echo "[INFO] 启动 Rerank 服务..."
    
    # 清理占用端口的进程
    if lsof -i:${RERANK_PORT} >/dev/null 2>&1; then
        echo "[INFO] 清理占用端口 ${RERANK_PORT} 的进程..."
        lsof -t -i:${RERANK_PORT} | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # 启动服务
    local RERANK_LOG="${RERANK_LOG_DIR}/rerank_$(date '+%Y%m%d_%H%M%S').log"
    local RERANK_PIPE=$(mktemp -u)
    mkfifo "$RERANK_PIPE"
    
    # 后台日志写入
    (while IFS= read -r line; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
    done < "$RERANK_PIPE" >> "$RERANK_LOG") &
    local logger_pid=$!
    
    # 启动 uvicorn
    nohup uvicorn "$RERANK_APP" --host "$RERANK_HOST" --port "$RERANK_PORT" > "$RERANK_PIPE" 2>&1 &
    local rerank_pid=$!
    echo $rerank_pid > "$RERANK_PID_FILE"
    
    echo "[INFO] Rerank 服务已启动 (PID: $rerank_pid, 日志: $RERANK_LOG)"
}

check_rerank_service() {
    echo "[INFO] 检查 Rerank 服务状态..."
    
    # 测试请求
    local test_payload='{"query":"test","texts":["sample"]}'
    local max_retry=30
    local retry=0
    
    while [ $retry -lt $max_retry ]; do
        local response=$(curl -s -w "\n%{http_code}" -X POST "$RERANK_URL" \
            -H "Content-Type: application/json" \
            -d "$test_payload" \
            --max-time 3 2>/dev/null || echo "000")
        
        local http_code=$(echo "$response" | tail -n1)
        
        if [[ "$http_code" == "200" ]]; then
            echo "[INFO] Rerank 服务运行正常 ✓"
            return 0
        fi
        
        retry=$((retry + 1))
        if [ $retry -lt $max_retry ]; then
            echo "[INFO] 等待服务就绪... ($retry/$max_retry)"
            sleep 1
        fi
    done
    
    echo "[ERROR] Rerank 服务启动失败或响应超时"
    echo "[ERROR] 请检查日志: $RERANK_LOG_DIR"
    exit 1
}

ensure_rerank_service() {
    # 检查服务是否已运行
    if lsof -i:${RERANK_PORT} >/dev/null 2>&1; then
        local test_payload='{"query":"test","texts":["sample"]}'
        local response=$(curl -s -w "\n%{http_code}" -X POST "$RERANK_URL" \
            -H "Content-Type: application/json" \
            -d "$test_payload" \
            --max-time 3 2>/dev/null || echo "000")
        local http_code=$(echo "$response" | tail -n1)
        
        if [[ "$http_code" == "200" ]]; then
            echo "[INFO] Rerank 服务已就绪 ✓"
            return 0
        fi
    fi
    
    # 服务未运行或异常，启动服务
    start_rerank_service
    check_rerank_service
}

rotate_log() {
    LOG_FILE="$LOG_DIR/$(date '+%Y%m%d').log"
    echo "$LOG_FILE"
}

start_log_rotator() {
    local LOG_FILE
    LOG_FILE=$(rotate_log)

    # 创建命名管道（若不存在）
    [[ -p "$PIPE_FILE" ]] || mkfifo "$PIPE_FILE"

    echo "[INFO] 启动日志轮转后台任务 ..."
    (
        while true; do
            LOG_FILE=$(rotate_log)
            echo "[INFO] 写入日志到: $LOG_FILE" >> "$LOG_DIR/start_system.log"

            # 每行前添加时间戳
            while IFS= read -r line; do
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line"
            done < "$PIPE_FILE" >> "$LOG_FILE" 2>/dev/null &
            cat_pid=$!

            # 睡到明天零点
            now=$(date +%s)
            tomorrow=$(date -d "tomorrow 00:00:00" +%s)
            sleep_seconds=$(( tomorrow - now ))
            sleep "$sleep_seconds"

            # 停掉当前写入进程，触发轮换
            kill "$cat_pid" >/dev/null 2>&1 || true
        done
    ) >> "$LOG_DIR/start_system.log" 2>&1 &

    echo $! > "$ROTATE_PID_FILE"
}


stop_log_rotator() {
    if [[ -f "$ROTATE_PID_FILE" ]]; then
        local pid
        pid=$(cat "$ROTATE_PID_FILE")
        if ps -p "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
        rm -f "$ROTATE_PID_FILE"
    fi
}

start_service() {
    # 确保 Rerank 服务运行（自动启动并等待就绪）
    ensure_rerank_service
    
    if [[ -f "$PID_FILE" ]] && ps -p "$(cat "$PID_FILE")" >/dev/null 2>&1; then
        echo "[WARN] 服务已在运行中 (PID: $(cat "$PID_FILE"))"
        exit 0
    fi

    # 杀掉占用端口的 python 进程
    if lsof -i:${PORT} | grep -q python; then
        echo "[INFO] 杀死占用 ${PORT} 端口的进程..."
        lsof -i:${PORT} | grep python | awk '{print $2}' | xargs kill -9 || true
        sleep 1
    fi

    echo "[INFO] 启动服务 (端口: ${PORT}) ..."
    local LOG_FILE
    LOG_FILE=$(rotate_log)

    # 启动日志轮换进程
    start_log_rotator

    # 启动应用
    nohup python "$APP_DIR/$APP_NAME" --port "$PORT" > "$PIPE_FILE" 2>&1 &
    APP_PID=$!
    echo $APP_PID > "$PID_FILE"

    echo "[INFO] 服务已启动 (PID: $APP_PID)"
    echo "[INFO] 日志文件: $LOG_FILE"
}

stop_service() {
    # 停止主服务
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" >/dev/null 2>&1; then
            echo "[INFO] 停止主服务 (PID: $PID)..."
            kill "$PID"
            sleep 1
            if ps -p "$PID" >/dev/null 2>&1; then
                echo "[WARN] 进程未退出，强制终止..."
                kill -9 "$PID" || true
            fi
            echo "[INFO] 主服务已停止"
        else
            echo "[WARN] PID 文件存在但进程未运行，清理中..."
        fi
        rm -f "$PID_FILE"
    else
        echo "[INFO] 主服务未运行"
    fi

    stop_log_rotator
    [[ -p "$PIPE_FILE" ]] && rm -f "$PIPE_FILE"
    
    # 停止 Rerank 服务
    if [[ -f "$RERANK_PID_FILE" ]]; then
        local rerank_pid=$(cat "$RERANK_PID_FILE")
        if ps -p "$rerank_pid" >/dev/null 2>&1; then
            echo "[INFO] 停止 Rerank 服务 (PID: $rerank_pid)..."
            kill "$rerank_pid" 2>/dev/null || true
            sleep 1
            ps -p "$rerank_pid" >/dev/null 2>&1 && kill -9 "$rerank_pid" 2>/dev/null || true
        fi
        rm -f "$RERANK_PID_FILE"
    fi
    
    # 清理 Rerank 端口
    if lsof -i:${RERANK_PORT} >/dev/null 2>&1; then
        echo "[INFO] 清理 Rerank 端口 ${RERANK_PORT}..."
        lsof -t -i:${RERANK_PORT} | xargs kill -9 2>/dev/null || true
    fi
}

restart_service() {
    local port="${2:-$DEFAULT_PORT}"
    stop_service
    PORT="$port"
    start_service
}

status_service() {
    echo "========== 主服务状态 =========="
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" >/dev/null 2>&1; then
            echo "[INFO] 主服务正在运行 (PID: $PID)"
            PORT_INFO=$(lsof -Pan -p "$PID" -i | grep LISTEN || true)
            [[ -n "$PORT_INFO" ]] && echo "[INFO] 监听端口: $(echo "$PORT_INFO" | awk '{print $9}')"
            echo "[INFO] 日志目录: $LOG_DIR"
        else
            echo "[INFO] 主服务未运行"
        fi
    else
        echo "[INFO] 主服务未运行"
    fi
    
    echo ""
    echo "========== Rerank 服务状态 =========="
    if [[ -f "$RERANK_PID_FILE" ]]; then
        local rerank_pid=$(cat "$RERANK_PID_FILE")
        if ps -p "$rerank_pid" >/dev/null 2>&1; then
            echo "[INFO] Rerank 服务正在运行 (PID: $rerank_pid)"
            echo "[INFO] 监听端口: ${RERANK_PORT}"
            
            # 测试服务健康状态
            local test_payload='{"query":"test","texts":["sample"]}'
            local response=$(curl -s -w "\n%{http_code}" -X POST "$RERANK_URL" \
                -H "Content-Type: application/json" \
                -d "$test_payload" \
                --max-time 3 2>/dev/null || echo "000")
            local http_code=$(echo "$response" | tail -n1)
            
            if [[ "$http_code" == "200" ]]; then
                echo "[INFO] 健康状态: ✓ 正常"
            else
                echo "[WARN] 健康状态: ✗ 异常 (HTTP: $http_code)"
            fi
        else
            echo "[INFO] Rerank 服务未运行"
        fi
    else
        echo "[INFO] Rerank 服务未运行"
    fi
}

show_log() {
    local LOG_FILE
    LOG_FILE=$(rotate_log)
    if [[ -f "$LOG_FILE" ]]; then
        tail -n 50 -f "$LOG_FILE"
    else
        echo "[INFO] 日志文件不存在: $LOG_FILE"
    fi
}

show_help() {
    cat <<EOF
用法: bash run.sh [命令] [可选参数]

可用命令:
  --start [port]     启动服务 (默认端口: $DEFAULT_PORT)
  --stop             停止服务
  --restart [port]   重启服务
  --status           查看服务状态
  --log              查看当前日志 (实时输出)
  --help             显示帮助信息
EOF
}

# ========== 主逻辑 ==========

case "${1:-}" in
    --start) start_service ;;
    --stop) stop_service ;;
    --restart) restart_service "${2:-}" ;;   # ✅ 修复：安全取参数
    --status) status_service ;;
    --log) show_log ;;
    --help|"") show_help ;;
    *)
        echo "[ERROR] 未知命令: $1"
        show_help
        exit 1
        ;;
esac
