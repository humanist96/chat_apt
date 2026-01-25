"""Caching service for performance optimization.

This module provides:
- Upstash Redis REST API caching (production, serverless-optimized)
- Standard Redis caching (alternative)
- In-memory caching (fallback)
- Cache decorators for API endpoints
"""
from typing import Optional, Any, Callable, TypeVar
from functools import wraps
from datetime import timedelta
import json
import hashlib
import asyncio
import logging

from app.config import get_settings


T = TypeVar("T")
logger = logging.getLogger(__name__)


class UpstashRedisClient:
    """Upstash Redis REST API client for serverless environments."""

    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token
        self._session = None

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def _request(self, *args) -> Any:
        """Execute a Redis command via REST API."""
        session = await self._get_session()
        try:
            async with session.post(
                self.url,
                json=list(args),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result")
                else:
                    logger.error(f"Upstash Redis error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Upstash Redis request failed: {e}")
            return None

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self._request("GET", key)

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        """Set value with expiration."""
        result = await self._request("SETEX", key, ttl, value)
        return result == "OK"

    async def delete(self, key: str) -> int:
        """Delete key."""
        return await self._request("DEL", key) or 0

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return await self._request("EXISTS", key) or 0

    async def incr(self, key: str) -> int:
        """Increment value."""
        return await self._request("INCR", key) or 0

    async def expireat(self, key: str, timestamp: int) -> int:
        """Set expiration timestamp."""
        return await self._request("EXPIREAT", key, timestamp) or 0

    async def ping(self) -> bool:
        """Ping server."""
        result = await self._request("PING")
        return result == "PONG"

    async def close(self):
        """Close session."""
        if self._session:
            await self._session.close()
            self._session = None


class CacheService:
    """Caching service with Upstash/Redis support and in-memory fallback."""

    # Default TTL values (in seconds)
    TTL_SHORT = 60  # 1 minute
    TTL_MEDIUM = 300  # 5 minutes
    TTL_LONG = 3600  # 1 hour
    TTL_DAY = 86400  # 24 hours

    def __init__(self):
        self._redis = None
        self._upstash = None
        self._memory_cache: dict = {}
        self._memory_ttl: dict = {}

    async def _get_redis(self):
        """Get Redis connection (lazy initialization).

        Priority:
        1. Upstash REST API (serverless-optimized)
        2. Standard Redis
        3. In-memory fallback
        """
        # Try Upstash REST API first
        if self._upstash is None:
            settings = get_settings()
            if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
                try:
                    self._upstash = UpstashRedisClient(
                        settings.upstash_redis_rest_url,
                        settings.upstash_redis_rest_token,
                    )
                    if await self._upstash.ping():
                        logger.info("Connected to Upstash Redis (REST API)")
                        return self._upstash
                    else:
                        self._upstash = False
                except Exception as e:
                    logger.warning(f"Upstash connection failed: {e}")
                    self._upstash = False

        if self._upstash and self._upstash is not False:
            return self._upstash

        # Fallback to standard Redis
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
                    await self._redis.ping()
                    logger.info("Connected to standard Redis")
                except Exception as e:
                    logger.warning(f"Redis connection failed: {e}")
                    self._redis = False

        return self._redis if self._redis and self._redis is not False else None

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
