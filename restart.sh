#!/bin/bash
# Memory Bank 重启脚本

cd "$(dirname "$0")"

echo "=========================================="
echo "  Memory Bank 重启脚本"
echo "=========================================="

# 停止已有进程
echo ""
echo "[1/3] 停止已有进程..."
pkill -f "app.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ 已停止旧进程"
else
    echo "  - 没有运行中的进程"
fi

sleep 1

# 检查端口是否释放
if lsof -i:8088 > /dev/null 2>&1; then
    echo "  ! 端口 8088 仍被占用，强制清理..."
    lsof -ti:8088 | xargs kill -9 2>/dev/null
    sleep 1
fi

# 启动服务
echo ""
echo "[2/3] 启动 Memory Bank..."
cd web
nohup python3 app.py > ../logs/server.log 2>&1 &
PID=$!
cd ..

sleep 2

# 检查是否启动成功
echo ""
echo "[3/3] 检查服务状态..."
if kill -0 $PID 2>/dev/null; then
    echo "  ✓ 服务已启动 (PID: $PID)"
    echo ""
    echo "=========================================="
    echo "  访问地址:"
    echo "  - 主页:   http://localhost:8088/"
    echo "  - 图谱:   http://localhost:8088/graph"
    echo "  - 配置:   http://localhost:8088/config"
    echo "  - 状态:   http://localhost:8088/api/status"
    echo "=========================================="
    echo ""
    echo "  日志: tail -f logs/server.log"
    echo ""
else
    echo "  ✗ 启动失败，查看日志:"
    echo "    cat logs/server.log"
    exit 1
fi
