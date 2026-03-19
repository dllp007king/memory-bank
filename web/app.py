"""
Memory Bank Web UI - Flask 后端

提供 RESTful API 用于管理记忆库。
适配 LanceDB 向量数据库。
"""

import sys
import os
import logging
from pathlib import Path
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime, timedelta

# 添加 memory_bank 模块路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============ LanceDB 模块导入 ============
from memory_bank.lance import LanceConnection
from memory_bank.lance_crud import MemoryCRUD, get_crud, set_crud
from memory_bank.lance_search import MemorySearch, get_searcher

# 嵌入和生命周期模块
from memory_bank.embedding import check_server_health, embed_single
from memory_bank.lifecycle import effective_confidence

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ============ LanceDB 配置 ============
# 数据库路径
DB_PATH = "/home/myclaw/.openclaw/workspace/.memory/lancedb"

# 嵌入模型信息
EMBEDDING_MODEL = "Qwen3-Embedding-4B-Q8_0"
EMBEDDING_DIM = 2560

# 全局 LanceDB 连接
_lance_conn = None
_crud = None
_searcher = None


def get_lance_conn():
    """获取 LanceDB 连接"""
    global _lance_conn
    if _lance_conn is None:
        _lance_conn = LanceConnection(DB_PATH)
        _lance_conn.connect()
        _lance_conn.init_schema()
    return _lance_conn


def get_crud_instance():
    """获取 CRUD 实例"""
    global _crud
    if _crud is None:
        _crud = get_crud()  # 使用 lance_crud 中的全局 crud
    return _crud


def get_searcher_instance():
    """获取搜索器实例（每次都重新获取以避免缓存问题）"""
    from memory_bank.lance_search import MemorySearch
    return MemorySearch()  # 每次都创建新实例，避免缓存问题


def get_time_range(time_filter):
    """根据时间筛选获取时间范围"""
    now = datetime.now()
    if time_filter == 'today':
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    elif time_filter == 'week':
        start = now - timedelta(days=now.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0), now
    elif time_filter == 'month':
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now
    elif time_filter == 'year':
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), now
    return None, None


# ==================== API 路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取数据库状态"""
    try:
        crud = get_crud_instance()

        # 记忆总数
        memories = crud.list_memories(limit=10000)
        facts_count = len(memories)

        # 实体总数
        entities = crud.list_entities(limit=10000)
        entities_count = len(entities)

        # 关系总数
        relations = crud.list_relations(limit=10000)
        relations_count = len(relations)

        # 向量索引数（通过检查有向量的记忆）
        vectors_count = sum(1 for m in memories if m.vector is not None)

        # 嵌入服务状态
        embedding_ok = check_server_health()

        return jsonify({
            "success": True,
            "data": {
                "facts_count": facts_count,
                "entities_count": entities_count,
                "relations_count": relations_count,
                "vectors_count": vectors_count,
                "embedding_status": "ok" if embedding_ok else "error",
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dim": EMBEDDING_DIM
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/facts', methods=['GET'])
def get_facts():
    """列出事实"""
    try:
        crud = get_crud_instance()
        memory_type = request.args.get('kind', '')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # 参数验证
        if limit < 1 or limit > 1000:
            return jsonify({"success": False, "error": "limit 必须在 1-1000 之间"}), 400
        if offset < 0:
            return jsonify({"success": False, "error": "offset 必须大于等于 0"}), 400
        
        # 获取记忆列表
        memories = crud.list_memories(
            memory_type=memory_type if memory_type else None,
            limit=limit + offset  # 需要先获取足够的数据
        )
        
        total = len(memories)
        
        # 分页
        paginated_memories = memories[offset:offset + limit]
        
        # 预加载所有关系和实体，构建 memory_id -> relations 映射
        all_relations = crud.list_relations(limit=10000)
        all_entities = crud.list_entities(limit=10000)
        # 构建 slug -> name 映射
        slug_to_name = {e.slug: e.name for e in all_entities}
        
        memory_relations_map = {}
        for rel in all_relations:
            if rel.source_memory_id:
                if rel.source_memory_id not in memory_relations_map:
                    memory_relations_map[rel.source_memory_id] = []
                # 转换为友好名称
                src_name = slug_to_name.get(rel.source_slug, rel.source_slug)
                tgt_name = slug_to_name.get(rel.target_slug, rel.target_slug)
                memory_relations_map[rel.source_memory_id].append(
                    f"{src_name}|{rel.relation_type}|{tgt_name}"
                )
        
        facts = []
        for m in paginated_memories:
            eff_conf = effective_confidence(m)
            # 从预加载的映射中获取关系，而不是用空的 m.relations
            fact_relations = memory_relations_map.get(m.id, m.relations)
            facts.append({
                "id": m.id,
                "content": m.content,
                "timestamp": m.created_at,
                "entities": m.entities,
                "relations": fact_relations,
                "confidence": m.confidence,
                "effective_confidence": round(eff_conf, 4),
                "importance": m.importance,
                "lifecycle_state": getattr(m, 'lifecycle_state', 'ACTIVE'),
                "decay_rate": getattr(m, 'decay_rate', 0.01),
                "access_count": getattr(m, 'access_count', 0)
            })
        
        return jsonify({
            "success": True,
            "data": {
                "facts": facts,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/facts', methods=['POST'])
def add_fact():
    """添加新事实（自动创建向量索引，自动提取实体）"""
    try:
        data = request.get_json()

        if not data or 'content' not in data:
            return jsonify({"success": False, "error": "缺少 content 字段"}), 400

        content = data['content']
        entities = data.get('entities', [])  # 用户指定的实体
        relations = data.get('relations', [])  # 用户指定的关系（可以是字符串列表或字典列表）
        importance = data.get('importance', 0.5)  # 重要性
        tags = data.get('tags', [])  # 标签
        entity_type = data.get('entity_type', '')  # 用户指定的实体类型
        confidence = data.get('confidence', 0.9)

        crud = get_crud_instance()

        # 解析关系数据（支持多种格式）
        parsed_relations = []
        for rel in relations:
            if isinstance(rel, str):
                # 字符串格式: "A|关系|B" 或 "A|关系|B|C"（三元关系）
                parts = [p.strip() for p in rel.split('|') if p.strip()]
                
                if len(parts) == 3:
                    # 标准二元关系: A|关系|B
                    parsed_relations.append({
                        "from": parts[0],
                        "rel": parts[1],
                        "to": parts[2]
                    })
                elif len(parts) >= 4:
                    # 三元关系: A|关系|B|C 或更复杂的关系
                    source = parts[0]
                    rel_type = parts[1]
                    middle = parts[2]
                    target = parts[3] if len(parts) > 3 else None
                    
                    # 主关系
                    parsed_relations.append({
                        "from": source,
                        "rel": rel_type,
                        "to": middle
                    })
                    
                    # 如果有第四部分，创建连接关系
                    if target:
                        parsed_relations.append({
                            "from": middle,
                            "rel": "关联",
                            "to": target
                        })
                        
            elif isinstance(rel, dict):
                # 字典格式: {"from": "A", "rel": "关系", "to": "B"}
                source = rel.get('from') or rel.get('source') or ''
                rel_type = rel.get('rel') or rel.get('relation') or rel.get('relation_type') or ''
                target = rel.get('to') or rel.get('target') or ''
                if source and rel_type and target:
                    parsed_relations.append({
                        "from": source.strip(),
                        "rel": rel_type.strip(),
                        "to": target.strip()
                    })

        # 解析实体数据（支持字符串列表或对象列表）
        # 对象格式: {"name": "实体名", "type": "PERSON"}
        entity_type_map = {}  # 用户指定的实体类型映射（用于学习）
        entity_names = []  # 转换后的实体名称列表（用于存储）
        raw_entities = []  # 保存原始 entities（带类型信息）
        
        for entity in entities:
            if isinstance(entity, dict):
                entity_name = entity.get('name', '')
                user_type = entity.get('type')
                if entity_name:
                    entity_names.append(entity_name)
                    raw_entities.append({"name": entity_name, "type": user_type})
                    if user_type:
                        entity_type_map[entity_name.lower().strip()] = user_type
            else:
                entity_names.append(entity)
                raw_entities.append({"name": entity, "type": None})
        
        # 用转换后的名称列表替换原列表（LanceDB 只支持字符串列表）
        entities = entity_names

        # 先检查所有关系是否有效，再决定是否创建
        error_relations = []
        valid_entities = [e.lower().strip().replace(' ', '_').replace('.', '_') for e in entities]
        
        for rel_data in parsed_relations:
            source_slug = rel_data["from"].lower().strip().replace(' ', '_').replace('.', '_')
            target_slug = rel_data["to"].lower().strip().replace(' ', '_').replace('.', '_')
            
            if source_slug not in valid_entities or target_slug not in valid_entities:
                error_relations.append({
                    "from": rel_data["from"],
                    "rel": rel_data["rel"],
                    "to": rel_data["to"],
                    "error": f"'{rel_data['from'] if source_slug not in valid_entities else rel_data['to']}' 不在定义的 entities 列表中"
                })
        
        # 如果有错误关系，不创建记忆，返回错误信息
        if error_relations:
            return jsonify({
                "success": False,
                "error": "关系中的实体不在定义的 entities 列表中",
                "error_code": "RELATION_ENTITY_MISMATCH",
                "error_relations": error_relations,
                "data": {
                    "content": content,
                    "entities": raw_entities,
                    "relations": [f"{r['from']}|{r['rel']}|{r['to']}" for r in parsed_relations],
                    "confidence": confidence,
                    "importance": importance,
                    "tags": tags
                }
            }), 400

        # 创建记忆（包含向量嵌入，跳过关系创建，由后面统一处理）
        memory = crud.create_memory(
            content=content,
            memory_type='fact',  # 统一类型
            entities=entities,
            relations=parsed_relations,
            importance=importance,
            confidence=confidence,
            tags=tags,
            auto_embed=True,
            skip_relations=True  # 关系由后面统一创建，使用正确的 slug
        )
        
        # 创建/关联实体（使用已解析的 entity_names 和 entity_type_map）
        # 返回 name -> slug 映射，用于后续创建关系
        name_to_slug = {}
        for entity_name in entities:
            if not entity_name:
                continue

            # 确定实体类型（优先级：用户指定 > 全局entity_type > 自动推断）
            entity_name_lower = entity_name.lower().strip()
            inferencer = get_inferencer()
            if entity_name_lower in entity_type_map:
                # 用户在实体中指定的类型（最高优先级）
                inferred_type = entity_type_map[entity_name_lower]
                # 学习到缓存中（系统会记住这个映射）
                inferencer._save_to_cache(entity_name_lower, inferred_type, 1.0, 'user_defined')
                logger.info(f"📚 学习实体类型: {entity_name} -> {inferred_type}")
            elif entity_type:
                # 全局指定的类型
                inferred_type = entity_type
            else:
                # 自动推断
                inferred_type, _, _ = inferencer.infer(entity_name)

            # 按名称检查实体是否已存在
            existing = crud.get_entity_by_name(entity_name)
            if existing:
                # 实体已存在，记录其 slug
                name_to_slug[entity_name] = existing.slug
                logger.debug(f"实体已存在: {existing.slug} ({entity_name})")
            else:
                # 创建新实体（自动生成 Base62 slug）
                try:
                    new_entity = crud.create_entity(
                        name=entity_name,
                        entity_type=inferred_type
                    )
                    name_to_slug[entity_name] = new_entity.slug
                    logger.info(f"创建实体: {new_entity.slug} ({entity_name})")
                except Exception as e:
                    logger.warning(f"创建实体失败: {e}")

        # 创建关系（通过名称查找 slug）
        for rel_data in parsed_relations:
            try:
                source_name = rel_data["from"].strip()
                target_name = rel_data["to"].strip()
                rel_type = rel_data["rel"]

                # 通过名称获取 slug
                source_slug = name_to_slug.get(source_name)
                target_slug = name_to_slug.get(target_name)

                if not source_slug:
                    # 尝试从数据库查找
                    source_entity = crud.get_entity_by_name(source_name)
                    if source_entity:
                        source_slug = source_entity.slug
                    else:
                        logger.warning(f"找不到源实体: {source_name}")
                        continue

                if not target_slug:
                    # 尝试从数据库查找
                    target_entity = crud.get_entity_by_name(target_name)
                    if target_entity:
                        target_slug = target_entity.slug
                    else:
                        logger.warning(f"找不到目标实体: {target_name}")
                        continue

                crud.create_relation(
                    source=source_slug,
                    target=target_slug,
                    relation_type=rel_type,
                    source_memory_id=memory.id,
                    confidence=confidence
                )
            except Exception as e:
                logger.warning(f"创建关系失败: {e}")

        embedding_ok = memory.vector is not None

        return jsonify({
            "success": True,
            "data": {
                "id": memory.id,
                "content": content,
                "entities": entities,
                "relations": [f"{r['from']}|{r['rel']}|{r['to']}" for r in parsed_relations],
                "indexed": embedding_ok
            }
        })
    except Exception as e:
        logger.error(f"添加事实失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/facts/<fact_id>', methods=['DELETE'])
def remove_fact(fact_id):
    """删除事实"""
    try:
        crud = get_crud_instance()

        # 删除记忆
        deleted = crud.delete_memory(fact_id)

        if deleted:
            return jsonify({
                "success": True,
                "data": {
                    "id": fact_id,
                    "deleted": True
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "记忆不存在"
            }), 404
    except Exception as e:
        logger.error(f"删除事实失败 (fact_id={fact_id}): {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/facts/<fact_id>', methods=['GET'])
def get_fact_detail(fact_id):
    """获取单个事实详情"""
    try:
        crud = get_crud_instance()
        memory = crud.get_memory(fact_id)
        
        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404
        
        # 从关系表查询该记忆关联的关系
        all_relations = crud.list_relations(limit=10000)
        all_entities = crud.list_entities(limit=10000)
        # 构建 slug -> name 映射
        slug_to_name = {e.slug: e.name for e in all_entities}
        
        fact_relations = []
        for rel in all_relations:
            if rel.source_memory_id == fact_id:
                # 转换为友好名称
                src_name = slug_to_name.get(rel.source_slug, rel.source_slug)
                tgt_name = slug_to_name.get(rel.target_slug, rel.target_slug)
                fact_relations.append(f"{src_name}|{rel.relation_type}|{tgt_name}")
        
        return jsonify({
            "success": True,
            "data": {
                "id": memory.id,
                "content": memory.content,
                "entities": memory.entities,
                "relations": fact_relations,
                "confidence": memory.confidence,
                "importance": memory.importance,
                "tags": memory.tags,
                "created_at": memory.created_at
            }
        })
    except Exception as e:
        logger.error(f"获取事实详情失败 (fact_id={fact_id}): {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/entities/search', methods=['GET'])
def search_entities_by_name():
    """
    按名称搜索实体（支持模糊匹配）

    Query参数:
        q: 搜索查询（实体名称）
        type: 可选，实体类型过滤
        limit: 返回数量限制（默认10）
    """
    try:
        crud = get_crud_instance()

        query = request.args.get('q', '').strip()
        entity_type = request.args.get('type', None)
        limit = int(request.args.get('limit', 10))

        if not query:
            return jsonify({"success": False, "error": "请提供搜索查询"}), 400

        # 搜索实体
        entities = crud.search_entities_by_name(
            name_query=query,
            entity_type=entity_type,
            limit=limit
        )

        # 转换为字典格式
        results = [
            {
                "slug": e.slug,
                "name": e.name,
                "type": e.entity_type,
                "summary": e.summary,
                "memory_count": len(crud.get_entity_memories(e.slug))
            }
            for e in entities
        ]

        return jsonify({
            "success": True,
            "data": {
                "query": query,
                "results": results,
                "total": len(results)
            }
        })
    except Exception as e:
        logger.error(f"搜索实体失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/entities/<slug>', methods=['DELETE'])
def delete_entity(slug):
    """
    删除实体及其关联的记忆

    ⚠️ 警告：这是一个危险操作！
    - 删除实体时，会级联删除所有与该实体关联的记忆
    - 这些操作不可逆，请谨慎使用

    建议在生产环境中添加额外的确认机制（如二次确认）
    """
    try:
        crud = get_crud_instance()

        logger.warning(f"危险操作：正在删除实体 {slug}")

        # 获取关联的记忆数量
        entity_memories = crud.get_entity_memories(slug)
        deleted_memories = len(entity_memories)

        # 删除关联的记忆
        for memory in entity_memories:
            crud.delete_memory(memory.id)

        # 删除实体本身
        deleted = crud.delete_entity(slug)

        logger.warning(f"实体 {slug} 已删除：关联记忆 {deleted_memories} 条")

        return jsonify({
            "success": True,
            "data": {
                "deleted_entity": slug,
                "deleted_facts": deleted_memories,
                "deleted_vectors": deleted_memories  # 每个记忆都有向量
            }
        })
    except Exception as e:
        logger.error(f"删除实体失败 (slug={slug}): {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/infer-entity-type', methods=['POST'])
def infer_entity_type():
    """实时推断实体类型（用于预览）"""
    try:
        data = request.get_json()
        entity_name = data.get('entity_name', '')
        
        if not entity_name:
            return jsonify({"success": False, "error": "请输入实体名称"})
        
        inferencer = get_inferencer()
        entity_type, confidence, source = inferencer.infer(entity_name)
        
        return jsonify({
            "success": True,
            "data": {
                "entity_name": entity_name,
                "entity_type": entity_type,
                "confidence": confidence,
                "source": source
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/entities', methods=['GET'])
def get_entities():
    """列出所有实体（支持分页）"""
    try:
        crud = get_crud_instance()

        # 分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        offset = (page - 1) * page_size

        # 获取所有实体（LanceDB 不支持原生分页，先获取全部再切片）
        all_entities = crud.list_entities(limit=10000)
        total = len(all_entities)

        # 分页切片
        entities = all_entities[offset:offset + page_size]

        result = []
        for e in entities:
            # 获取关联的记忆数量
            memories = crud.get_entity_memories(e.slug)
            result.append({
                "slug": e.slug,
                "name": e.name,
                "type": e.entity_type,
                "fact_count": len(memories),
                "first_seen": e.first_seen
            })

        return jsonify({
            "success": True,
            "data": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search():
    """搜索（支持时间过滤）"""
    try:
        searcher = get_searcher_instance()
        crud = get_crud_instance()
        
        query = request.args.get('q', '')
        mode = request.args.get('mode', 'hybrid')
        entity = request.args.get('e', '')
        limit = int(request.args.get('limit', 20))
        time_filter = request.args.get('time', '')

        # LanceDB 不支持 limit <= 0，设置默认值
        if limit <= 0:
            limit = 20

        if not query and mode != 'entity':
            return jsonify({"success": False, "error": "缺少搜索关键词"}), 400

        # 执行搜索
        if mode == 'entity':
            if not entity:
                return jsonify({"success": False, "error": "实体搜索需要指定实体名"}), 400
            results = searcher.search_by_entity(entity, limit=limit)
        elif mode == 'vector':
            results = searcher.vector_search(query, limit=limit)
        else:  # hybrid
            results = searcher.hybrid_search(query, limit=limit)

        # 时间过滤
        start_time, end_time = get_time_range(time_filter)

        data = []
        for r in results:
            try:
                fact_time = datetime.fromisoformat(str(r.fact.timestamp))
            except (ValueError, TypeError) as e:
                logger.debug(f"时间解析失败 (fact_id={r.fact.id}): {e}")
                continue

            # 时间过滤
            if start_time and (fact_time < start_time or fact_time > end_time):
                continue

            data.append({
                "id": r.fact.id,
                "kind": r.fact.kind,
                "content": r.fact.content,
                "timestamp": r.fact.timestamp.isoformat() if hasattr(r.fact.timestamp, 'isoformat') else str(r.fact.timestamp),
                "entities": r.fact.entities,
                "score": round(r.score, 4),
                "match_type": r.match_type
            })

        return jsonify({
            "success": True,
            "data": {
                "query": query,
                "mode": mode,
                "time_filter": time_filter,
                "results": data,
                "count": len(data)
            }
        })
    except ValueError as e:
        # 参数解析错误
        logger.warning(f"搜索参数错误: {e}")
        return jsonify({"success": False, "error": "参数错误"}), 400
    except Exception as e:
        # 其他错误
        logger.error(f"搜索失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/relations', methods=['GET'])
def get_relations():
    """列出所有关系（用于关系列表页面）"""
    try:
        crud = get_crud_instance()
        
        # 获取所有关系
        relations = crud.list_relations(limit=5000)
        
        # 获取所有实体用于名称映射
        entities = crud.list_entities(limit=5000)
        entity_map = {e.slug: e.name for e in entities}
        
        result = []
        for r in relations:
            result.append({
                "id": r.id,
                "source": r.source_slug,
                "source_name": entity_map.get(r.source_slug, r.source_slug),
                "target": r.target_slug,
                "target_name": entity_map.get(r.target_slug, r.target_slug),
                "relation_type": r.relation_type,
                "confidence": r.confidence,
                "created_at": r.created_at,
                "is_current": r.is_current
            })
        
        return jsonify({
            "success": True,
            "data": result,
            "total": len(result)
        })
    except Exception as e:
        logger.error(f"获取关系列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 知识图谱 API ====================

@app.route('/graph')
def graph_page():
    """知识图谱可视化页面"""
    return render_template('graph.html')


@app.route('/api/graph', methods=['GET'])
def get_graph_data():
    """
    获取知识图谱数据
    
    返回节点（实体）和边（关系）数据，用于 force-graph 可视化
    """
    try:
        crud = get_crud_instance()
        
        # 获取所有实体
        entities = crud.list_entities(limit=5000)
        
        # 获取所有关系
        relations = crud.list_relations(limit=5000)
        
        # 实体类型颜色映射（处理 "PERSON(人物)" 格式）
        type_colors = {
            'PERSON': '#3b82f6',      # 蓝色 - 人物
            'ORG': '#22c55e',         # 绿色 - 组织
            'LOCATION': '#f59e0b',    # 橙色 - 地点
            'PLACE': '#f59e0b',       # 橙色 - 地点
            'TOOL': '#8b5cf6',        # 紫色 - 工具
            'SYSTEM': '#ec4899',      # 粉色 - 系统
            'PROJECT': '#06b6d4',     # 青色 - 项目
            'CONCEPT': '#6366f1',     # 靛蓝 - 概念
            'DOCUMENT': '#10b981',    # 绿色 - 文档
            'EVENT': '#ef4444',       # 红色 - 事件
            'TOPIC': '#14b8a6',       # 蓝绿 - 主题
            'PRODUCT': '#a855f7',     # 紫红 - 产品
        }
        default_color = '#94a3b8'     # 灰色 - 未知类型
        
        # 提取实体类型（处理 "PERSON(人物)" 格式）
        def extract_type_key(entity_type):
            if not entity_type:
                return 'CONCEPT'
            import re
            match = re.match(r'^([A-Z]+)', entity_type)
            return match.group(1) if match else entity_type
        
        # 关系类型颜色映射
        relation_colors = {
            '使用': '#3b82f6',        # 蓝色
            '用于': '#22c55e',        # 绿色
            '连接': '#f59e0b',        # 橙色
            '测试': '#8b5cf6',        # 紫色
            '认识': '#ec4899',        # 粉色
            '共事': '#06b6d4',        # 青色
            '相关': '#6366f1',        # 靛蓝
            '位于': '#ef4444',        # 红色
            '属于': '#14b8a6',        # 蓝绿
            '管理': '#a855f7',        # 紫红
            '创建': '#f97316',        # 深橙
            '提及': '#64748b',        # 灰色
        }
        
        # 构建节点数据 - 按 slug 去重
        nodes = []
        entity_slug_to_id = {}
        seen_slugs = set()
        
        # 先计算最大 memoryCount（用于归一化 importance）
        entity_memory_counts = {}
        for entity in entities:
            # 🔒 使用精确 slug（不再使用 .lower()，防止大小写冲突）
            if entity.slug not in seen_slugs:
                memories = crud.get_entity_memories(entity.slug)
                entity_memory_counts[entity.slug] = len(memories)
        
        max_memory_count = max(entity_memory_counts.values()) if entity_memory_counts else 1
        
        seen_slugs.clear()
        
        for entity in entities:
            # 🔒 使用精确 slug（不再使用 .lower()，防止大小写冲突）
            slug_exact = entity.slug
            
            # 去重：如果已经处理过这个 slug，跳过
            if slug_exact in seen_slugs:
                continue
            seen_slugs.add(slug_exact)
            
            node_id = len(nodes) + 1
            entity_slug_to_id[slug_exact] = node_id
            
            # 获取关联记忆数量
            memory_count = entity_memory_counts.get(slug_exact, 0)
            
            # 计算重要性（基于 memoryCount 归一化到 0-1）
            importance = min(1.0, memory_count / max_memory_count) if max_memory_count > 0 else 0.5
            
            # 提取类型键并获取颜色
            type_key = extract_type_key(entity.entity_type)
            node_color = type_colors.get(type_key, default_color)
            
            nodes.append({
                "id": node_id,
                "slug": entity.slug,
                "name": entity.name,
                "type": entity.entity_type,
                "color": node_color,
                "memoryCount": memory_count,
                "importance": round(importance, 2),  # 添加 importance 字段
                "summary": entity.summary or "",
            })
        
        # 构建边数据 - 从 relations 表读取
        links = []

        # 收集每个实体对之间的关系列表（用于计算曲率）
        entity_pair_relations = {}

        for relation in relations:
            # 🔒 使用精确 slug（不再使用 .lower()，防止大小写冲突）
            source_id = entity_slug_to_id.get(relation.source_slug)
            target_id = entity_slug_to_id.get(relation.target_slug)

            # 只添加两端实体都存在的边
            if source_id and target_id:
                # ✅ 正确做法：使用精确的源和目标去重，确保双向关系都能保留
                relation_key = f"{source_id}-{target_id}-{relation.relation_type}"

                if relation_key not in entity_pair_relations:
                    entity_pair_relations[relation_key] = {
                        "source": source_id,
                        "target": target_id,
                        "type": relation.relation_type,
                        "color": relation_colors.get(relation.relation_type, '#64748b'),
                        "confidence": relation.confidence,
                    }
                else:
                    # 如果已存在，只保留置信度更高的
                    if relation.confidence > entity_pair_relations[relation_key]["confidence"]:
                        entity_pair_relations[relation_key]["confidence"] = relation.confidence

        # 直接添加所有关系到 links（curvature 由前端 3D 渲染层处理）
        for rel in entity_pair_relations.values():
            links.append(rel.copy())
        
        # 统计信息
        type_counts = {}
        for node in nodes:
            t = node['type']
            type_counts[t] = type_counts.get(t, 0) + 1
        
        return jsonify({
            "success": True,
            "data": {
                "nodes": nodes,
                "links": links,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_links": len(links),
                    "type_counts": type_counts,
                }
            }
        })
    except Exception as e:
        logger.error(f"获取图谱数据失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 配置管理 ====================

from memory_bank.config import get_config, save_config, reset_config, update_config

@app.route('/config')
def config_page():
    """配置页面"""
    return render_template('config.html')


@app.route('/api/config/data', methods=['GET'])
def api_get_config():
    """获取当前配置"""
    try:
        config = get_config()
        return jsonify({
            "success": True,
            "data": config.to_dict()
        })
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config/update', methods=['POST'])
def api_update_config():
    """更新配置项"""
    try:
        data = request.get_json()
        section = data.get('section')
        key = data.get('key')
        value = data.get('value')

        if not all([section, key, value is not None]):
            return jsonify({"success": False, "error": "缺少参数"}), 400

        # 类型转换
        config = get_config()
        section_map = {
            "decay_rates": config.decay_rates,
            "confidence": config.confidence,
            "importance": config.importance,
            "lifecycle": config.lifecycle
        }

        if section in section_map:
            section_obj = section_map[section]
            if hasattr(section_obj, key):
                # 获取原始类型并转换
                original_value = getattr(section_obj, key)
                if isinstance(original_value, float):
                    value = float(value)
                elif isinstance(original_value, int):
                    value = int(value)

        success = update_config(section, key, value)

        if success:
            return jsonify({"success": True, "message": "配置已更新"})
        else:
            return jsonify({"success": False, "error": "更新失败"}), 500
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config/reset', methods=['POST'])
def api_reset_config():
    """重置配置为默认值"""
    try:
        config = reset_config()
        return jsonify({
            "success": True,
            "message": "配置已重置",
            "data": config.to_dict()
        })
    except Exception as e:
        logger.error(f"重置配置失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Lifecycle API (新增) ====================

@app.route('/api/lifecycle/stats', methods=['GET'])
def get_lifecycle_stats():
    """
    获取生命周期统计数据
    
    返回:
    - state_distribution: 各状态记忆数量
    - avg_effective_confidence: 平均有效置信度
    - cleanup_candidates: 待清理候选数量
    - distill_candidates: 待提炼候选数量
    """
    try:
        from memory_bank.lifecycle import (
            LifecycleState, effective_confidence, 
            cleanup_priority, distill_priority
        )
        
        crud = get_crud_instance()
        memories = crud.list_memories(limit=10000)
        
        # 状态分布统计
        state_counts = {
            LifecycleState.ACTIVE: 0,
            LifecycleState.ARCHIVED: 0,
            LifecycleState.SUPERSEDED: 0,
            LifecycleState.FORGOTTEN: 0
        }
        
        # 有效置信度统计
        effective_confidences = []
        
        # 候选统计
        cleanup_candidates = []
        distill_candidates = []
        
        for memory in memories:
            # 状态计数
            state = getattr(memory, 'lifecycle_state', 'ACTIVE')
            if state in state_counts:
                state_counts[state] += 1
            else:
                state_counts[LifecycleState.ACTIVE] += 1
            
            # 计算有效置信度
            try:
                eff_conf = effective_confidence(memory)
                effective_confidences.append(eff_conf)
            except:
                eff_conf = memory.confidence
                effective_confidences.append(eff_conf)
            
            # 清理候选
            try:
                cleanup_prio = cleanup_priority(memory)
                if cleanup_prio > 1.0:  # 阈值可调整
                    cleanup_candidates.append({
                        'id': memory.id,
                        'content': memory.content[:100] + '...' if len(memory.content) > 100 else memory.content,
                        'priority': round(cleanup_prio, 2)
                    })
            except:
                pass
            
            # 提炼候选
            try:
                distill_prio = distill_priority(memory)
                if distill_prio > 5.0:  # 阈值可调整
                    distill_candidates.append({
                        'id': memory.id,
                        'content': memory.content[:100] + '...' if len(memory.content) > 100 else memory.content,
                        'priority': round(distill_prio, 2)
                    })
            except:
                pass
        
        # 排序候选
        cleanup_candidates.sort(key=lambda x: x['priority'], reverse=True)
        distill_candidates.sort(key=lambda x: x['priority'], reverse=True)
        
        avg_eff_conf = sum(effective_confidences) / len(effective_confidences) if effective_confidences else 0
        
        return jsonify({
            "success": True,
            "data": {
                "total_memories": len(memories),
                "state_distribution": {
                    "active": state_counts[LifecycleState.ACTIVE],
                    "archived": state_counts[LifecycleState.ARCHIVED],
                    "superseded": state_counts[LifecycleState.SUPERSEDED],
                    "forgotten": state_counts[LifecycleState.FORGOTTEN]
                },
                "avg_effective_confidence": round(avg_eff_conf, 3),
                "cleanup_candidates_count": len(cleanup_candidates),
                "cleanup_candidates_preview": cleanup_candidates[:5],  # 只返回前5个
                "distill_candidates_count": len(distill_candidates),
                "distill_candidates_preview": distill_candidates[:5]
            }
        })
        
    except Exception as e:
        logger.error(f"获取生命周期统计失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/lifecycle/cleanup-candidates', methods=['GET'])
def get_cleanup_candidates():
    """
    获取清理候选列表（按 cleanup_priority 排序）
    
    Query params:
    - limit: 返回数量 (默认 50)
    - min_priority: 最小优先级阈值 (默认 1.0)
    """
    try:
        from memory_bank.lifecycle import cleanup_priority
        
        crud = get_crud_instance()
        limit = int(request.args.get('limit', 50))
        min_priority = float(request.args.get('min_priority', 1.0))
        
        memories = crud.list_memories(limit=10000)
        candidates = []
        
        for memory in memories:
            try:
                priority = cleanup_priority(memory)
                if priority >= min_priority:
                    # 计算有效置信度
                    from memory_bank.lifecycle import effective_confidence
                    eff_conf = effective_confidence(memory)
                    
                    candidates.append({
                        'id': memory.id,
                        'content': memory.content,
                        'priority': round(priority, 3),
                        'confidence': memory.confidence,
                        'effective_confidence': round(eff_conf, 3),
                        'importance': memory.importance,
                        'lifecycle_state': getattr(memory, 'lifecycle_state', 'ACTIVE'),
                        'created_at': memory.created_at,
                        'access_count': getattr(memory, 'access_count', 0)
                    })
            except Exception as e:
                logger.warning(f"计算记忆 {memory.id} 的清理优先级失败: {e}")
                continue
        
        # 按优先级降序排序
        candidates.sort(key=lambda x: x['priority'], reverse=True)
        
        return jsonify({
            "success": True,
            "data": {
                "candidates": candidates[:limit],
                "total": len(candidates),
                "threshold": min_priority
            }
        })
        
    except Exception as e:
        logger.error(f"获取清理候选失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/lifecycle/distill-candidates', methods=['GET'])
def get_distill_candidates():
    """
    获取提炼候选列表（按 distill_priority 排序）
    
    Query params:
    - limit: 返回数量 (默认 50)
    - min_priority: 最小优先级阈值 (默认 5.0)
    """
    try:
        from memory_bank.lifecycle import distill_priority, effective_confidence
        
        crud = get_crud_instance()
        limit = int(request.args.get('limit', 50))
        min_priority = float(request.args.get('min_priority', 5.0))
        
        memories = crud.list_memories(limit=10000)
        candidates = []
        
        for memory in memories:
            try:
                priority = distill_priority(memory)
                if priority >= min_priority:
                    eff_conf = effective_confidence(memory)
                    
                    candidates.append({
                        'id': memory.id,
                        'content': memory.content,
                        'priority': round(priority, 3),
                        'confidence': memory.confidence,
                        'effective_confidence': round(eff_conf, 3),
                        'importance': memory.importance,
                        'access_count': getattr(memory, 'access_count', 0),
                        'lifecycle_state': getattr(memory, 'lifecycle_state', 'ACTIVE'),
                        'created_at': memory.created_at
                    })
            except Exception as e:
                logger.warning(f"计算记忆 {memory.id} 的提炼优先级失败: {e}")
                continue
        
        # 按优先级降序排序
        candidates.sort(key=lambda x: x['priority'], reverse=True)
        
        return jsonify({
            "success": True,
            "data": {
                "candidates": candidates[:limit],
                "total": len(candidates),
                "threshold": min_priority
            }
        })
        
    except Exception as e:
        logger.error(f"获取提炼候选失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/lifecycle/batch-cleanup', methods=['POST'])
def batch_cleanup():
    """
    批量清理记忆（标记为 FORGOTTEN 或物理删除）
    
    Request body:
    {
        "memory_ids": ["id1", "id2", ...],
        "action": "mark_forgotten" | "delete_permanently"
    }
    """
    try:
        from memory_bank.lifecycle import LifecycleState
        
        data = request.get_json() or {}
        memory_ids = data.get('memory_ids', [])
        action = data.get('action', 'mark_forgotten')
        
        if not memory_ids:
            return jsonify({"success": False, "error": "未指定要清理的记忆ID"}), 400
        
        crud = get_crud_instance()
        results = []
        
        for memory_id in memory_ids:
            try:
                memory = crud.get_memory(memory_id)
                if not memory:
                    results.append({"id": memory_id, "status": "not_found"})
                    continue
                
                if action == 'delete_permanently':
                    crud.delete_memory(memory_id)
                    results.append({"id": memory_id, "status": "deleted"})
                else:
                    # 标记为遗忘
                    crud.update_memory(memory_id, lifecycle_state=LifecycleState.FORGOTTEN)
                    results.append({"id": memory_id, "status": "marked_forgotten"})
                    
            except Exception as e:
                logger.error(f"清理记忆 {memory_id} 失败: {e}")
                results.append({"id": memory_id, "status": "error", "error": str(e)})
        
        success_count = sum(1 for r in results if r['status'] in ['deleted', 'marked_forgotten'])
        
        return jsonify({
            "success": True,
            "data": {
                "processed": len(memory_ids),
                "success": success_count,
                "failed": len(memory_ids) - success_count,
                "results": results
            }
        })
        
    except Exception as e:
        logger.error(f"批量清理失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/lifecycle/batch-distill', methods=['POST'])
def batch_distill():
    """
    批量提炼记忆（标记为 ARCHIVED，可生成知识文档）
    
    Request body:
    {
        "memory_ids": ["id1", "id2", ...],
        "create_knowledge_doc": true | false
    }
    """
    try:
        from memory_bank.lifecycle import LifecycleState
        
        data = request.get_json() or {}
        memory_ids = data.get('memory_ids', [])
        create_doc = data.get('create_knowledge_doc', False)
        
        if not memory_ids:
            return jsonify({"success": False, "error": "未指定要提炼的记忆ID"}), 400
        
        crud = get_crud_instance()
        results = []
        distilled_contents = []
        
        for memory_id in memory_ids:
            try:
                memory = crud.get_memory(memory_id)
                if not memory:
                    results.append({"id": memory_id, "status": "not_found"})
                    continue
                
                # 标记为归档
                crud.update_memory(memory_id, lifecycle_state=LifecycleState.ARCHIVED)
                distilled_contents.append(memory.content)
                results.append({"id": memory_id, "status": "archived"})
                    
            except Exception as e:
                logger.error(f"提炼记忆 {memory_id} 失败: {e}")
                results.append({"id": memory_id, "status": "error", "error": str(e)})
        
        success_count = sum(1 for r in results if r['status'] == 'archived')
        
        response_data = {
            "processed": len(memory_ids),
            "success": success_count,
            "failed": len(memory_ids) - success_count,
            "results": results
        }
        
        # 如果要求生成知识文档，返回合并的内容
        if create_doc and distilled_contents:
            response_data['knowledge_doc'] = {
                "title": f"提炼知识汇总 ({len(distilled_contents)} 条)",
                "content": "\n\n---\n\n".join(distilled_contents),
                "source_count": len(distilled_contents)
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"批量提炼失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/memories/<memory_id>/confirm', methods=['POST'])
def confirm_memory(memory_id):
    """
    确认记忆（提高置信度）

    Request body: optional {"confidence_boost": float}
    """
    try:
        from memory_bank.lifecycle import LifecycleState

        crud = get_crud_instance()
        memory = crud.get_memory(memory_id)

        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404

        data = request.get_json() or {}
        boost = data.get('confidence_boost', 0.1)

        # Update confidence (capped at 1.0)
        new_confidence = min(1.0, memory.confidence + boost)

        # Update memory
        updated = crud.update_memory(
            memory_id,
            confidence=new_confidence
        )

        # Increment access count
        crud._increment_access_count(memory_id)

        if updated:
            return jsonify({
                "success": True,
                "data": {
                    "id": memory_id,
                    "old_confidence": memory.confidence,
                    "new_confidence": new_confidence
                }
            })
        else:
            return jsonify({"success": False, "error": "更新失败"}), 500

    except Exception as e:
        logger.error(f"确认记忆失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/memories/<memory_id>/contradictions', methods=['GET'])
def get_contradictions(memory_id):
    """查看矛盾"""
    try:
        from memory_bank.contradiction import detect_contradiction
        from memory_bank.lifecycle import effective_confidence

        crud = get_crud_instance()
        memory = crud.get_memory(memory_id)

        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404

        # Get all memories
        all_memories = crud.list_memories(limit=1000)

        # Find potential contradictions
        contradictions = []
        mem_effective = effective_confidence(memory)

        for other in all_memories:
            if other.id == memory_id:
                continue

            # Check content contradiction
            if detect_contradiction(memory.content, other.content):
                other_effective = effective_confidence(other)
                contradictions.append({
                    "id": other.id,
                    "content": other.content,
                    "effective_confidence": other_effective,
                    "difference": abs(mem_effective - other_effective)
                })

        return jsonify({
            "success": True,
            "data": {
                "memory_id": memory_id,
                "contradictions": contradictions
            }
        })

    except Exception as e:
        logger.error(f"获取矛盾失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/memories/<memory_id>/resolve', methods=['POST'])
def resolve_contradiction(memory_id):
    """
    解决冲突

    Request body: {"resolution": "accept_new|keep_old|merge", "target_id": "..."}
    """
    try:
        from memory_bank.lifecycle import LifecycleState

        data = request.get_json()
        if not data or 'resolution' not in data:
            return jsonify({"success": False, "error": "缺少 resolution 参数"}), 400

        resolution = data['resolution']
        if resolution not in ["accept_new", "keep_old", "merge"]:
            return jsonify({"success": False, "error": "无效的 resolution 值"}), 400

        crud = get_crud_instance()
        memory = crud.get_memory(memory_id)

        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404

        target_id = data.get('target_id')
        if not target_id:
            return jsonify({"success": False, "error": "缺少 target_id"}), 400

        target = crud.get_memory(target_id)
        if not target:
            return jsonify({"success": False, "error": "目标记忆不存在"}), 404

        if resolution == "accept_new":
            # Keep current, mark old as SUPERSEDED
            crud.update_memory(
                target_id,
                lifecycle_state=LifecycleState.SUPERSEDED,
                superseded_by=memory_id
            )
        elif resolution == "keep_old":
            # Keep old, mark new as SUPERSEDED
            crud.update_memory(
                memory_id,
                lifecycle_state=LifecycleState.SUPERSEDED,
                superseded_by=target_id
            )
        elif resolution == "merge":
            # Merge content (simple concatenation for now)
            merged_content = f"{memory.content}; {target.content}"
            crud.update_memory(
                memory_id,
                content=merged_content
            )
            crud.update_memory(
                target_id,
                lifecycle_state=LifecycleState.SUPERSEDED,
                superseded_by=memory_id
            )

        return jsonify({
            "success": True,
            "data": {
                "resolution": resolution,
                "memory_id": memory_id,
                "target_id": target_id
            }
        })

    except Exception as e:
        logger.error(f"解决冲突失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Relation Replacement API (新增) ====================

@app.route('/api/relations/create-or-replace', methods=['POST'])
def create_or_replace_relation():
    """
    创建或替代关系（支持不同目标替代）

    Request body: {
      "source": "entity_slug",
      "target": "entity_slug",
      "relation_type": "RELATION_TYPE",
      "confidence": 0.9,
      "source_memory_id": "memory_id",
      "replacement_reason": "update"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "缺少请求数据"}), 400

        source = data.get('source')
        target = data.get('target')
        relation_type = data.get('relation_type')
        confidence = data.get('confidence', 1.0)
        source_memory_id = data.get('source_memory_id', '')
        replacement_reason = data.get('replacement_reason', 'update')

        if not all([source, target, relation_type]):
            return jsonify({"success": False, "error": "缺少必填字段: source, target, relation_type"}), 400

        crud = get_crud_instance()
        relation = crud.create_or_replace_relation(
            source=source,
            target=target,
            relation_type=relation_type,
            confidence=confidence,
            source_memory_id=source_memory_id,
            replacement_reason=replacement_reason
        )

        return jsonify({
            "success": True,
            "data": relation.to_dict()
        })
    except Exception as e:
        logger.error(f"创建或替代关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/relations/<source_slug>/current', methods=['GET'])
def get_entity_current_relations_api(source_slug):
    """
    获取实体的所有当前关系（is_current=True）

    Returns: List of current relations
    """
    try:
        crud = get_crud_instance()
        relations = crud.get_entity_current_relations(source_slug)

        return jsonify({
            "success": True,
            "data": relations,
            "count": len(relations)
        })
    except Exception as e:
        logger.error(f"获取当前关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/relations/<source_slug>/<relation_type>/history', methods=['GET'])
def get_relation_history_api(source_slug, relation_type):
    """
    获取指定源实体和关系类型的历史记录

    Returns: List of historical relations
    """
    try:
        crud = get_crud_instance()
        history = crud.get_relation_history(source_slug, relation_type)

        return jsonify({
            "success": True,
            "data": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"获取关系历史失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/relations/batch-update', methods=['POST'])
def batch_update_relations_api():
    """
    批量更新关系

    Request body: {
      "updates": [
        {"source": "A", "target": "B", "relation_type": "RELATION", "confidence": 0.9}
      ]
    }
    """
    try:
        data = request.get_json()
        if not data or 'updates' not in data:
            return jsonify({"success": False, "error": "缺少 updates 字段"}), 400

        updates = data['updates']
        if not isinstance(updates, list):
            return jsonify({"success": False, "error": "updates 必须是数组"}), 400

        crud = get_crud_instance()
        results = crud.batch_update_relations(updates)

        return jsonify({
            "success": True,
            "data": {
                "total": len(results),
                "success_count": sum(1 for r in results if r['success']),
                "results": results
            }
        })
    except Exception as e:
        logger.error(f"批量更新关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/relations/<entity_slug>', methods=['DELETE'])
def delete_entity_relations_api(entity_slug):
    """
    删除实体的关系

    Query params:
      - relation_type: 指定关系类型（可选，如果为空则删除所有关系）
    """
    try:
        crud = get_crud_instance()
        relation_type = request.args.get('relation_type')

        crud.delete_entity_relations(entity_slug, relation_type)

        return jsonify({
            "success": True,
            "data": {
                "entity": entity_slug,
                "relation_type": relation_type or "all",
                "deleted": True
            }
        })
    except Exception as e:
        logger.error(f"删除实体关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "资源未找到"}), 404


@app.route('/api/relations/batch-delete', methods=['POST'])
def batch_delete_relations():
    """
    批量删除关系

    Body:
      - relation_ids: 关系 ID 列表
    """
    try:
        data = request.get_json()
        relation_ids = data.get('relation_ids', [])

        if not relation_ids:
            return jsonify({"success": False, "error": "请提供要删除的关系 ID"}), 400

        crud = get_crud_instance()
        deleted_count = 0
        failed_count = 0

        for relation_id in relation_ids:
            if crud.delete_relation(relation_id):
                deleted_count += 1
            else:
                failed_count += 1

        return jsonify({
            "success": True,
            "data": {
                "deleted": deleted_count,
                "failed": failed_count
            }
        })
    except Exception as e:
        logger.error(f"批量删除关系失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "资源未找到"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "服务器内部错误"}), 500


# ==================== 启动 ====================

if __name__ == '__main__':
    print("=" * 50)
    print("Memory Bank Web UI (LanceDB)")
    print("=" * 50)
    print(f"数据库: {DB_PATH}")
    print(f"嵌入模型: {EMBEDDING_MODEL} ({EMBEDDING_DIM}D)")
    print(f"监听: http://0.0.0.0:8088")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=8088,
        debug=False
    )
