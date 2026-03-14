#!/bin/bash
# 推送到 GitHub 的完整脚本

cd ~/.openclaw/workspace/memory-bank

echo "=== 推送到 GitHub ==="
echo ""

# 1. 检查远程仓库
echo "[1/4] 检查远程仓库..."
git remote -v

# 2. 确保分支名是 main
echo ""
echo "[2/4] 切换到 main 分支..."
git branch -M main

# 3. 强制推送到 GitHub
echo ""
echo "[3/4] 推送到 GitHub..."
git push -u origin main --force

# 4. 验证
echo ""
echo "[4/4] 验证推送结果..."
git log --oneline -3
git status

echo ""
echo "=== 完成！==="
echo "仓库地址: https://github.com/dllp007king/memory-bank"
