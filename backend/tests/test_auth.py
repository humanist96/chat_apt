"""Tests for authentication module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import base64
import json

from fastapi import HTTPException

from app.auth.jwt import (
    JWTAuth,
    AuthenticatedUser,
    get_current_user,
    get_current_user_optional,
    require_tier,
)
from app.auth.rate_limiter import RateLimiter, RateLimitConfig, check_rate_limit


class TestJWTAuth:
    """Tests for JWT authentication."""

    def test_authenticated_user_creation(self):
        """Test AuthenticatedUser dataclass."""
        user = AuthenticatedUser(
            id="user-123",
            email="test@example.com",
            membership_tier="basic",
        )

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.membership_tier == "basic"

    def test_authenticated_user_defaults(self):
        """Test AuthenticatedUser default values."""
        user = AuthenticatedUser(id="user-456")

        assert user.id == "user-456"
        assert user.email is None
        assert user.membership_tier == "free"

    def test_decode_token_valid(self):
        """Test decoding a valid JWT token."""
        import jwt as pyjwt

        jwt_auth = JWTAuth()

        # Create a properly signed JWT token using pyjwt
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {},
            "app_metadata": {"membership_tier": "premium"},
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "secret", algorithm="HS256")

        user = jwt_auth.get_user_from_token(token)

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.membership_tier == "premium"

    def test_decode_token_missing_sub(self):
        """Test decoding token without user ID."""
        import jwt as pyjwt

        jwt_auth = JWTAuth()

        # Token without 'sub' claim
        payload = {
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "secret", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            jwt_auth.get_user_from_token(token)

        assert exc_info.value.status_code == 401
        assert "missing user ID" in exc_info.value.detail


class TestRequireTier:
    """Tests for tier requirement decorator."""

    @pytest.mark.asyncio
    async def test_require_tier_premium_access(self):
        """Test premium user accessing premium feature."""

        @require_tier("premium")
        async def premium_feature(user: AuthenticatedUser):
            return {"data": "premium content"}

        user = AuthenticatedUser(id="user-1", membership_tier="premium")
        result = await premium_feature(user=user)

        assert result == {"data": "premium content"}

    @pytest.mark.asyncio
    async def test_require_tier_basic_accessing_premium(self):
        """Test basic user trying to access premium feature."""

        @require_tier("premium")
        async def premium_feature(user: AuthenticatedUser):
            return {"data": "premium content"}

        user = AuthenticatedUser(id="user-1", membership_tier="basic")

        with pytest.raises(HTTPException) as exc_info:
            await premium_feature(user=user)

        assert exc_info.value.status_code == 403
        assert "premium tier" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_tier_free_accessing_basic(self):
        """Test free user trying to access basic feature."""

        @require_tier("basic")
        async def basic_feature(user: AuthenticatedUser):
            return {"data": "basic content"}

        user = AuthenticatedUser(id="user-1", membership_tier="free")

        with pytest.raises(HTTPException) as exc_info:
            await basic_feature(user=user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_tier_no_user(self):
        """Test accessing feature without user."""

        @require_tier("basic")
        async def basic_feature():
            return {"data": "basic content"}

        with pytest.raises(HTTPException) as exc_info:
            await basic_feature()

        assert exc_info.value.status_code == 401


class TestRateLimiter:
    """Tests for rate limiter."""

    def test_rate_limit_config(self):
        """Test RateLimitConfig dataclass."""
        config = RateLimitConfig(listings=100, analysis=10, report=5)

        assert config.listings == 100
        assert config.analysis == 10
        assert config.report == 5

    def test_tier_limits_defined(self):
        """Test that tier limits are properly defined."""
        limiter = RateLimiter()

        assert "free" in limiter.TIER_LIMITS
        assert "basic" in limiter.TIER_LIMITS
        assert "premium" in limiter.TIER_LIMITS

        # Free tier should have limited access
        assert limiter.TIER_LIMITS["free"].listings == 10
        assert limiter.TIER_LIMITS["free"].analysis == 0

        # Premium should have unlimited access
        assert limiter.TIER_LIMITS["premium"].listings == -1

    def test_get_limit(self):
        """Test getting limits for different tiers and endpoints."""
        limiter = RateLimiter()

        # Free tier
        assert limiter._get_limit("free", "listings") == 10
        assert limiter._get_limit("free", "analysis") == 0
        assert limiter._get_limit("free", "report") == 0

        # Basic tier
        assert limiter._get_limit("basic", "listings") == 100
        assert limiter._get_limit("basic", "analysis") == 10
        assert limiter._get_limit("basic", "report") == 5

        # Premium tier (unlimited)
        assert limiter._get_limit("premium", "listings") == -1
        assert limiter._get_limit("premium", "analysis") == -1

    @pytest.mark.asyncio
    async def test_check_limit_premium_unlimited(self):
        """Test that premium users have unlimited access."""
        limiter = RateLimiter()

        allowed, remaining = await limiter.check_limit(
            user_id="user-123",
            tier="premium",
            endpoint="listings",
        )

        assert allowed is True
        assert remaining == -1

    @pytest.mark.asyncio
    async def test_check_limit_free_within_limit(self):
        """Test free user within their limit."""
        limiter = RateLimiter()
        limiter._memory_store = {}  # Reset memory store

        allowed, remaining = await limiter.check_limit(
            user_id="user-456",
            tier="free",
            endpoint="listings",
        )

        assert allowed is True
        assert remaining == 9  # 10 - 1 (just used one)

    @pytest.mark.asyncio
    async def test_check_limit_free_no_access(self):
        """Test free user with no access to analysis."""
        limiter = RateLimiter()

        allowed, remaining = await limiter.check_limit(
            user_id="user-789",
            tier="free",
            endpoint="analysis",
        )

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_check_limit_exceeded(self):
        """Test that limit is enforced."""
        limiter = RateLimiter()
        limiter._memory_store = {}

        user_id = "test-user"
        from datetime import date
        today = date.today().isoformat()
        key = f"rate:{user_id}:listings:{today}"

        # Simulate usage at limit
        limiter._memory_store[key] = 10  # Free tier limit

        allowed, remaining = await limiter.check_limit(
            user_id=user_id,
            tier="free",
            endpoint="listings",
        )

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_get_usage_stats(self):
        """Test getting usage statistics."""
        limiter = RateLimiter()
        limiter._memory_store = {}

        from datetime import date
        today = date.today().isoformat()

        # Simulate some usage
        limiter._memory_store[f"rate:user-1:listings:{today}"] = 5
        limiter._memory_store[f"rate:user-1:analysis:{today}"] = 2

        stats = await limiter.get_usage_stats("user-1", "basic")

        assert stats["listings"]["used"] == 5
        assert stats["listings"]["limit"] == 100
        assert stats["listings"]["remaining"] == 95

        assert stats["analysis"]["used"] == 2
        assert stats["analysis"]["limit"] == 10


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        """Test rate limit check when allowed."""
        from app.auth import rate_limiter

        # Reset the global limiter
        rate_limiter._rate_limiter = None
        limiter = rate_limiter.get_rate_limiter()
        limiter._memory_store = {}

        remaining = await check_rate_limit(
            user_id="user-1",
            tier="basic",
            endpoint="listings",
        )

        assert remaining == 99  # 100 - 1

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self):
        """Test rate limit check when exceeded."""
        from app.auth import rate_limiter
        from datetime import date

        # Reset and setup
        rate_limiter._rate_limiter = None
        limiter = rate_limiter.get_rate_limiter()
        limiter._memory_store = {}

        today = date.today().isoformat()
        key = f"rate:user-2:listings:{today}"
        limiter._memory_store[key] = 10  # At free tier limit

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(
                user_id="user-2",
                tier="free",
                endpoint="listings",
            )

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_access(self):
        """Test rate limit check for forbidden feature."""
        from app.auth import rate_limiter

        rate_limiter._rate_limiter = None

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(
                user_id="user-3",
                tier="free",
                endpoint="analysis",
            )

        assert exc_info.value.status_code == 403
        assert "paid subscription" in exc_info.value.detail
