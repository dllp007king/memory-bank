#!/usr/bin/env python3
"""
知识导出脚本

功能：
- 从 LanceDB 导出所有数据
- 转换为 JSON + Markdown
- 生成美化版知识图谱
- 打包为可分享文件

用法：
    python export_knowledge.py --output knowledge_export
    python export_knowledge.py --output knowledge_export --format json
    python export_knowledge.py --output knowledge_export --format markdown
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# 添加 memory_bank 模块路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_bank.lance_crud import MemoryCRUD


class KnowledgeExporter:
    """知识导出器"""

    def __init__(self, output_dir="knowledge_export"):
        self.output_dir = Path(output_dir)
        self.crud = MemoryCRUD()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def export(self, format="all"):
        """执行导出"""
        print(f"📦 开始导出知识库...")
        print(f"   输出目录: {self.output_dir}")

        # 创建目录结构
        self._create_directories()

        # 导出数据
        memories = self._export_memories()
        entities = self._export_entities()
        relations = self._export_relations()

        # 生成文档
        if format in ["markdown", "all"]:
            self._generate_markdown_docs(memories, entities)
            self._generate_readme()

        # 生成图谱
        if format in ["html", "all"]:
            self._generate_graph_html(entities, relations)

        # 打包
        zip_path = self._create_archive()

        print(f"\n✅ 导出完成！")
        print(f"   记忆数: {len(memories)}")
        print(f"   实体数: {len(entities)}")
        print(f"   关系数: {len(relations)}")
        print(f"   压缩包: {zip_path}")

        return zip_path

    def _create_directories(self):
        """创建目录结构"""
        dirs = [
            self.output_dir,
            self.output_dir / "data",
            self.output_dir / "docs",
            self.output_dir / "docs" / "entities",
            self.output_dir / "docs" / "memories",
            self.output_dir / "visualization",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _export_memories(self):
        """导出记忆"""
        print("   导出记忆...")

        # 获取所有记忆
        memories = self.crud.list_memories(limit=10000)

        # 保存为 JSON
        memories_data = [m.to_dict() for m in memories]
        with open(self.output_dir / "data" / "memories.json", "w", encoding="utf-8") as f:
            json.dump(memories_data, f, ensure_ascii=False, indent=2)

        return memories_data

    def _export_entities(self):
        """导出实体"""
        print("   导出实体...")

        # 获取所有实体
        entities = self.crud.list_entities(limit=10000)

        # 保存为 JSON
        entities_data = [e.to_dict() for e in entities]
        with open(self.output_dir / "data" / "entities.json", "w", encoding="utf-8") as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)

        return entities_data

    def _export_relations(self):
        """导出关系"""
        print("   导出关系...")

        # 获取所有关系
        relations = self.crud.list_relations(limit=10000)

        # 保存为 JSON
        relations_data = [r.to_dict() for r in relations]
        with open(self.output_dir / "data" / "relations.json", "w", encoding="utf-8") as f:
            json.dump(relations_data, f, ensure_ascii=False, indent=2)

        return relations_data

    def _generate_markdown_docs(self, memories, entities):
        """生成 Markdown 文档"""
        print("   生成 Markdown 文档...")

        # 生成实体文档
        for entity in entities:
            self._generate_entity_doc(entity, memories)

        # 生成记忆文档（按时间）
        self._generate_memories_doc(memories)

    def _generate_entity_doc(self, entity, memories):
        """生成单个实体的文档"""
        slug = entity.get("slug", entity.get("name", ""))
        name = entity.get("name", slug)
        entity_type = entity.get("entity_type", "UNKNOWN")
        summary = entity.get("summary", "")

        # 查找相关记忆
        related_memories = [
            m for m in memories
            if slug in m.get("entities", [])
        ]

        # 生成 Markdown
        md = f"""# {name}

**类型**: {entity_type}

{summary}

## 相关记忆 ({len(related_memories)} 条)

"""
        for i, mem in enumerate(related_memories[:20], 1):
            content = mem.get("content", "")[:100]
            timestamp = mem.get("timestamp", mem.get("created_at", ""))
            md += f"{i}. {content}... ({timestamp})\n"

        # 保存
        doc_path = self.output_dir / "docs" / "entities" / f"{slug}.md"
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(md)

    def _generate_memories_doc(self, memories):
        """生成记忆文档（按时间）"""
        # 按时间分组
        from collections import defaultdict
        by_month = defaultdict(list)

        for mem in memories:
            timestamp = mem.get("timestamp", mem.get("created_at", ""))
            if timestamp:
                month = timestamp[:7]  # YYYY-MM
                by_month[month].append(mem)

        # 生成每月文档
        for month, mems in by_month.items():
            md = f"# 记忆 - {month}\n\n"

            for i, mem in enumerate(mems, 1):
                content = mem.get("content", "")
                entities = ", ".join(mem.get("entities", []))
                md += f"## {i}. {content[:50]}...\n\n"
                md += f"**实体**: {entities}\n\n"
                md += f"{content}\n\n"
                md += "---\n\n"

            # 保存
            doc_path = self.output_dir / "docs" / "memories" / f"{month}.md"
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(md)

    def _generate_readme(self):
        """生成 README.md"""
        md = f"""# 知识库导出

**导出时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 目录结构

```
knowledge_export/
├── data/
│   ├── memories.json      # 所有记忆（JSON 格式）
│   ├── entities.json      # 所有实体
│   └── relations.json     # 所有关系
│
├── docs/
│   ├── entities/          # 实体文档（Markdown）
│   └── memories/          # 记忆文档（按月）
│
├── visualization/
│   └── graph.html         # 知识图谱（可视化）
│
└── README.md              # 本文件
```

## 使用方法

### 在线查看

1. 打开 `visualization/graph.html` 查看知识图谱
2. 浏览 `docs/` 目录查看 Markdown 文档

### 导入到其他系统

```bash
# 导入到新的 LanceDB
python import_from_json.py data/memories.json
```

### 查看数据

```bash
# 查看 JSON 数据
cat data/memories.json | python -m json.tool | less
```

## 数据格式

### memories.json

```json
[
  {{
    "id": "xxx",
    "content": "记忆内容",
    "entities": ["实体1", "实体2"],
    "relations": ["实体1|关系|实体2"],
    "importance": 0.7,
    "tags": ["标签"]
  }}
]
```

### entities.json

```json
[
  {{
    "slug": "entity-name",
    "name": "实体名称",
    "entity_type": "PERSON(人物)",
    "summary": "实体摘要"
  }}
]
```

---

**生成工具**: Memory Bank Exporter v1.0
"""

        with open(self.output_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(md)

    def _generate_graph_html(self, entities, relations):
        """生成美化版知识图谱 HTML"""
        print("   生成知识图谱...")

        # 准备图谱数据
        nodes = []
        for entity in entities:
            name = entity.get("name", entity.get("slug", ""))
            entity_type = entity.get("entity_type", "UNKNOWN")
            memory_count = entity.get("memory_count", 0)

            # 实体类型颜色映射
            color_map = {
                "PERSON": "#FF6B6B",
                "PROJECT": "#4ECDC4",
                "TOOL": "#45B7D1",
                "DOCUMENT": "#FFA07A",
                "TASK": "#98D8C8",
                "BUG": "#FF8C94",
                "ROLE": "#DDA0DD",
                "CONCEPT": "#F7DC6F",
            }

            # 提取类型（去掉中文部分）
            type_key = entity_type.split("(")[0] if "(" in entity_type else entity_type
            color = color_map.get(type_key, "#95A5A6")

            nodes.append({
                "id": name,
                "name": name,
                "type": entity_type,
                "color": color,
                "size": max(10, min(40, 10 + memory_count * 3)),  # 节点大小
                "memory_count": memory_count
            })

        links = []
        for relation in relations:
            source = relation.get("source_slug", "")
            target = relation.get("target_slug", "")
            rel_type = relation.get("relation_type", "")
            confidence = relation.get("confidence", 0.5)

            if source and target:
                links.append({
                    "source": source,
                    "target": target,
                    "type": rel_type,
                    "confidence": confidence
                })

        # 生成 HTML（使用简化版 D3.js）
        html = self._get_graph_template(nodes, links)

        with open(self.output_dir / "visualization" / "graph.html", "w", encoding="utf-8") as f:
            f.write(html)

    def _get_graph_template(self, nodes, links):
        """获取图谱 HTML 模板"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知识图谱 - Memory Bank</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow: hidden;
        }}

        #graph {{
            width: 100vw;
            height: 100vh;
        }}

        .node {{
            cursor: pointer;
            transition: all 0.3s;
        }}

        .node:hover {{
            filter: brightness(1.3);
        }}

        .link {{
            stroke-opacity: 0.6;
        }}

        .tooltip {{
            position: absolute;
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid #555;
            border-radius: 8px;
            padding: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            max-width: 300px;
        }}

        .tooltip.active {{
            opacity: 1;
        }}

        .legend {{
            position: fixed;
            top: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #444;
        }}

        .legend h3 {{
            margin-bottom: 10px;
            font-size: 14px;
            color: #fff;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 12px;
        }}

        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 8px;
        }}

        .controls {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #444;
        }}

        .controls button {{
            background: #4ECDC4;
            border: none;
            padding: 8px 16px;
            margin: 5px;
            border-radius: 4px;
            cursor: pointer;
            color: #1a1a2e;
            font-weight: bold;
        }}

        .controls button:hover {{
            background: #45B7D1;
        }}

        .stats {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #444;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div id="graph"></div>

    <div class="tooltip" id="tooltip"></div>

    <div class="legend">
        <h3>实体类型</h3>
        <div class="legend-item">
            <div class="legend-color" style="background: #FF6B6B;"></div>
            <span>PERSON(人物)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #4ECDC4;"></div>
            <span>PROJECT(项目)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #45B7D1;"></div>
            <span>TOOL(工具)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #FFA07A;"></div>
            <span>DOCUMENT(文档)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #98D8C8;"></div>
            <span>TASK(任务)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #F7DC6F;"></div>
            <span>CONCEPT(概念)</span>
        </div>
    </div>

    <div class="controls">
        <button onclick="resetZoom()">重置视图</button>
        <button onclick="toggleLabels()">切换标签</button>
    </div>

    <div class="stats">
        <div>节点数: {len(nodes)}</div>
        <div>关系数: {len(links)}</div>
        <div>导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
    </div>

    <script>
        const nodes = {json.dumps(nodes, ensure_ascii=False)};
        const links = {json.dumps(links, ensure_ascii=False)};

        // 创建 SVG
        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", window.innerWidth)
            .attr("height", window.innerHeight);

        // 创建容器（支持缩放）
        const container = svg.append("g");

        // 缩放行为
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on("zoom", (event) => {{
                container.attr("transform", event.transform);
            }});

        svg.call(zoom);

        // 创建力导向模拟
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2))
            .force("collision", d3.forceCollide().radius(d => d.size + 10));

        // 绘制关系
        const link = container.append("g")
            .selectAll("line")
            .data(links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke", "#666")
            .attr("stroke-width", d => d.confidence * 3);

        // 绘制节点
        const node = container.append("g")
            .selectAll("circle")
            .data(nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.size)
            .attr("fill", d => d.color)
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", showTooltip)
            .on("mouseout", hideTooltip);

        // 节点标签
        const labels = container.append("g")
            .selectAll("text")
            .data(nodes)
            .enter().append("text")
            .text(d => d.name)
            .attr("font-size", 12)
            .attr("dx", d => d.size + 5)
            .attr("dy", 4)
            .attr("fill", "#ddd");

        let showLabels = true;

        // 更新位置
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);

            labels
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }});

        // 拖拽函数
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}

        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}

        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}

        // 工具提示
        function showTooltip(event, d) {{
            const tooltip = document.getElementById('tooltip');
            tooltip.innerHTML = `
                <strong>${{d.name}}</strong><br>
                类型: ${{d.type}}<br>
                记忆数: ${{d.memory_count}}
            `;
            tooltip.style.left = (event.pageX + 10) + 'px';
            tooltip.style.top = (event.pageY + 10) + 'px';
            tooltip.classList.add('active');
        }}

        function hideTooltip() {{
            document.getElementById('tooltip').classList.remove('active');
        }}

        // 控制函数
        function resetZoom() {{
            svg.transition().duration(750).call(
                zoom.transform,
                d3.zoomIdentity
            );
        }}

        function toggleLabels() {{
            showLabels = !showLabels;
            labels.style("opacity", showLabels ? 1 : 0);
        }}

        // 窗口调整
        window.addEventListener('resize', () => {{
            svg.attr("width", window.innerWidth)
               .attr("height", window.innerHeight);
            simulation.force("center", d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2));
            simulation.alpha(1).restart();
        }});
    </script>
</body>
</html>
"""

    def _create_archive(self):
        """创建压缩包"""
        print("   创建压缩包...")

        archive_name = f"{self.output_dir.name}_{self.timestamp}"
        archive_path = shutil.make_archive(archive_name, 'zip', self.output_dir)

        return archive_path


def main():
    parser = argparse.ArgumentParser(description="导出知识库")
    parser.add_argument("--output", "-o", default="knowledge_export", help="输出目录")
    parser.add_argument("--format", "-f", choices=["json", "markdown", "html", "all"],
                        default="all", help="导出格式")

    args = parser.parse_args()

    exporter = KnowledgeExporter(output_dir=args.output)
    exporter.export(format=args.format)


if __name__ == "__main__":
    main()
