"""
实体类型推断缓存系统

使用多级匹配策略推断实体类型：
1. 缓存精确匹配
2. 关键词规则匹配
3. 嵌入向量相似度匹配
4. 默认 PERSON

复用现有的 Database 和 embedding 模块。
"""

import threading
from typing import Optional, Tuple, Dict, List
from .database import Database
from .embedding import embed_single, cosine_similarity, vector_to_blob


# ==================== 类型定义 ====================

TYPE_EXAMPLES = {
    'PERSON': ['张三', '李四', 'user', 'admin', 'developer', '用户', '开发者', 'liu', '萨拉塔斯', '阿尔萨斯', '吉安娜', '先驱'],
    'TOOL': ['vscode', 'git', 'docker', 'python', 'web', 'api', '工具', '编辑器', 'terminal'],
    'SYSTEM': ['linux', 'server', 'robot', 'xiaop', 'gateway', '系统', '服务器', 'myclaw'],
    'PROJECT': ['memory-bank', 'web-ui', 'project', '项目', '工程', 'app'],
    'CONCEPT': ['world', '世界', '概念', '理论', 'idea', 'model', '模型', 'search', 'entity', 'fact', 'fts', 'fts5', 'sqlite'],
    'PLACE': ['beijing', 'shanghai', 'office', 'home', '北京', '上海', '办公室', '艾泽拉斯', '永歌森林', '暴风城'],
    'EVENT': ['meeting', '会议', 'event', '事件', '更新', '上线'],
    'GAME': ['魔兽世界', 'wow', '游戏', 'game', '暴雪', '网易'],
    'ORGANIZATION': ['血精灵', '部落', '联盟', '公司', '团队', 'organization'],
}

KEYWORD_RULES = {
    # 工具（编程语言、框架、软件）
    'vscode': 'TOOL', 'vs code': 'TOOL', 'git': 'TOOL', 'docker': 'TOOL',
    'python': 'TOOL', 'javascript': 'TOOL', 'node.js': 'TOOL', 'nodejs': 'TOOL',
    'java': 'TOOL', 'golang': 'TOOL', 'rust': 'TOOL', 'typescript': 'TOOL',
    'api': 'TOOL', 'cli': 'TOOL', 'web': 'TOOL', 'ui': 'TOOL', 'terminal': 'TOOL',
    'react': 'TOOL', 'vue': 'TOOL', 'angular': 'TOOL', 'django': 'TOOL', 'flask': 'TOOL',
    'mysql': 'TOOL', 'postgresql': 'TOOL', 'mongodb': 'TOOL', 'redis': 'TOOL',
    'lancedb': 'TOOL', 'sqlite': 'TOOL', 'elasticsearch': 'TOOL',
    'postman': 'TOOL', 'github': 'TOOL', 'gitlab': 'TOOL',
    '工具': 'TOOL', '编辑器': 'TOOL', '框架': 'TOOL', '库': 'TOOL',
    
    # 系统
    'linux': 'SYSTEM', 'server': 'SYSTEM', 'robot': 'SYSTEM',
    'xiaop': 'SYSTEM', 'gateway': 'SYSTEM', 'system': 'SYSTEM',
    '系统': 'SYSTEM', '服务器': 'SYSTEM', 'myclaw': 'SYSTEM',
    
    # 项目
    'project': 'PROJECT', 'app': 'PROJECT', 'bank': 'PROJECT',
    '项目': 'PROJECT', '工程': 'PROJECT', '后台': 'PROJECT',
    '电商后台': 'PROJECT', '电商': 'PROJECT',
    
    # 概念
    'world': 'CONCEPT', '世界': 'CONCEPT', 'concept': 'CONCEPT',
    'idea': 'CONCEPT', 'theory': 'CONCEPT', 'model': 'TOOL',
    'search': 'CONCEPT', 'entity': 'CONCEPT', 'fact': 'CONCEPT',
    'fts': 'CONCEPT', 'fts5': 'CONCEPT',
    'bug': 'CONCEPT', '问题': 'CONCEPT', '待修复问题': 'CONCEPT',
    '接口': 'CONCEPT', '配置': 'CONCEPT', '配置文件': 'CONCEPT',
    
    # 地点
    'beijing': 'PLACE', 'shanghai': 'PLACE', 'office': 'PLACE',
    '北京': 'PLACE', '上海': 'PLACE', '办公室': 'PLACE',
    '艾泽拉斯': 'PLACE', '永歌森林': 'PLACE', '暴风城': 'PLACE', '部落': 'PLACE', '联盟': 'PLACE',
    
    # 事件
    'meeting': 'EVENT', '会议': 'EVENT', 'event': 'EVENT',
    '更新': 'EVENT', '上线': 'EVENT', '发布': 'EVENT', '部署': 'EVENT',
    '至暗之夜': 'EVENT', '三部曲': 'EVENT', '篇章': 'EVENT',
    '开发任务': 'EVENT', '任务': 'EVENT', '接口开发': 'EVENT',
    '验收': 'EVENT', '测试': 'EVENT', '交接': 'EVENT',
    
    # 游戏
    '魔兽世界': 'GAME', 'wow': 'GAME', '游戏': 'GAME', 'game': 'GAME',
    '暴雪': 'GAME', '网易': 'GAME', '魔兽': 'GAME',
    
    # 组织
    '血精灵': 'ORGANIZATION', '公司': 'ORGANIZATION', '团队': 'ORGANIZATION', '组织': 'ORGANIZATION',
    '运维团队': 'ORGANIZATION', '运维': 'ORGANIZATION', '开发团队': 'ORGANIZATION',
}

# 技术术语 -> 类型映射（优先级最高，精确匹配）
TECH_TYPE_MAP = {
    # 编程语言 -> TOOL
    'python': 'TOOL', 'javascript': 'TOOL', 'java': 'TOOL', 'go': 'TOOL',
    'rust': 'TOOL', 'typescript': 'TOOL', 'ruby': 'TOOL', 'php': 'TOOL',
    'swift': 'TOOL', 'kotlin': 'TOOL', 'scala': 'TOOL', 'lua': 'TOOL',
    'c++': 'TOOL', 'c#': 'TOOL',
    # Node.js 系列（包含各种变体）
    'node.js': 'TOOL', 'nodejs': 'TOOL', 'node': 'TOOL', 'npm': 'TOOL',
    'express': 'TOOL', 'koa': 'TOOL', 'next.js': 'TOOL',
    'js.node': 'TOOL', 'js': 'TOOL',  # 反向写法
    # 数据库 -> TOOL
    'mysql': 'TOOL', 'postgresql': 'TOOL', 'mongodb': 'TOOL',
    'redis': 'TOOL', 'lancedb': 'TOOL', 'sqlite': 'TOOL',
    # AI 模型 -> TOOL
    'gpt': 'TOOL', 'bert': 'TOOL', 'llm': 'TOOL', 'chatgpt': 'TOOL',
    'qwen': 'TOOL', 'minimax': 'TOOL', 'claude': 'TOOL',
}

# 常见中文姓氏（小写拼音）-> PERSON
SURNAME_PINYIN = {
    'wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'zhao', 'huang', 
    'zhou', 'wu', 'xu', 'sun', 'hu', 'zhu', 'gao', 'lin', 'he', 
    'guo', 'ma', 'luo', 'liang', 'song', 'zheng', 'xie', 'han',
    'tang', 'feng', 'yu', 'dong', 'xiao', 'cheng', 'cao', 'yuan',
    'deng', 'xu', 'fu', 'shen', 'zeng', 'peng', 'lv', 'su', 'lu',
    'jiang', 'cai', 'jia', 'ding', 'wei', 'xue', 'ye', 'yan',
}

# 缓存表 Schema
CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entity_type_cache (
    entity_name TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    embedding BLOB,
    source TEXT DEFAULT 'keyword',
    confidence REAL DEFAULT 1.0,
    hit_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_hit DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


class EntityTypeInferencer:
    """
    实体类型推断器
    
    多级匹配策略：
    1. 缓存表精确匹配（最快）
    2. 关键词规则匹配（快速）
    3. 嵌入相似度匹配（较慢但准确）
    4. 默认 PERSON（兜底）
    """
    
    def __init__(self, db: Database, similarity_threshold: float = 0.75):
        """
        初始化推断器
        
        Args:
            db: 数据库实例
            similarity_threshold: 嵌入相似度阈值（0-1）
        """
        self.db = db
        self.similarity_threshold = similarity_threshold
        self._lock = threading.Lock()
        
        # 类型代表向量缓存（内存中）
        self._type_embeddings: Dict[str, List[float]] = {}
        
        # 初始化
        self._init_cache_table()
        self._init_type_embeddings()
    
    def _init_cache_table(self):
        """初始化缓存表"""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS entity_type_cache (
                    entity_name TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    embedding BLOB,
                    source TEXT DEFAULT 'keyword',
                    confidence REAL DEFAULT 1.0,
                    hit_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_hit DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 创建索引
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_etc_type ON entity_type_cache(entity_type)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_etc_hits ON entity_type_cache(hit_count)")
            print("[entity_type_cache] 缓存表初始化成功")
        except Exception as e:
            print(f"[entity_type_cache] 缓存表初始化失败: {e}")
    
    def _init_type_embeddings(self):
        """
        预计算类型代表向量
        
        对每个类型的示例文本计算嵌入，取平均值作为该类型的代表向量。
        这些向量缓存在内存中，用于快速相似度匹配。
        """
        print("[entity_type_cache] 正在预计算类型代表向量...")
        
        for entity_type, examples in TYPE_EXAMPLES.items():
            embeddings = []
            
            for example in examples:
                emb = embed_single(example)
                if emb is not None:
                    embeddings.append(emb)
            
            if embeddings:
                # 计算平均向量
                avg_embedding = [
                    sum(e[i] for e in embeddings) / len(embeddings)
                    for i in range(len(embeddings[0]))
                ]
                self._type_embeddings[entity_type] = avg_embedding
                print(f"  - {entity_type}: {len(embeddings)}/{len(examples)} 个示例")
            else:
                print(f"  - {entity_type}: 嵌入服务不可用，跳过")
        
        print(f"[entity_type_cache] 完成，已缓存 {len(self._type_embeddings)} 个类型向量")
    
    def infer(self, entity_name: str) -> Tuple[str, float, str]:
        """
        推断实体类型
        
        Args:
            entity_name: 实体名称
            
        Returns:
            (entity_type, confidence, source)
            - entity_type: 推断的类型
            - confidence: 置信度 (0-1)
            - source: 来源 (cache/keyword/embedding/default)
        """
        if not entity_name:
            return ('PERSON', 0.0, 'default')
        
        entity_name_lower = entity_name.lower().strip()
        
        # 0. 技术术语精确匹配（优先级最高）
        if entity_name_lower in TECH_TYPE_MAP:
            entity_type = TECH_TYPE_MAP[entity_name_lower]
            self._save_to_cache(entity_name_lower, entity_type, 1.0, 'tech_term')
            return (entity_type, 1.0, 'tech_term')
        
        # 0.5 中文姓氏拼音 -> PERSON（优先级高）
        if entity_name_lower in SURNAME_PINYIN:
            self._save_to_cache(entity_name_lower, 'PERSON', 0.9, 'surname')
            return ('PERSON', 0.9, 'surname')
        
        # 1. 查缓存（精确匹配）
        cached = self._get_from_cache(entity_name_lower)
        if cached is not None:
            entity_type, confidence = cached
            self._update_hit(entity_name_lower)
            return (entity_type, confidence, 'cache')
        
        # 2. 关键词匹配（包含匹配，按长度排序优先匹配更长的）
        # 先按关键词长度降序排序，确保更具体的关键词优先匹配
        sorted_keywords = sorted(KEYWORD_RULES.items(), key=lambda x: len(x[0]), reverse=True)
        for keyword, entity_type in sorted_keywords:
            # 精确匹配或包含匹配（关键词长度 >= 3 才做包含匹配，避免误判）
            if entity_name_lower == keyword:
                self._save_to_cache(entity_name_lower, entity_type, 1.0, 'keyword')
                return (entity_type, 1.0, 'keyword')
            elif len(keyword) >= 3 and keyword in entity_name_lower:
                self._save_to_cache(entity_name_lower, entity_type, 1.0, 'keyword')
                return (entity_type, 1.0, 'keyword')
        
        # 3. 嵌入相似度匹配
        if self._type_embeddings:
            entity_emb = embed_single(entity_name)
            if entity_emb is not None:
                matched_type, confidence = self._similarity_match(entity_emb)
                if confidence >= self.similarity_threshold:
                    self._save_to_cache(
                        entity_name_lower, 
                        matched_type, 
                        confidence, 
                        'embedding',
                        entity_emb
                    )
                    return (matched_type, confidence, 'embedding')
        
        # 4. 默认 PERSON
        self._save_to_cache(entity_name_lower, 'PERSON', 0.5, 'default')
        return ('PERSON', 0.5, 'default')
    
    def _get_from_cache(self, entity_name: str) -> Optional[Tuple[str, float]]:
        """
        从缓存获取类型
        
        Args:
            entity_name: 实体名称（已小写化）
            
        Returns:
            (entity_type, confidence) 或 None
        """
        try:
            with self._lock:
                cur = self.db.execute(
                    "SELECT entity_type, confidence FROM entity_type_cache WHERE entity_name = ?",
                    (entity_name,)
                )
                row = cur.fetchone()
                if row:
                    return (row[0], row[1])
        except Exception as e:
            print(f"[entity_type_cache] 查询缓存失败: {e}")
        
        return None
    
    def _update_hit(self, entity_name: str):
        """
        更新命中次数和最后命中时间
        
        Args:
            entity_name: 实体名称
        """
        try:
            with self._lock:
                self.db.execute(
                    """
                    UPDATE entity_type_cache 
                    SET hit_count = hit_count + 1, 
                        last_hit = CURRENT_TIMESTAMP 
                    WHERE entity_name = ?
                    """,
                    (entity_name,)
                )
        except Exception as e:
            print(f"[entity_type_cache] 更新命中失败: {e}")
    
    def _similarity_match(self, entity_emb: List[float]) -> Tuple[str, float]:
        """
        嵌入相似度匹配
        
        计算输入实体向量与各类型代表向量的余弦相似度，
        返回最高分的类型。
        
        Args:
            entity_emb: 实体嵌入向量
            
        Returns:
            (matched_type, confidence)
        """
        best_type = 'PERSON'
        best_score = 0.0
        
        for entity_type, type_emb in self._type_embeddings.items():
            score = cosine_similarity(entity_emb, type_emb)
            if score > best_score:
                best_score = score
                best_type = entity_type
        
        return (best_type, best_score)
    
    def _save_to_cache(
        self, 
        entity_name: str, 
        entity_type: str, 
        confidence: float, 
        source: str,
        embedding: Optional[List[float]] = None
    ):
        """
        保存到缓存
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            confidence: 置信度
            source: 来源
            embedding: 嵌入向量（可选）
        """
        try:
            emb_blob = vector_to_blob(embedding) if embedding else None
            
            with self._lock:
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO entity_type_cache 
                    (entity_name, entity_type, embedding, source, confidence, hit_count)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (entity_name, entity_type, emb_blob, source, confidence)
                )
        except Exception as e:
            # 数据库锁定时静默失败，不影响主流程
            pass
    
    def get_cache_stats(self) -> dict:
        """
        获取缓存统计
        
        Returns:
            统计信息字典
        """
        try:
            stats = {}
            
            # 总数
            cur = self.db.execute("SELECT COUNT(*) FROM entity_type_cache")
            stats['total_count'] = cur.fetchone()[0]
            
            # 按类型统计
            cur = self.db.execute(
                "SELECT entity_type, COUNT(*) FROM entity_type_cache GROUP BY entity_type"
            )
            stats['by_type'] = {row[0]: row[1] for row in cur.fetchall()}
            
            # 按来源统计
            cur = self.db.execute(
                "SELECT source, COUNT(*) FROM entity_type_cache GROUP BY source"
            )
            stats['by_source'] = {row[0]: row[1] for row in cur.fetchall()}
            
            # 总命中次数
            cur = self.db.execute("SELECT SUM(hit_count) FROM entity_type_cache")
            stats['total_hits'] = cur.fetchone()[0] or 0
            
            # 类型代表向量数
            stats['type_embeddings'] = len(self._type_embeddings)
            
            return stats
        except Exception as e:
            print(f"[entity_type_cache] 获取统计失败: {e}")
            return {'error': str(e)}
    
    def cleanup_cache(self, max_size: int = 1000):
        """
        清理缓存（LRU 策略）
        
        当缓存超过 max_size 时，删除最久未使用的条目。
        
        Args:
            max_size: 最大缓存条目数
        """
        try:
            with self._lock:
                # 检查当前大小
                cur = self.db.execute("SELECT COUNT(*) FROM entity_type_cache")
                current_size = cur.fetchone()[0]
                
                if current_size > max_size:
                    # 删除最久未使用的条目
                    delete_count = current_size - max_size
                    self.db.execute(
                        """
                        DELETE FROM entity_type_cache 
                        WHERE entity_name IN (
                            SELECT entity_name FROM entity_type_cache 
                            ORDER BY last_hit ASC 
                            LIMIT ?
                        )
                        """,
                        (delete_count,)
                    )
                    print(f"[entity_type_cache] 已清理 {delete_count} 条缓存")
        except Exception as e:
            print(f"[entity_type_cache] 清理缓存失败: {e}")
    
    def clear_cache(self):
        """清空所有缓存"""
        try:
            with self._lock:
                self.db.execute("DELETE FROM entity_type_cache")
                print("[entity_type_cache] 已清空缓存")
        except Exception as e:
            print(f"[entity_type_cache] 清空缓存失败: {e}")
    
    def preload_keywords(self):
        """
        预加载关键词规则到缓存
        
        将所有 KEYWORD_RULES 中的关键词预先存入缓存表，
        避免后续重复匹配。
        """
        try:
            count = 0
            with self._lock:
                for keyword, entity_type in KEYWORD_RULES.items():
                    self.db.execute(
                        """
                        INSERT OR IGNORE INTO entity_type_cache 
                        (entity_name, entity_type, source, confidence, hit_count)
                        VALUES (?, ?, 'keyword', 1.0, 0)
                        """,
                        (keyword, entity_type)
                    )
                    count += 1
            print(f"[entity_type_cache] 已预加载 {count} 个关键词")
        except Exception as e:
            print(f"[entity_type_cache] 预加载关键词失败: {e}")


# ==================== 测试代码 ====================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/myclaw/.openclaw/workspace/memory-bank')
    
    from memory_bank.database import Database
    
    # 实际数据库路径
    DB_PATH = "/home/myclaw/.openclaw/workspace/.memory/index.sqlite"
    # 测试时可改为 ":memory:" 使用内存数据库
    
    print("=" * 60)
    print("实体类型推断缓存系统 - 测试")
    print("=" * 60)
    print(f"数据库: {DB_PATH}")
    print()
    
    # 初始化
    db = Database(DB_PATH)
    inferencer = EntityTypeInferencer(db)
    
    # 测试用例
    test_cases = ['vscode', 'search', 'entity', 'memory-bank', 'xiaop', '新实体']
    
    print("【推断测试】")
    print("-" * 60)
    for entity in test_cases:
        type_name, conf, source = inferencer.infer(entity)
        print(f'{entity:15} → {type_name:10} ({conf:.2f}, {source})')
    
    # 统计
    print()
    print("【缓存统计】")
    print("-" * 60)
    stats = inferencer.get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

# 扩展的技术术语映射
TECH_TYPE_MAP.update({
    # IDE 和编辑器
    'pycharm': 'TOOL', 'jupyter': 'TOOL', 'jupyter notebook': 'TOOL',
    'intellij': 'TOOL', 'intellij idea': 'TOOL', 'idea': 'TOOL',
    'vscode': 'TOOL', 'vs code': 'TOOL', 'vim': 'TOOL', 'emacs': 'TOOL',
    # 开发工具
    'anaconda': 'TOOL', 'conda': 'TOOL', 'pip': 'TOOL',
    # 概念术语（这些是技术概念，但不是工具）
    '机器学习': 'CONCEPT', '深度学习': 'CONCEPT', '数据分析': 'CONCEPT',
})
