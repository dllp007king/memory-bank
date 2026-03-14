#!/bin/bash
# Memory Bank 启动脚本

cd "$(dirname "$0")"

# 停止已有进程
echo "停止已有进程..."
pkill -f "app.py" 2>/dev/null
sleep 1

# 启动服务
echo "启动 Memory Bank..."
cd web
/usr/bin/python3 app.py

# 如果需要后台运行，使用：
# nohup /usr/bin/python3 app.py > ../logs/server.log 2>&1 &
# echo "服务已启动: http://localhost:8088"
