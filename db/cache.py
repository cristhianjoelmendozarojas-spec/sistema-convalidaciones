# db/cache.py
"""
Sistema de cache en memoria con TTL y límites de tamaño.
Thread-safe para uso en aplicaciones Flask.
"""

import time
import threading
from functools import wraps


class CacheEntry:
    def __init__(self, value, ttl=None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl

    def is_expired(self):
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class Cache:
    def __init__(self, max_size=100, default_ttl=300):
        self._cache = {}
        self._lock = threading.RLock()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key, default=None):
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return default
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return default
            self._hits += 1
            return entry.value

    def set(self, key, value, ttl=None):
        with self._lock:
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_oldest()
            self._cache[key] = CacheEntry(value, ttl or self.default_ttl)

    def delete(self, key):
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _evict_oldest(self):
        if not self._cache:
            return
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]

    def cleanup_expired(self):
        with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired()]
            for k in expired:
                del self._cache[k]
            return len(expired)

    @property
    def stats(self):
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "max_size": self.max_size,
            }


pdf_cache = Cache(max_size=50, default_ttl=600)
preview_cache = Cache(max_size=50, default_ttl=600)


def cached(cache_instance, ttl=None, key_func=None):
    """Decorador para cachear resultados de funciones."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{f.__module__}.{f.__name__}:{str(args)}:{str(kwargs)}"

            result = cache_instance.get(cache_key)
            if result is not None:
                return result

            result = f(*args, **kwargs)
            cache_instance.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def invalidate(cache_instance, *keys):
    """Invalida claves específicas del cache."""
    for key in keys:
        cache_instance.delete(key)
