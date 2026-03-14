#!/bin/bash
# Memory Bank 停止脚本

echo "=========================================="
echo "  Memory Bank 停止脚本"
echo "=========================================="

# 停止 Flask 进程
echo ""
echo "[1/2] 停止服务进程..."
pkill -f "app.py" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "  ✓ 已发送停止信号"
else
    echo "  - 没有运行中的进程"
fi

sleep 1

# 检查端口
echo ""
echo "[2/2] 检查端口状态..."
if lsof -i:8088 > /dev/null 2>&1; then
    echo "  ! 端口 8088 仍被占用，强制清理..."
    lsof -ti:8088 | xargs kill -9 2>/dev/null
    sleep 1
    echo "  ✓ 端口已释放"
else
    echo "  ✓ 端口 8088 已释放"
fi

echo ""
echo "=========================================="
echo "  Memory Bank 已停止"
echo "=========================================="
