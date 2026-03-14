#!/bin/bash
# Memory Bank Web UI 启动脚本

cd "$(dirname "$0")"

# 检查依赖
check_deps() {
    python3 -c "import flask" 2>/dev/null
    return $?
}

# 尝试安装系统依赖（需要 sudo）
install_system_deps() {
    echo "正在安装系统依赖..."
    sudo apt update && sudo apt install -y python3-flask python3-flask-cors
}

# 主逻辑
if ! check_deps; then
    echo "缺少依赖: flask"
    echo ""
    echo "安装方法："
    echo "  方法1 (推荐): sudo apt install python3-flask python3-flask-cors"
    echo "  方法2: 创建虚拟环境 (需要 python3-venv)"
    echo ""
    read -p "是否尝试自动安装系统依赖？[y/N] " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        install_system_deps
    else
        exit 1
    fi
fi

# 启动服务
echo "启动 Memory Bank Web UI..."
echo "访问地址: http://localhost:8081"
echo ""
python3 app.py
