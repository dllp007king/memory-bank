"""
SQLite 数据库管理

Schema 设计：
- facts: 事实表
- entities: 实体表
- fact_entities: 事实-实体关联表
- facts_fts: FTS5 全文搜索
- vec_embeddings: 向量存储（预留）
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


SCHEMA_VERSION = 3

SCHEMA_SQL = """
-- 事实表
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'W',
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_path TEXT,
    source_line INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 实体表
CREATE TABLE IF NOT EXISTS entities (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT,
    entity_type TEXT DEFAULT 'PERSON',
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 事实-实体关联表
CREATE TABLE IF NOT EXISTS fact_entities (
    fact_id TEXT NOT NULL,
    entity_slug TEXT NOT NULL,
    PRIMARY KEY (fact_id, entity_slug),
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_slug) REFERENCES entities(slug) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_facts_kind ON facts(kind);
CREATE INDEX IF NOT EXISTS idx_facts_timestamp ON facts(timestamp);
CREATE INDEX IF NOT EXISTS idx_facts_confidence ON facts(confidence);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);

-- FTS5 全文搜索（使用 content='' 外部内容模式）
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content,
    source_path,
    content='',
    tokenize='porter unicode61'
);

-- 触发器：插入时同步 FTS
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content, source_path) VALUES (NEW.rowid, NEW.content, NEW.source_path);
END;

-- 触发器：删除时同步 FTS
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, source_path) VALUES('delete', OLD.rowid, OLD.content, OLD.source_path);
END;

-- 触发器：更新时同步 FTS
CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content, source_path) VALUES('delete', OLD.rowid, OLD.content, OLD.source_path);
    INSERT INTO facts_fts(rowid, content, source_path) VALUES (NEW.rowid, NEW.content, NEW.source_path);
END;

-- 元数据表
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- 向量存储表（v2.0）
-- 存储 2560 维向量（Qwen3-Embedding-4B）
CREATE TABLE IF NOT EXISTS vec_embeddings (
    fact_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    dimension INTEGER DEFAULT 2560,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
);

-- 向量索引
CREATE INDEX IF NOT EXISTS idx_vec_fact_id ON vec_embeddings(fact_id);

-- NER 队列表（v3.0）
CREATE TABLE IF NOT EXISTS ner_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    model_used TEXT,
    result_json TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ner_queue_status ON ner_queue(status);
"""


class Database:
    """SQLite 数据库管理器"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self):
        """确保数据库目录存在"""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """获取数据库连接（线程安全）"""
        with self._lock:
            if self._conn is None:
                # check_same_thread=False 允许跨线程使用
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                # 启用 WAL 模式和外键约束
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
            return self._conn

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        try:
            conn = self.connect()
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def init_schema(self):
        """初始化数据库 Schema"""
        with self.transaction() as conn:
            # 执行主 Schema
            conn.executescript(SCHEMA_SQL)

            # 检查并记录版本
            cur = conn.execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,)
                )
            elif row["version"] < SCHEMA_VERSION:
                # 执行迁移
                self._migrate(conn, row["version"], SCHEMA_VERSION)
    
    def _migrate(self, conn, from_version: int, to_version: int):
        """执行数据库迁移"""
        if from_version < 2:
            # v1 -> v2: 添加向量表
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS vec_embeddings (
                    fact_id TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    dimension INTEGER DEFAULT 2560,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_vec_fact_id ON vec_embeddings(fact_id);
            """)
            print(f"[database] Migrated to v2")
        
        if from_version < 3:
            # v2 -> v3: 添加 NER 队列表
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ner_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    model_used TEXT,
                    result_json TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ner_queue_status ON ner_queue(status);
            """)
            print(f"[database] Migrated to v3")

        # 迁移成功后才更新版本号
        conn.execute("UPDATE schema_version SET version = ?", (to_version,))

    def get_schema_version(self) -> int:
        """获取当前 Schema 版本"""
        try:
            cur = self.connect().execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError:
            # 表不存在，返回版本 0
            return 0

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL（自动 commit）"""
        conn = self.connect()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """批量执行 SQL（自动 commit）"""
        conn = self.connect()
        cursor = conn.executemany(sql, params_list)
        conn.commit()
        return cursor


def init_database(db_path: str = ":memory:") -> Database:
    """初始化数据库并返回实例"""
    db = Database(db_path)
    db.init_schema()
    return db
