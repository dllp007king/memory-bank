"""
向量化模块

使用 llama.cpp HTTP Server (Qwen3-Embedding-4B-Q8) 进行文本向量化。

配置：
- LLAMA_SERVER_URL: llama-server 地址（默认 http://localhost:8080）
- LLAMA_EMBEDDING_BIN: llama-embedding 二进制路径（备用）
- LLAMA_MODEL_PATH: GGUF 模型路径

特性：
- 支持 50 并发限制的嵌入服务
- 自动排队机制
- 线程安全
"""

import json
import subprocess
import urllib.request
import urllib.error
from typing import List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
import os
import struct
import threading
import sys
from pathlib import Path

# 导入并发客户端（50并发限制）
# 添加父目录到路径以支持绝对导入
_parent_dir = str(Path(__file__).parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from embedding.concurrent_client import ConcurrentEmbeddingClient


@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    server_url: str = "http://localhost:8080"
    embedding_bin: str = "/mnt/sdb/models/llama.cpp/build/bin/llama-embedding"
    model_path: str = "/mnt/sdb/models/llama.cpp/Qwen3-Embedding-4B-Q8/Qwen3-Embedding-4B-Q8_0.gguf"
    dimension: int = 2560  # Qwen3-Embedding-4B 维度
    timeout: int = 60
    max_concurrent: int = 50  # 最大并发数


# 默认配置
_default_config: Optional[EmbeddingConfig] = None

# 全局并发客户端（单例）
_global_concurrent_client: Optional[ConcurrentEmbeddingClient] = None
_client_lock = threading.Lock()


def get_config() -> EmbeddingConfig:
    """获取配置"""
    global _default_config
    if _default_config is None:
        _default_config = EmbeddingConfig(
            server_url=os.environ.get("LLAMA_SERVER_URL", "http://localhost:8080"),
            embedding_bin=os.environ.get("LLAMA_EMBEDDING_BIN", "/mnt/sdb/models/llama.cpp/build/bin/llama-embedding"),
            model_path=os.environ.get("LLAMA_MODEL_PATH", "/mnt/sdb/models/llama.cpp/Qwen3-Embedding-4B-Q8/Qwen3-Embedding-4B-Q8_0.gguf"),
        )
    return _default_config


def set_config(config: EmbeddingConfig):
    """设置配置"""
    global _default_config
    _default_config = config


def get_embed_client(
    base_url: Optional[str] = None,
    max_concurrent: int = 50,
    timeout: int = 60,
) -> ConcurrentEmbeddingClient:
    """
    获取全局并发嵌入客户端（单例）
    
    Args:
        base_url: 嵌入服务地址（默认使用配置中的 server_url）
        max_concurrent: 最大并发数（默认 50）
        timeout: 超时时间（秒）
        
    Returns:
        ConcurrentEmbeddingClient 实例
        
    特性：
        - 50 并发限制
        - 超过限制自动排队
        - 线程安全
    """
    global _global_concurrent_client
    
    with _client_lock:
        if _global_concurrent_client is None:
            config = get_config()
            url = base_url or f"{config.server_url}/v1/embeddings"
            _global_concurrent_client = ConcurrentEmbeddingClient(
                base_url=url,
                max_concurrent=max_concurrent,
                timeout=timeout,
            )
        return _global_concurrent_client


def check_server_health(config: Optional[EmbeddingConfig] = None) -> bool:
    """检查 llama-server 是否运行"""
    config = config or get_config()
    try:
        req = urllib.request.Request(f"{config.server_url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def embed_via_server(
    texts: List[str],
    config: Optional[EmbeddingConfig] = None,
) -> Optional[List[List[float]]]:
    """
    通过 llama-server HTTP API 获取嵌入向量
    
    Args:
        texts: 文本列表
        config: 配置
        
    Returns:
        嵌入向量列表，失败返回 None
    """
    config = config or get_config()
    
    try:
        # 构建请求
        payload = {
            "content": texts[0] if len(texts) == 1 else texts,
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{config.server_url}/embedding",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=config.timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            
            # 解析响应 - llama-server 返回 [{"index": 0, "embedding": [[...]]}]
            if isinstance(result, list):
                # llama-server 格式
                embeddings = []
                for item in result:
                    if "embedding" in item:
                        emb = item["embedding"]
                        # embedding 可能是嵌套列表 [[...]]，需要展平
                        if isinstance(emb, list) and len(emb) == 1 and isinstance(emb[0], list):
                            emb = emb[0]
                        embeddings.append(emb)
                return embeddings if embeddings else None
            elif isinstance(result, dict):
                # 兼容其他格式
                if "embedding" in result:
                    return [result["embedding"]]
                elif "embeddings" in result:
                    return result["embeddings"]
            
            return None
                
    except Exception as e:
        print(f"[embedding] Server error: {e}")
        return None


def embed_via_cli(
    texts: List[str],
    config: Optional[EmbeddingConfig] = None,
) -> Optional[List[List[float]]]:
    """
    通过 llama-embedding 命令行工具获取嵌入向量
    
    Args:
        texts: 文本列表
        config: 配置
        
    Returns:
        嵌入向量列表，失败返回 None
    """
    config = config or get_config()
    
    try:
        embeddings = []
        for text in texts:
            # 运行 llama-embedding
            proc = subprocess.run(
                [
                    config.embedding_bin,
                    "-m", config.model_path,
                    "-c", "512",
                    "-ub", "512",
                    "--no-warmup",
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=config.timeout,
            )
            
            if proc.returncode != 0:
                print(f"[embedding] CLI error: {proc.stderr.decode()}")
                return None
            
            # 解析输出
            output = proc.stdout.decode("utf-8")
            embedding = parse_embedding_output(output)
            if embedding is None:
                return None
            embeddings.append(embedding)
            
        return embeddings
        
    except subprocess.TimeoutExpired:
        print("[embedding] CLI timeout")
        return None
    except Exception as e:
        print(f"[embedding] CLI error: {e}")
        return None


def parse_embedding_output(output: str) -> Optional[List[float]]:
    """
    解析 llama-embedding 输出
    
    格式：embedding 0:  0.001  0.002  0.003 ...
    """
    try:
        for line in output.split("\n"):
            if line.startswith("embedding"):
                # 提取数值部分
                parts = line.split(":")
                if len(parts) >= 2:
                    values_str = parts[1].strip()
                    values = [float(v) for v in values_str.split()]
                    return values
        return None
    except Exception:
        return None


def embed(
    texts: List[str],
    config: Optional[EmbeddingConfig] = None,
    prefer_server: bool = True,
    use_concurrent: bool = False,
) -> Optional[List[List[float]]]:
    """
    获取文本嵌入向量
    
    Args:
        texts: 文本列表
        config: 配置
        prefer_server: 是否优先使用服务器
        use_concurrent: 是否使用并发客户端（50并发限制）
        
    Returns:
        嵌入向量列表，失败返回 None
        
    注意：
        use_concurrent=True 时，使用 50 并发限制的客户端
        超过限制会自动排队等待
    """
    config = config or get_config()
    
    # 使用并发客户端（50 并发限制）
    if use_concurrent:
        try:
            client = get_embed_client(
                max_concurrent=config.max_concurrent,
                timeout=config.timeout,
            )
            results = []
            for text in texts:
                result = client.embed(text)
                results.append(result)
            return results if all(r is not None for r in results) else None
        except Exception as e:
            print(f"[embedding] Concurrent client error: {e}")
            # 回退到传统方式
    
    # 传统方式：优先使用 HTTP Server，失败则回退到 CLI
    if prefer_server and check_server_health(config):
        result = embed_via_server(texts, config)
        if result is not None:
            return result
    
    # 回退到 CLI
    return embed_via_cli(texts, config)


def embed_batch(
    texts: List[str],
    config: Optional[EmbeddingConfig] = None,
    use_concurrent: bool = True,
) -> List[Optional[List[float]]]:
    """
    批量获取文本嵌入向量（推荐使用）
    
    Args:
        texts: 文本列表
        config: 配置
        use_concurrent: 是否使用并发客户端（默认 True，50并发限制）
        
    Returns:
        嵌入向量列表（可能包含 None）
        
    特性：
        - 自动使用 50 并发限制
        - 超过限制自动排队
        - 单个失败不影响其他
    """
    config = config or get_config()
    
    if use_concurrent:
        try:
            client = get_embed_client(
                max_concurrent=config.max_concurrent,
                timeout=config.timeout,
            )
            return client.embed_batch(texts)
        except Exception as e:
            print(f"[embedding] Batch concurrent error: {e}")
            # 回退到传统方式
    
    # 传统方式
    result = embed(texts, config, use_concurrent=False)
    if result is None:
        return [None] * len(texts)
    return result


def embed_single(
    text: str,
    config: Optional[EmbeddingConfig] = None,
    use_concurrent: bool = False,
) -> Optional[List[float]]:
    """
    获取单个文本的嵌入向量
    
    Args:
        text: 文本
        config: 配置
        use_concurrent: 是否使用并发客户端
        
    Returns:
        嵌入向量，失败返回 None
    """
    result = embed([text], config, use_concurrent=use_concurrent)
    return result[0] if result else None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    计算余弦相似度
    
    Args:
        a: 向量 A
        b: 向量 B
        
    Returns:
        相似度 (0-1)
    """
    a_arr = np.array(a)
    b_arr = np.array(b)
    
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot / (norm_a * norm_b))


def vector_to_blob(vector: List[float]) -> bytes:
    """将向量转换为 BLOB 存储"""
    return struct.pack(f"{len(vector)}f", *vector)


def blob_to_vector(blob: bytes, dimension: int) -> List[float]:
    """将 BLOB 转换为向量"""
    return list(struct.unpack(f"{dimension}f", blob))


# ==================== 批量嵌入管理 ====================

class EmbeddingManager:
    """
    嵌入管理器
    
    特性：
        - 自动使用 50 并发限制的客户端
        - 内置缓存
        - 批量优化
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None, use_concurrent: bool = True):
        """
        初始化嵌入管理器
        
        Args:
            config: 配置
            use_concurrent: 是否使用并发客户端（默认 True）
        """
        self.config = config or get_config()
        self.use_concurrent = use_concurrent
        self._cache: dict = {}
    
    def embed(self, text: str) -> Optional[List[float]]:
        """
        获取单个文本的嵌入（带缓存）
        
        Args:
            text: 文本
            
        Returns:
            嵌入向量，失败返回 None
        """
        if text in self._cache:
            return self._cache[text]
        
        result = embed_single(text, self.config, use_concurrent=self.use_concurrent)
        if result is not None:
            self._cache[text] = result
        return result
    
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量获取嵌入（推荐使用）
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
            
        特性：
            - 自动使用 50 并发限制
            - 智能缓存
        """
        results = []
        uncached = []
        uncached_indices = []
        
        # 检查缓存
        for i, text in enumerate(texts):
            if text in self._cache:
                results.append(self._cache[text])
            else:
                results.append(None)
                uncached.append(text)
                uncached_indices.append(i)
        
        # 批量获取未缓存的（使用并发客户端）
        if uncached:
            embeddings = embed_batch(uncached, self.config, use_concurrent=self.use_concurrent)
            for idx, text, emb in zip(uncached_indices, uncached, embeddings):
                results[idx] = emb
                if emb is not None:
                    self._cache[text] = emb
        
        return results
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def search_similar(
        self,
        query: str,
        candidates: List[Tuple[str, List[float]]],
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        搜索相似文本
        
        Args:
            query: 查询文本
            candidates: 候选列表 [(id, vector), ...]
            top_k: 返回前 K 个
            
        Returns:
            [(id, similarity), ...]
        """
        query_vec = self.embed(query)
        if query_vec is None:
            return []
        
        scores = []
        for id_, vec in candidates:
            if vec is not None:
                sim = cosine_similarity(query_vec, vec)
                scores.append((id_, sim))
        
        # 按相似度排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def get_stats(self) -> dict:
        """
        获取并发客户端统计信息
        
        Returns:
            统计字典，包含：
            - total_requests: 总请求数
            - success: 成功数
            - failed: 失败数
            - rejected: 被拒绝数（超过并发限制）
        """
        if self.use_concurrent:
            client = get_embed_client()
            return client.get_stats()
        return {"cache_size": len(self._cache)}


# ==================== 便捷接口 ====================

def get_stats() -> dict:
    """
    获取全局并发客户端统计信息
    
    Returns:
        统计字典
    """
    client = get_embed_client()
    return client.get_stats()
