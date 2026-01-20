"""Caching service for performance optimization.

This module provides:
- Redis-based caching (production)
- In-memory caching (fallback)
- Cache decorators for API endpoints
"""
from typing import Optional, Any, Callable, TypeVar
from functools import wraps
from datetime import timedelta
import json
import hashlib
import asyncio

from app.config import get_settings


T = TypeVar("T")


class CacheService:
    """Caching service with Redis support and in-memory fallback."""

    # Default TTL values (in seconds)
    TTL_SHORT = 60  # 1 minute
    TTL_MEDIUM = 300  # 5 minutes
    TTL_LONG = 3600  # 1 hour
    TTL_DAY = 86400  # 24 hours

    def __init__(self):
        self._redis = None
        self._memory_cache: dict = {}
        self._memory_ttl: dict = {}

    async def _get_redis(self):
        """Get Redis connection (lazy initialization)."""
        if self._redis is None:
            settings = get_settings()
            if settings.redis_url:
                try:
                    import redis.asyncio as aioredis
                    self._redis = aioredis.from_url(
                        settings.redis_url,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    # Test connection
                    await self._redis.ping()
                except Exception:
                    self._redis = False  # Mark as unavailable
        return self._redis if self._redis else None

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        redis = await self._get_redis()

        if redis:
            try:
                value = await redis.get(key)
                if value:
                    return json.loads(value)
            except Exception:
                pass

        # Fallback to memory cache
        if key in self._memory_cache:
            import time
            if self._memory_ttl.get(key, 0) > time.time():
                return self._memory_cache[key]
            else:
                # Expired
                del self._memory_cache[key]
                del self._memory_ttl[key]

        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = TTL_MEDIUM,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        redis = await self._get_redis()

        if redis:
            try:
                await redis.setex(key, ttl, json.dumps(value))
                return True
            except Exception:
                pass

        # Fallback to memory cache
        import time
        self._memory_cache[key] = value
        self._memory_ttl[key] = time.time() + ttl
        return True

    async def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        redis = await self._get_redis()

        if redis:
            try:
                await redis.delete(key)
            except Exception:
                pass

        # Also remove from memory cache
        self._memory_cache.pop(key, None)
        self._memory_ttl.pop(key, None)
        return True

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "apartment:*")

        Returns:
            Number of keys deleted
        """
        redis = await self._get_redis()
        count = 0

        if redis:
            try:
                keys = []
                async for key in redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    count = await redis.delete(*keys)
            except Exception:
                pass

        # Also remove from memory cache
        pattern_prefix = pattern.rstrip("*")
        keys_to_delete = [
            k for k in self._memory_cache.keys()
            if k.startswith(pattern_prefix)
        ]
        for key in keys_to_delete:
            del self._memory_cache[key]
            self._memory_ttl.pop(key, None)
            count += 1

        return count

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        redis = await self._get_redis()

        if redis:
            try:
                return await redis.exists(key) > 0
            except Exception:
                pass

        return key in self._memory_cache

    def clear_memory_cache(self):
        """Clear in-memory cache."""
        self._memory_cache.clear()
        self._memory_ttl.clear()


# Singleton instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get the cache service singleton."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(
    prefix: str,
    ttl: int = CacheService.TTL_MEDIUM,
):
    """Decorator to cache function results.

    Args:
        prefix: Cache key prefix
        ttl: Time-to-live in seconds

    Usage:
        @cached("apartment", ttl=300)
        async def get_apartment(apartment_id: int):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            key = f"{prefix}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            cache = get_cache_service()
            cached_value = await cache.get(key)

            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)

            if result is not None:
                await cache.set(key, result, ttl)

            return result
        return wrapper
    return decorator


# Pre-defined cache keys
class CacheKeys:
    """Standard cache key patterns."""

    @staticmethod
    def apartment(apartment_id: int) -> str:
        return f"apartment:{apartment_id}"

    @staticmethod
    def apartment_list(dong_code: str) -> str:
        return f"apartments:dong:{dong_code}"

    @staticmethod
    def listing(listing_id: int) -> str:
        return f"listing:{listing_id}"

    @staticmethod
    def recommendations(dong_code: str = "all") -> str:
        return f"recommendations:{dong_code}"

    @staticmethod
    def similar_apartments(apartment_id: int) -> str:
        return f"similar:{apartment_id}"

    @staticmethod
    def price_trend(apartment_id: int) -> str:
        return f"price_trend:{apartment_id}"

    @staticmethod
    def user_subscription(user_id: str) -> str:
        return f"subscription:{user_id}"
