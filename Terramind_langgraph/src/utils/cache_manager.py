import hashlib
import json
import pickle
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from src.config.settings import settings

class CacheManager:
    """
    Manager for caching query responses and embeddings.
    Implements TTL (Time To Live) for cache entries.
    """

    def __init__(self, cache_dir: Path = None, ttl_hours: int = 24):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
            ttl_hours: Time to live for cache entries in hours
        """
        self.cache_dir = cache_dir or (settings.BASE_DIR / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

        # Separate cache directories
        self.response_cache_dir = self.cache_dir / "responses"
        self.embedding_cache_dir = self.cache_dir / "embeddings"
        self.tool_cache_dir = self.cache_dir / "tools"

        for dir_path in [self.response_cache_dir, self.embedding_cache_dir, self.tool_cache_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, data: Any) -> str:
        """
        Generate a cache key from data.

        Args:
            data: Data to generate key from

        Returns:
            SHA256 hash as hex string
        """
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)

        return hashlib.sha256(data_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str, cache_type: str = "response") -> Path:
        """Get the file path for a cache entry."""
        if cache_type == "response":
            return self.response_cache_dir / f"{cache_key}.pkl"
        elif cache_type == "embedding":
            return self.embedding_cache_dir / f"{cache_key}.pkl"
        elif cache_type == "tool":
            return self.tool_cache_dir / f"{cache_key}.pkl"
        else:
            return self.cache_dir / f"{cache_key}.pkl"

    def _is_expired(self, cache_path: Path) -> bool:
        """Check if a cache entry has expired."""
        if not cache_path.exists():
            return True

        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - modified_time > self.ttl

    def get(self, cache_key: str, cache_type: str = "response") -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached entry.

        Args:
            cache_key: Cache key
            cache_type: Type of cache (response, embedding, tool)

        Returns:
            Cached data or None if not found/expired
        """
        if not settings.ENABLE_CACHE:
            return None

        cache_path = self._get_cache_path(cache_key, cache_type)

        if not cache_path.exists() or self._is_expired(cache_path):
            return None

        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def set(self, cache_key: str, data: Dict[str, Any], cache_type: str = "response"):
        """
        Store data in cache.

        Args:
            cache_key: Cache key
            data: Data to cache
            cache_type: Type of cache (response, embedding, tool)
        """
        if not settings.ENABLE_CACHE:
            return

        cache_path = self._get_cache_path(cache_key, cache_type)

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def get_or_compute(
            self,
            query: str,
            compute_fn,
            cache_type: str = "response",
            **kwargs
    ) -> Dict[str, Any]:
        """
        Get cached result or compute if not available.

        Args:
            query: Query string
            compute_fn: Function to compute result if cache miss
            cache_type: Type of cache
            **kwargs: Additional arguments for compute_fn

        Returns:
            Cached or computed result
        """
        cache_key = self._generate_cache_key({"query": query, **kwargs})

        # Try to get from cache
        cached = self.get(cache_key, cache_type)
        if cached is not None:
            print(f"[HIT]  Cache hit for query: {query[:50]}...")
            cached["from_cache"] = True
            return cached

        # Compute if not cached
        print(f"[MISS] Cache miss for query: {query[:50]}...")
        result = compute_fn(query, **kwargs)
        result["from_cache"] = False

        # Store in cache
        self.set(cache_key, result, cache_type)

        return result

    def invalidate(self, cache_key: str, cache_type: str = "response"):
        """Remove a cache entry."""
        cache_path = self._get_cache_path(cache_key, cache_type)
        if cache_path.exists():
            cache_path.unlink()

    def clear_expired(self):
        """Remove all expired cache entries."""
        count = 0
        for cache_dir in [self.response_cache_dir, self.embedding_cache_dir, self.tool_cache_dir]:
            for cache_file in cache_dir.glob("*.pkl"):
                if self._is_expired(cache_file):
                    cache_file.unlink()
                    count += 1

        print(f"Cleared {count} expired cache entries")
        return count

    def clear_all(self, cache_type: Optional[str] = None):
        """Clear all cache entries of a specific type or all types."""
        if cache_type == "response":
            dirs = [self.response_cache_dir]
        elif cache_type == "embedding":
            dirs = [self.embedding_cache_dir]
        elif cache_type == "tool":
            dirs = [self.tool_cache_dir]
        else:
            dirs = [self.response_cache_dir, self.embedding_cache_dir, self.tool_cache_dir]

        count = 0
        for cache_dir in dirs:
            for cache_file in cache_dir.glob("*.pkl"):
                cache_file.unlink()
                count += 1

        print(f"Cleared {count} cache entries")
        return count

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        stats = {
            "response_cache": len(list(self.response_cache_dir.glob("*.pkl"))),
            "embedding_cache": len(list(self.embedding_cache_dir.glob("*.pkl"))),
            "tool_cache": len(list(self.tool_cache_dir.glob("*.pkl"))),
            "total_size_mb": sum(
                f.stat().st_size for f in self.cache_dir.rglob("*.pkl")
            ) / (1024 * 1024)
        }
        stats["total_entries"] = sum([
            stats["response_cache"],
            stats["embedding_cache"],
            stats["tool_cache"]
        ])

        return stats


# Global cache manager instance
cache_manager = CacheManager()


# Test function
if __name__ == "__main__":
    print("Testing Cache Manager")
    print("="*80)

    # Test basic caching
    test_query = "What is the soil type for tea gardening?"

    def mock_compute(query):
        return {"answer": f"Computed answer for: {query}", "sources": ["doc1", "doc2"]}

    # First call - cache miss
    result1 = cache_manager.get_or_compute(test_query, mock_compute)
    print(f"\nFirst call (cache miss): {result1['from_cache']}")

    # Second call - cache hit
    result2 = cache_manager.get_or_compute(test_query, mock_compute)
    print(f"Second call (cache hit): {result2['from_cache']}")

    # Get stats
    stats = cache_manager.get_cache_stats()
    print(f"\nCache stats: {stats}")

    print("\n" + "="*80)