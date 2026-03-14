#!/bin/bash
# Memory Bank Systemd 服务安装脚本

echo "=== Memory Bank 后台服务安装 ==="
echo ""

# 停止当前运行的实例
echo "[1/5] 停止当前运行实例..."
pkill -f "memory-bank/web/app.py" 2>/dev/null || true
sleep 1

# 安装服务文件
echo "[2/5] 安装 systemd 服务文件..."
sudo cp /home/myclaw/.openclaw/workspace/memory-bank/memory-bank.service /etc/systemd/system/

# 重载配置
echo "[3/5] 重载 systemd 配置..."
sudo systemctl daemon-reload

# 设置开机自启
echo "[4/5] 设置开机自启..."
sudo systemctl enable memory-bank

# 启动服务
echo "[5/5] 启动服务..."
sudo systemctl start memory-bank

sleep 2

# 检查状态
echo ""
echo "=== 服务状态 ==="
sudo systemctl status memory-bank --no-pager

echo ""
echo "=== 安装完成 ==="
echo "访问: http://10.10.10.18:8088"
echo ""
echo "常用命令:"
echo "  查看状态: sudo systemctl status memory-bank"
echo "  查看日志: sudo journalctl -u memory-bank -f"
echo "  停止服务: sudo systemctl stop memory-bank"
echo "  重启服务: sudo systemctl restart memory-bank"
