# Memory Bank 部署指南

## 环境要求

- Python 3.10+
- pip
- (可选) Node.js 18+ - 用于 Web 前端构建

## 快速部署

### 1. 复制文件到目标机器

```bash
scp -r /mnt/sdb/memory-bank-release user@target:/path/to/install
```

### 2. 创建虚拟环境

```bash
cd /path/to/install/memory-bank-release
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
pip install lancedb jieba
```

### 4. 启动服务

```bash
# 前台运行
./start.sh

# 或使用 systemd 服务
./install-service.sh
```

### 5. 验证

```bash
curl http://localhost:8088/api/search?q=test
```

## 目录结构

```
memory-bank-release/
├── memory_bank/       # 核心源码
├── web/               # Web 服务
├── scripts/           # 工具脚本
├── requirements.txt   # Python 依赖
├── start.sh           # 启动脚本
├── stop.sh            # 停止脚本
├── restart.sh         # 重启脚本
├── memory_cli.py      # CLI 工具
└── README.md          # 项目说明
```

## 配置

配置文件在首次运行时自动创建于 `config/memory_lifecycle.json`。

默认配置：
- 服务端口: 8088
- 数据目录: `~/.openclaw/workspace/.memory/`
  - SQLite: `index.sqlite` (FTS5 全文索引)
  - LanceDB: `lancedb/` (向量数据库)

## systemd 服务

安装为系统服务：

```bash
sudo ./install-service.sh
sudo systemctl enable memory-bank
sudo systemctl start memory-bank
```

## 常见问题

### Q: 启动失败，提示模块找不到？
A: 确保已激活虚拟环境并安装所有依赖：
```bash
source .venv/bin/activate
pip install -r requirements.txt
pip install lancedb jieba flask flask-cors
```

### Q: 端口被占用？
A: 修改 `web/app.py` 中的端口配置，或设置环境变量 `PORT=8089`。

### Q: 数据存储在哪里？
A: 默认在 `~/.openclaw/workspace/.memory/` 目录：
- `index.sqlite` - SQLite 数据库 + FTS5 索引
- `lancedb/memories.lance/` - 记忆向量
- `lancedb/entities.lance/` - 实体向量
- `lancedb/relations.lance/` - 关系数据

### Q: 如何备份数据？
A: 运行备份脚本：
```bash
python3 scripts/backup_lancedb.py
```

### Q: 嵌入服务不可用？
A: 确保 llm.cpp HTTP Server 正在运行：
```bash
curl http://localhost:8080/v1/embeddings
```
