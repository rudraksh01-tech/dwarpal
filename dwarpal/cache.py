"""Verdict cache and rate limiting: Redis when REDIS_URL is set, memory otherwise.

Tool descriptions and many tool results repeat, so a guard verdict is
cached by a hash of the exact text. A cached verdict skips the model calls
(tens to thousands of ms on a free tier) and saves rate-limited quota.
"""

import json
import threading
import time

from dwarpal import config


class MemoryCache:
    name = "memory"

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self._lock:
            item = self._data.get(key)

            if item and (item[1] is None or item[1] > time.time()):
                self.hits += 1
                return item[0]

            self.misses += 1
            return None

    def set(self, key, value, ttl=None):
        with self._lock:
            self._data[key] = (value, time.time() + ttl if ttl else None)

    def hit_window(self, key, limit, window_seconds):
        """Sliding-window rate limit; True if this request is allowed."""
        now = time.time()

        with self._lock:
            stamps = [stamp for stamp in self._data.get(key, ([], None))[0] if now - stamp < window_seconds]
            allowed = len(stamps) < limit

            if allowed:
                stamps.append(now)

            self._data[key] = (stamps, None)
            return allowed

    def stats(self):
        total = self.hits + self.misses
        return {"backend": self.name, "hits": self.hits, "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else None}


class RedisCache(MemoryCache):
    name = "redis"

    def __init__(self, url):
        super().__init__()
        import redis

        self.redis = redis.Redis.from_url(url, decode_responses=True, socket_timeout=3)

    def get(self, key):
        value = self.redis.get(f"dwarpal:v:{key}")

        if value is None:
            self.misses += 1
            return None

        self.hits += 1
        return json.loads(value)

    def set(self, key, value, ttl=None):
        self.redis.set(f"dwarpal:v:{key}", json.dumps(value, ensure_ascii=False), ex=ttl)

    def hit_window(self, key, limit, window_seconds):
        # Fixed window per key: one INCR and one EXPIRE, cheap on a free tier
        bucket = f"dwarpal:rl:{key}:{int(time.time() // window_seconds)}"
        count = self.redis.incr(bucket)

        if count == 1:
            self.redis.expire(bucket, window_seconds)

        return count <= limit


_cache = None


def get_cache():
    global _cache

    if _cache is None:
        _cache = RedisCache(config.REDIS_URL) if config.REDIS_URL else MemoryCache()

    return _cache


def reset_cache(cache=None):
    """Tests use this to start from an empty cache."""
    global _cache
    _cache = cache
