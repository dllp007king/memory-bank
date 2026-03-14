# Memory Bank Web UI

Memory Bank 记忆库的可视化管理界面。

## 功能

- 📊 仪表盘：显示统计信息和类型分布饼图
- 🔍 搜索：支持向量搜索、混合搜索、实体搜索
- 📋 事实管理：浏览、添加、删除事实
- 👥 实体列表：查看所有实体及关联事实数

## 安装依赖

### 方法 1：系统包（推荐）

```bash
sudo apt install python3-flask python3-flask-cors
```

### 方法 2：虚拟环境

```bash
# 安装 venv（如果没有）
sudo apt install python3-venv

# 创建虚拟环境
python3 -m venv venv
./venv/bin/pip install flask flask-cors
```

## 启动

```bash
./run.sh
```

或者直接运行：

```bash
python3 app.py
```

## 访问

打开浏览器访问：http://localhost:8081

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取数据库状态 |
| `/api/facts` | GET | 列出事实（支持分页、筛选） |
| `/api/facts` | POST | 添加新事实 |
| `/api/facts/<id>` | DELETE | 删除事实 |
| `/api/entities` | GET | 列出所有实体 |
| `/api/search` | GET | 搜索（支持向量/混合/实体） |

## 配置

- 数据库路径：`/home/myclaw/.openclaw/workspace/.memory/index.sqlite`
- 监听端口：`0.0.0.0:8081`（允许局域网访问）
