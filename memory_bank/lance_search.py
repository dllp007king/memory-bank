"""
LanceDB 搜索模块

提供基于 LanceDB 的向量搜索、全文搜索和混合搜索功能。
支持 RRF (Reciprocal Rank Fusion) 融合排序。

依赖：
- lancedb: LanceDB Python SDK
- embedding: 本地向量化模块
- jieba: 中文分词
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

# LanceDB 导入
import lancedb
import pyarrow as pa

# 本地模块导入
from .models import Fact
from .embedding import embed_single, cosine_similarity, get_config
from .lifecycle import effective_confidence

# jieba 中文分词（使用共享词典管理器）
from .jieba_dict import init_jieba, tokenize_to_string

# 初始化词典
init_jieba()

# 日志记录器（必须在使用前定义）
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    fact: Fact
    score: float
    match_type: str  # "vector", "fts", "hybrid", "entity"


@dataclass
class LanceConfig:
    """LanceDB 配置"""
    db_path: str = "./lancedb"
    table_name: str = "memories"
    vector_column: str = "embedding"
    content_column: str = "content"
    id_column: str = "id"
    # 搜索参数
    default_limit: int = 10
    nprobes: int = 20  # 向量搜索探测数量
    refine_factor: int = 10  # 精细化因子


# 默认配置
_default_config: Optional[LanceConfig] = None


def get_lance_config() -> LanceConfig:
    """获取 LanceDB 配置"""
    global _default_config
    if _default_config is None:
        import os
        from pathlib import Path
        _default_config = LanceConfig(
            db_path=os.environ.get("LANCEDB_PATH", str(Path.home() / ".openclaw" / "workspace" / ".memory" / "lancedb")),
            table_name=os.environ.get("LANCEDB_TABLE", "memories"),
        )
    return _default_config


def set_lance_config(config: LanceConfig):
    """设置 LanceDB 配置"""
    global _default_config
    _default_config = config


class MemorySearch:
    """
    LanceDB 记忆搜索引擎
    
    提供向量搜索、全文搜索、混合搜索和实体搜索功能。
    使用 RRF 算法进行结果融合。
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        table_name: Optional[str] = None,
        config: Optional[LanceConfig] = None,
    ):
        """
        初始化搜索引擎
        
        Args:
            db_path: LanceDB 数据库路径
            table_name: 表名
            config: 完整配置对象
        """
        self.config = config or get_lance_config()
        if db_path:
            self.config.db_path = db_path
        if table_name:
            self.config.table_name = table_name
        
        # 延迟初始化
        self._db = None
        self._table = None
        self._embedding_config = get_config()
    
    @property
    def db(self):
        """延迟加载数据库连接"""
        if self._db is None:
            self._db = lancedb.connect(self.config.db_path)  # 使用 lancedb 而非 lance
        return self._db
    
    @property
    def table(self):
        """延迟加载表"""
        if self._table is None:
            try:
                self._table = self.db.open_table(self.config.table_name)
            except Exception as e:
                logger.warning(f"无法打开表 {self.config.table_name}: {e}")
                self._table = None
        return self._table
    
    def _get_query_vector(self, query: str) -> Optional[List[float]]:
        """获取查询文本的向量"""
        return embed_single(query, self._embedding_config)
    
    def _row_to_fact(self, row: Dict[str, Any]) -> Fact:
        """将 LanceDB 行转换为 Fact 对象"""
        return Fact(
            id=row.get("id", ""),
            kind=row.get("kind", "W"),
            content=row.get("content", ""),
            timestamp=datetime.fromisoformat(row["timestamp"]) if "timestamp" in row else datetime.now(),
            source_path=row.get("source_path", ""),
            source_line=row.get("source_line", 0),
            entities=row.get("entities", []) if isinstance(row.get("entities"), list) else [],
            confidence=row.get("confidence", 1.0),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
        )
    
    # ==================== 向量搜索 ====================
    
    def vector_search(
        self,
        query: str,
        limit: int = 10,
        filter_str: Optional[str] = None,
        use_effective_confidence: bool = True,
    ) -> List[SearchResult]:
        """
        向量相似度搜索

        Args:
            query: 查询文本
            limit: 返回结果数量
            filter_str: 预过滤条件（LanceDB SQL 语法）
            use_effective_confidence: 是否使用有效置信度排序

        Returns:
            搜索结果列表
        """
        if self.table is None:
            logger.warning("LanceDB 表未初始化")
            return []

        # 获取查询向量
        query_vec = self._get_query_vector(query)
        if query_vec is None:
            logger.warning(f"无法生成查询向量: {query}")
            return []

        try:
            # 构建向量搜索查询（使用 search(query_vector) 方法）
            search = self.table.search(query_vec)

            # 默认只返回 ACTIVE 状态
            final_filter = "lifecycle_state = 'ACTIVE'"
            if filter_str:
                final_filter = f"{final_filter} AND ({filter_str})"

            search = search.where(final_filter)

            # 获取更多结果用于重排序
            results = search.limit(limit * 3).to_list()

            # 转换结果并添加有效置信度
            search_results = []
            for row in results:  # row 已经是字典
                fact = self._row_to_fact(row)
                
                # 获取生命周期字段
                confidence = row.get("confidence", 1.0)
                decay_rate = row.get("decay_rate", 0.01)
                timestamp = row.get("created_at", row.get("timestamp"))
                
                # 计算有效置信度
                from datetime import datetime
                import math
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                days = (datetime.now() - timestamp).total_seconds() / 86400
                effective = confidence * math.exp(-decay_rate * days)
                
                # LanceDB 返回 _distance 字段，转换为相似度分数
                distance = row.get("_distance", 0.0)
                # 余弦距离转换为相似度 (假设使用余弦距离)
                relevance = 1.0 - distance if distance <= 1.0 else 1.0 / (1.0 + distance)
                
                # 最终得分 = 相关性 × 有效置信度
                final_score = relevance * effective if use_effective_confidence else relevance
                
                search_results.append({
                    "result": SearchResult(
                        fact=fact,
                        score=final_score,
                        match_type="vector",
                    ),
                    "effective_confidence": effective,
                })

            # 排序（按最终得分）
            search_results.sort(key=lambda x: x["result"].score, reverse=True)

            # 返回指定数量
            return [r["result"] for r in search_results[:limit]]

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    # ==================== 全文搜索 (FTS) ====================
    
    def fts_search(
        self,
        query: str,
        limit: int = 10,
        filter_str: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        全文搜索
        
        Args:
            query: 搜索查询
            limit: 返回结果数量
            filter_str: 预过滤条件
            
        Returns:
            搜索结果列表
        """
        if self.table is None:
            logger.warning("LanceDB 表未初始化")
            return []
        
        # 使用 jieba 对查询进行分词处理（搜索引擎模式，提高召回率）
        query_tokens = tokenize_to_string(query, mode="search")
        logger.debug(f"FTS 查询（分词后）: {query_tokens}")
        
        try:
            # 使用 LanceDB 的全文搜索（支持分词后的查询）
            search = self.table.search(
                query_tokens,
                query_type="fts",
            )
            
            # 添加预过滤（注意：FTS 可能不支持 filter，使用 where）
            if filter_str:
                try:
                    search = search.where(filter_str)
                except Exception:
                    logger.warning(f"FTS 不支持过滤条件: {filter_str}")
            
            # 执行搜索
            results = search.limit(limit).to_list()
            
            # 转换结果
            search_results = []
            for row in results:  # row 已经是字典
                fact = self._row_to_fact(row)
                # FTS 分数处理
                score = row.get("_score", 0.5)
                search_results.append(SearchResult(
                    fact=fact,
                    score=score,
                    match_type="fts",
                ))
            
            # 中文 fallback: 如果 FTS 无结果，使用简单字符串匹配
            if not search_results and any('\u4e00' <= c <= '\u9fff' for c in query):
                logger.info(f"FTS 无结果，使用字符串匹配 fallback: {query}")
                all_data = self.table.to_pandas()
                matches = []
                for _, row in all_data.iterrows():
                    content = row.get('content', '')
                    if query in content:
                        fact = self._row_to_fact(row.to_dict())
                        # 根据匹配位置计算分数（越靠前分数越高）
                        pos = content.find(query)
                        score = 1.0 - (pos / len(content)) if pos >= 0 else 0.5
                        matches.append(SearchResult(
                            fact=fact,
                            score=score,
                            match_type="fts",
                        ))
                # 按分数排序
                matches.sort(key=lambda x: x.score, reverse=True)
                search_results = matches[:limit]
            
            return search_results
            
        except Exception as e:
            logger.error(f"全文搜索失败: {e}")
            return []
    
    # ==================== 混合搜索 ====================
    
    def hybrid_search(
        self,
        query: str,
        vector_weight: float = 0.5,
        fts_weight: float = 0.5,
        limit: int = 10,
        filter_str: Optional[str] = None,
        fusion_method: str = "rrf",
    ) -> List[SearchResult]:
        """
        混合搜索（向量 + FTS）
        
        Args:
            query: 查询文本
            vector_weight: 向量搜索权重（仅用于 weighted 融合）
            fts_weight: FTS 权重（仅用于 weighted 融合）
            limit: 返回结果数量
            filter_str: 预过滤条件
            fusion_method: 融合方法 ("rrf" 或 "weighted")
            
        Returns:
            融合后的搜索结果列表
        """
        # 并行执行两种搜索
        vector_results = self.vector_search(query, limit * 2, filter_str)
        fts_results = self.fts_search(query, limit * 2, filter_str)
        
        # 降级策略
        if not vector_results and not fts_results:
            logger.warning("向量搜索和 FTS 搜索均无结果")
            return []
        elif not vector_results:
            logger.info("降级为纯 FTS 搜索")
            return fts_results[:limit]
        elif not fts_results:
            logger.info("降级为纯向量搜索")
            return vector_results[:limit]
        
        # 融合结果
        if fusion_method == "rrf":
            return self._rrf_fusion(vector_results, fts_results, limit)
        else:
            return self._weighted_fusion(
                vector_results, fts_results,
                vector_weight, fts_weight, limit
            )
    
    # ==================== RRF 融合排序 ====================
    
    def _rrf_fusion(
        self,
        vector_results: List[SearchResult],
        fts_results: List[SearchResult],
        limit: int,
        k: int = 60,
    ) -> List[SearchResult]:
        """
        RRF (Reciprocal Rank Fusion) 融合算法
        
        RRF 公式: score(d) = Σ 1/(k + rank(d))
        
        Args:
            vector_results: 向量搜索结果
            fts_results: FTS 搜索结果
            limit: 返回数量
            k: RRF 常数（默认 60）
            
        Returns:
            融合后的结果
        """
        # 收集所有文档 ID
        all_ids = set()
        for r in vector_results:
            all_ids.add(r.fact.id)
        for r in fts_results:
            all_ids.add(r.fact.id)
        
        # 构建 ID 到 rank 的映射
        vector_ranks = {r.fact.id: i + 1 for i, r in enumerate(vector_results)}
        fts_ranks = {r.fact.id: i + 1 for i, r in enumerate(fts_results)}
        
        # 构建 ID 到 Fact 的映射
        fact_map = {}
        for r in vector_results:
            fact_map[r.fact.id] = r.fact
        for r in fts_results:
            fact_map[r.fact.id] = r.fact
        
        # 计算 RRF 分数
        fused_scores = []
        for fact_id in all_ids:
            vec_rank = vector_ranks.get(fact_id, float('inf'))
            fts_rank = fts_ranks.get(fact_id, float('inf'))
            
            # RRF 公式
            rrf_score = 0.0
            if vec_rank != float('inf'):
                rrf_score += 1.0 / (k + vec_rank)
            if fts_rank != float('inf'):
                rrf_score += 1.0 / (k + fts_rank)
            
            # 确定匹配类型
            if fact_id in vector_ranks and fact_id in fts_ranks:
                match_type = "hybrid"
            elif fact_id in vector_ranks:
                match_type = "vector"
            else:
                match_type = "fts"
            
            fused_scores.append(SearchResult(
                fact=fact_map[fact_id],
                score=rrf_score,
                match_type=match_type,
            ))
        
        # 按 RRF 分数排序
        fused_scores.sort(key=lambda r: r.score, reverse=True)
        return fused_scores[:limit]
    
    def _weighted_fusion(
        self,
        vector_results: List[SearchResult],
        fts_results: List[SearchResult],
        vector_weight: float,
        fts_weight: float,
        limit: int,
    ) -> List[SearchResult]:
        """
        加权融合算法
        
        Args:
            vector_results: 向量搜索结果
            fts_results: FTS 搜索结果
            vector_weight: 向量权重
            fts_weight: FTS 权重
            limit: 返回数量
            
        Returns:
            融合后的结果
        """
        # 归一化分数
        def normalize_scores(results: List[SearchResult]) -> Dict[str, float]:
            if not results:
                return {}
            scores = [r.score for r in results]
            max_s, min_s = max(scores), min(scores)
            range_s = max_s - min_s if max_s != min_s else 1.0
            return {r.fact.id: (r.score - min_s) / range_s for r in results}
        
        vec_scores = normalize_scores(vector_results)
        fts_scores = normalize_scores(fts_results)
        
        # 合并所有 ID
        all_ids = set(vec_scores.keys()) | set(fts_scores.keys())
        
        # 构建事实映射
        fact_map = {}
        for r in vector_results:
            fact_map[r.fact.id] = r.fact
        for r in fts_results:
            fact_map[r.fact.id] = r.fact
        
        # 计算加权分数
        fused = []
        for fact_id in all_ids:
            vec_s = vec_scores.get(fact_id, 0.0)
            fts_s = fts_scores.get(fact_id, 0.0)
            
            final_score = vector_weight * vec_s + fts_weight * fts_s
            
            # 确定匹配类型
            if fact_id in vec_scores and fact_id in fts_scores:
                match_type = "hybrid"
            elif fact_id in vec_scores:
                match_type = "vector"
            else:
                match_type = "fts"
            
            fused.append(SearchResult(
                fact=fact_map[fact_id],
                score=final_score,
                match_type=match_type,
            ))
        
        # 排序并返回
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:limit]
    
    # ==================== 实体搜索 ====================
    
    def search_by_entity(
        self,
        entity_slug: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        按实体搜索
        
        Args:
            entity_slug: 实体标识
            limit: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        if self.table is None:
            logger.warning("LanceDB 表未初始化")
            return []
        
        try:
            # 使用标量过滤搜索包含指定实体的记录
            # 注意：LanceDB 对列表字段的过滤语法
            filter_str = f"array_contains(entities, '{entity_slug}')"
            
            results = self.table.search() \
                .where(filter_str) \
                .limit(limit) \
                .to_list()
            
            # 转换结果
            search_results = []
            for row in results:  # row 已经是字典
                fact = self._row_to_fact(row)
                search_results.append(SearchResult(
                    fact=fact,
                    score=1.0,
                    match_type="entity",
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"实体搜索失败: {e}")
            return []
    
    def search_by_entities(
        self,
        entity_slugs: List[str],
        match_all: bool = False,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        按多个实体搜索
        
        Args:
            entity_slugs: 实体标识列表
            match_all: 是否匹配所有实体（AND）或任一实体（OR）
            limit: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        if self.table is None or not entity_slugs:
            return []
        
        try:
            # 构建过滤条件
            conditions = [
                f"array_contains(entities, '{slug}')"
                for slug in entity_slugs
            ]
            
            if match_all:
                filter_str = " AND ".join(conditions)
            else:
                filter_str = " OR ".join(conditions)
            
            results = self.table.search() \
                .where(filter_str) \
                .limit(limit) \
                .to_list()
            
            # 转换结果
            search_results = []
            for row in results:  # row 已经是字典
                fact = self._row_to_fact(row)
                search_results.append(SearchResult(
                    fact=fact,
                    score=1.0,
                    match_type="entity",
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"多实体搜索失败: {e}")
            return []
    
    # ==================== 统一搜索接口 ====================
    
    def search(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 10,
        entity_filter: Optional[List[str]] = None,
        **kwargs,
    ) -> List[SearchResult]:
        """
        统一搜索接口
        
        Args:
            query: 查询文本
            mode: 搜索模式 ("vector", "fts", "hybrid")
            limit: 返回结果数量
            entity_filter: 实体过滤列表
            **kwargs: 其他参数
            
        Returns:
            搜索结果列表
        """
        # 构建过滤条件
        filter_str = None
        if entity_filter:
            conditions = [
                f"array_contains(entities, '{slug}')"
                for slug in entity_filter
            ]
            filter_str = " OR ".join(conditions)
        
        # 根据模式选择搜索方法
        if mode == "vector":
            return self.vector_search(query, limit, filter_str)
        elif mode == "fts":
            return self.fts_search(query, limit, filter_str)
        else:  # hybrid
            return self.hybrid_search(query, limit=limit, filter_str=filter_str, **kwargs)


# ==================== 兼容现有 search.py 接口的函数 ====================

# 默认搜索引擎实例
_default_searcher: Optional[MemorySearch] = None


def get_searcher() -> MemorySearch:
    """获取默认搜索引擎实例"""
    global _default_searcher
    if _default_searcher is None:
        _default_searcher = MemorySearch()
    return _default_searcher


def search_facts(
    query: str,
    limit: int = 10,
    mode: str = "hybrid",
) -> List[SearchResult]:
    """
    兼容接口：搜索事实
    
    Args:
        query: 查询文本
        limit: 返回结果数量
        mode: 搜索模式
        
    Returns:
        搜索结果列表
    """
    return get_searcher().search(query, mode=mode, limit=limit)


def vector_search(
    query: str,
    limit: int = 10,
) -> List[SearchResult]:
    """
    兼容接口：向量搜索
    
    Args:
        query: 查询文本
        limit: 返回结果数量
        
    Returns:
        搜索结果列表
    """
    return get_searcher().vector_search(query, limit)


def hybrid_search(
    query: str,
    vector_weight: float = 0.5,
    text_weight: float = 0.5,
    limit: int = 10,
) -> List[SearchResult]:
    """
    兼容接口：混合搜索
    
    Args:
        query: 查询文本
        vector_weight: 向量权重
        text_weight: 文本权重
        limit: 返回结果数量
        
    Returns:
        搜索结果列表
    """
    return get_searcher().hybrid_search(
        query,
        vector_weight=vector_weight,
        fts_weight=text_weight,
        limit=limit,
    )


def search_by_entity(
    entity_slug: str,
    limit: int = 10,
) -> List[SearchResult]:
    """
    兼容接口：按实体搜索
    
    Args:
        entity_slug: 实体标识
        limit: 返回结果数量
        
    Returns:
        搜索结果列表
    """
    return get_searcher().search_by_entity(entity_slug, limit)


def fuse_results(
    vector_results: List[SearchResult],
    fts_results: List[SearchResult],
    vector_weight: float = 0.5,
    text_weight: float = 0.5,
    limit: int = 10,
) -> List[SearchResult]:
    """
    兼容接口：融合结果
    
    Args:
        vector_results: 向量搜索结果
        fts_results: FTS 搜索结果
        vector_weight: 向量权重
        text_weight: 文本权重
        limit: 返回结果数量
        
    Returns:
        融合后的结果列表
    """
    searcher = get_searcher()
    return searcher._weighted_fusion(
        vector_results, fts_results,
        vector_weight, text_weight, limit
    )


# ==================== 数据导入工具 ====================

def create_table_from_facts(
    facts: List[Fact],
    db_path: Optional[str] = None,
    table_name: Optional[str] = None,
) -> bool:
    """
    从 Fact 列表创建 LanceDB 表
    
    Args:
        facts: 事实列表
        db_path: 数据库路径
        table_name: 表名
        
    Returns:
        是否成功
    """
    config = get_lance_config()
    if db_path:
        config.db_path = db_path
    if table_name:
        config.table_name = table_name
    
    try:
        # 连接数据库（使用 lancedb 而非 lance）
        db = lancedb.connect(config.db_path)
        
        # 准备数据
        records = []
        embedding_config = get_config()
        
        for fact in facts:
            # 生成向量
            embedding = embed_single(fact.content, embedding_config)
            if embedding is None:
                logger.warning(f"无法为 fact {fact.id} 生成向量，跳过")
                continue
            
            record = {
                "id": fact.id,
                "kind": fact.kind,
                "content": fact.content,
                "timestamp": fact.timestamp.isoformat(),
                "source_path": fact.source_path,
                "source_line": fact.source_line,
                "entities": fact.entities,
                "confidence": fact.confidence,
                "created_at": fact.created_at.isoformat(),
                "updated_at": fact.updated_at.isoformat(),
                "embedding": embedding,
            }
            records.append(record)
        
        if not records:
            logger.warning("没有有效记录可导入")
            return False
        
        # 创建表
        db.create_table(config.table_name, records)
        logger.info(f"成功创建表 {config.table_name}，共 {len(records)} 条记录")
        return True
        
    except Exception as e:
        logger.error(f"创建表失败: {e}")
        return False
