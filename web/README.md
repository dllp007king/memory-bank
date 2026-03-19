# Memory Bank Web UI

Memory Bank 记忆库的可视化管理界面。

## 功能

- **📊 仪表盘**：显示统计信息和类型分布饼图
- **🔍 搜索**：支持向量搜索、混合搜索、实体搜索、时间过滤
- **📝 事实管理**：浏览、添加、删除记忆
- **👥 实体列表**：查看所有实体及关联事实数
- **🕸️ 知识图谱**：3D 力导向图可视化
- **⚙️ 配置管理**：生命周期参数配置
- **🔄 生命周期**：清理/提炼候选管理

## 安装依赖

```bash
pip install flask flask-cors
```

## 启动

```bash
# 方式 1：使用脚本
./run.sh

# 方式 2：直接运行
python3 app.py

# 方式 3：后台运行
nohup python3 app.py > /tmp/memory-bank-web.log 2>&1 &
```

## 访问

- 主界面：http://localhost:8088
- 知识图谱：http://localhost:8088/graph
- 配置页面：http://localhost:8088/config

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取数据库状态 |
| `/api/facts` | GET | 列出记忆（支持分页、筛选） |
| `/api/facts` | POST | 添加新记忆 |
| `/api/facts/<id>` | GET | 获取单个记忆详情 |
| `/api/facts/<id>` | DELETE | 删除记忆 |
| `/api/entities` | GET | 列出所有实体 |
| `/api/entities/search` | GET | 搜索实体 |
| `/api/entities/<slug>` | DELETE | 删除实体 |
| `/api/search` | GET | 搜索（支持向量/混合/实体） |
| `/api/relations` | GET | 列出所有关系 |
| `/api/graph` | GET | 获取知识图谱数据 |
| `/api/config/data` | GET | 获取配置 |
| `/api/config/update` | POST | 更新配置 |
| `/api/lifecycle/stats` | GET | 生命周期统计 |
| `/api/lifecycle/cleanup-candidates` | GET | 清理候选列表 |
| `/api/lifecycle/distill-candidates` | GET | 提炼候选列表 |

## 配置

- 数据库路径：`~/.openclaw/workspace/.memory/`
- 监听端口：`0.0.0.0:8088`（允许局域网访问）

## 静态文件

| 文件 | 大小 | 说明 |
|------|------|------|
| index.html | 127KB | 主页面（仪表盘、搜索、管理） |
| graph.html | 67KB | 3D 知识图谱 |
| config.html | 14KB | 配置页面 |
