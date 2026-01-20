"""Rate limiting utilities."""
from datetime import datetime, date
from typing import Optional, Tuple
from dataclasses import dataclass

from fastapi import HTTPException, status, Request

from app.config import get_settings


@dataclass
class RateLimitConfig:
    """Rate limit configuration for different tiers."""
    listings: int  # Daily limit for listing queries
    analysis: int  # Daily limit for analysis requests
    report: int  # Daily limit for report generation


class RateLimiter:
    """Rate limiter based on user tier.

    Uses Redis (Upstash) for distributed rate limiting.
    Falls back to in-memory storage if Redis is unavailable.
    """

    # Rate limits per tier (-1 = unlimited)
    TIER_LIMITS = {
        "free": RateLimitConfig(listings=10, analysis=0, report=0),
        "basic": RateLimitConfig(listings=100, analysis=10, report=5),
        "premium": RateLimitConfig(listings=-1, analysis=-1, report=-1),
    }

    def __init__(self):
        self._memory_store: dict = {}  # Fallback in-memory store
        self._redis = None

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
                except Exception:
                    self._redis = False  # Mark as unavailable
        return self._redis if self._redis else None

    def _get_limit(self, tier: str, endpoint: str) -> int:
        """Get the rate limit for a tier and endpoint."""
        config = self.TIER_LIMITS.get(tier, self.TIER_LIMITS["free"])

        if endpoint in ("listings", "매물"):
            return config.listings
        elif endpoint in ("analysis", "분석"):
            return config.analysis
        elif endpoint in ("report", "리포트"):
            return config.report
        else:
            return config.listings  # Default to listings limit

    async def _get_current_count(self, key: str) -> int:
        """Get current count from Redis or memory."""
        redis = await self._get_redis()

        if redis:
            try:
                value = await redis.get(key)
                return int(value) if value else 0
            except Exception:
                pass

        # Fallback to memory
        return self._memory_store.get(key, 0)

    async def _increment_count(self, key: str) -> int:
        """Increment count in Redis or memory."""
        redis = await self._get_redis()

        if redis:
            try:
                new_count = await redis.incr(key)
                # Set expiry at midnight
                await redis.expireat(key, self._get_midnight_timestamp())
                return new_count
            except Exception:
                pass

        # Fallback to memory
        current = self._memory_store.get(key, 0)
        self._memory_store[key] = current + 1
        return current + 1

    def _get_midnight_timestamp(self) -> int:
        """Get timestamp for midnight (next day)."""
        from datetime import datetime, timedelta
        tomorrow = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        return int(tomorrow.timestamp())

    async def check_limit(
        self,
        user_id: str,
        tier: str,
        endpoint: str,
    ) -> Tuple[bool, int]:
        """Check if user is within rate limit.

        Args:
            user_id: User identifier
            tier: User's membership tier
            endpoint: API endpoint category

        Returns:
            Tuple of (is_allowed, remaining_count)
            remaining_count is -1 for unlimited
        """
        limit = self._get_limit(tier, endpoint)

        # Unlimited
        if limit == -1:
            return True, -1

        # No access
        if limit == 0:
            return False, 0

        # Check current usage
        today = date.today().isoformat()
        key = f"rate:{user_id}:{endpoint}:{today}"

        current = await self._get_current_count(key)

        if current >= limit:
            return False, 0

        # Increment and return remaining
        await self._increment_count(key)
        remaining = limit - current - 1

        return True, remaining

    async def get_usage_stats(
        self,
        user_id: str,
        tier: str,
    ) -> dict:
        """Get current usage statistics for a user.

        Args:
            user_id: User identifier
            tier: User's membership tier

        Returns:
            Dict with usage stats for each endpoint
        """
        today = date.today().isoformat()
        stats = {}

        for endpoint in ("listings", "analysis", "report"):
            limit = self._get_limit(tier, endpoint)
            key = f"rate:{user_id}:{endpoint}:{today}"
            current = await self._get_current_count(key)

            stats[endpoint] = {
                "used": current,
                "limit": limit if limit != -1 else "unlimited",
                "remaining": (limit - current) if limit != -1 else "unlimited",
            }

        return stats


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def check_rate_limit(
    user_id: str,
    tier: str,
    endpoint: str,
) -> int:
    """Check rate limit and raise exception if exceeded.

    Args:
        user_id: User identifier
        tier: User's membership tier
        endpoint: API endpoint category

    Returns:
        Remaining count (-1 for unlimited)

    Raises:
        HTTPException: If rate limit exceeded
    """
    limiter = get_rate_limiter()
    allowed, remaining = await limiter.check_limit(user_id, tier, endpoint)

    if not allowed:
        if remaining == 0 and limiter._get_limit(tier, endpoint) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires a paid subscription",
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily rate limit exceeded. Please upgrade your plan for more access.",
            headers={"Retry-After": "86400"},  # 24 hours
        )

    return remaining
