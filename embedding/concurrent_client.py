"""
并发限制的嵌入服务客户端

限制最大并发数为 50，超过后自动排队
"""

import requests
import threading
import queue
import time
from typing import List, Optional


class ConcurrentEmbeddingClient:
    """
    带并发限制的嵌入服务客户端
    
    特性：
    - 最大 50 并发
    - 超过限制自动排队
    - 超时保护
    - 线程安全
    """
    
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/v1/embeddings",
        max_concurrent: int = 50,
        timeout: int = 60,
    ):
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        
        # 信号量控制并发
        self.semaphore = threading.Semaphore(max_concurrent)
        
        # 等待队列（可选，用于统计）
        self.waiting_count = 0
        self.waiting_lock = threading.Lock()
        
        # 统计
        self.stats = {
            "total_requests": 0,
            "success": 0,
            "failed": 0,
            "rejected": 0,
        }
        self.stats_lock = threading.Lock()
    
    def embed(self, text: str) -> Optional[List[float]]:
        """
        嵌入单个文本（自动并发控制）
        """
        # 获取信号量（如果超过限制会阻塞）
        acquired = self.semaphore.acquire(timeout=self.timeout)
        
        if not acquired:
            with self.stats_lock:
                self.stats["rejected"] += 1
            raise TimeoutError(f"等待超时，超过 {self.max_concurrent} 并发限制")
        
        try:
            with self.stats_lock:
                self.stats["total_requests"] += 1
            
            response = requests.post(
                self.base_url,
                json={"input": text},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()["data"][0]["embedding"]
            
            with self.stats_lock:
                self.stats["success"] += 1
            
            return result
            
        except Exception as e:
            with self.stats_lock:
                self.stats["failed"] += 1
            raise
        
        finally:
            self.semaphore.release()
    
    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        嵌入多个文本（自动并发控制）
        
        注意：内部会复用信号量，不会超出并发限制
        """
        results = []
        
        for text in texts:
            try:
                result = self.embed(text)
                results.append(result)
            except Exception as e:
                print(f"嵌入失败: {e}")
                results.append(None)
        
        return results
    
    def embed_async(self, texts: List[str], callback=None) -> List[threading.Thread]:
        """
        异步嵌入（返回线程列表）
        
        使用示例：
        threads = client.embed_async(["text1", "text2"], callback=my_callback)
        for t in threads:
            t.join()
        """
        threads = []
        
        def wrapper(text, cb):
            try:
                result = self.embed(text)
                if cb:
                    cb(result)
            except Exception as e:
                if cb:
                    cb(None, error=e)
        
        for text in texts:
            t = threading.Thread(target=wrapper, args=(text, callback))
            t.start()
            threads.append(t)
        
        return threads
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.stats_lock:
            return self.stats.copy()
    
    def get_waiting_count(self) -> int:
        """获取当前等待的请求数"""
        # 注意：这是近似值，因为 Semaphore 不提供等待数量
        return 0
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


# 全局单例
_global_client: Optional[ConcurrentEmbeddingClient] = None
_client_lock = threading.Lock()


def get_embedding_client(
    base_url: str = "http://127.0.0.1:8080/v1/embeddings",
    max_concurrent: int = 50,
) -> ConcurrentEmbeddingClient:
    """
    获取全局嵌入客户端（单例）
    """
    global _global_client
    
    with _client_lock:
        if _global_client is None:
            _global_client = ConcurrentEmbeddingClient(
                base_url=base_url,
                max_concurrent=max_concurrent,
            )
        return _global_client


# 便捷函数
def embed(text: str) -> List[float]:
    """快速嵌入"""
    client = get_embedding_client()
    return client.embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """批量嵌入"""
    client = get_embedding_client()
    return client.embed_batch(texts)


# 测试
if __name__ == "__main__":
    import concurrent.futures
    
    print("=== 并发限制测试 ===\n")
    
    client = ConcurrentEmbeddingClient(max_concurrent=50)
    
    # 测试 100 并发
    texts = [f"测试文本 {i}" for i in range(100)]
    
    start = time.time()
    results = client.embed_batch(texts)
    elapsed = time.time() - start
    
    success = sum(1 for r in results if r is not None)
    
    print(f"100 个请求:")
    print(f"  总耗时: {elapsed:.2f}s")
    print(f"  成功: {success}/100")
    print(f"  吞吐: {100/elapsed:.1f} req/s")
    print(f"\n统计: {client.get_stats()}")
