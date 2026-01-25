"""Authentication middleware."""
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.auth.jwt import jwt_auth, AuthenticatedUser


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and attach user info from JWT token."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and attach user info if authenticated."""
        request.state.user = None

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

            try:
                user = jwt_auth.get_user_from_token(token)
                request.state.user = user
            except Exception:
                # Invalid token - continue as unauthenticated
                pass

        response = await call_next(request)

        # Add rate limit headers if user is authenticated
        if request.state.user:
            # These would be set by the rate limiter
            pass

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting based on user tier and endpoint type.

    Rate limits:
    - /api/listings: tier-based daily limit
    - /api/analysis: tier-based daily limit
    - /api/reports: tier-based daily limit
    - /api/payments: 5 requests/minute (fixed)
    - /api/auth: 10 requests/minute (fixed)
    - /api/search: 100 requests/minute (fixed)
    """

    # Endpoints with tier-based daily limits
    TIER_RATE_LIMITED_PATHS = {
        "/api/listings": "listings",
        "/api/analysis": "analysis",
        "/api/reports": "report",
    }

    # Endpoints with fixed per-minute limits (regardless of tier)
    FIXED_RATE_LIMITED_PATHS = {
        "/api/payments": 5,      # 5 requests/minute
        "/api/auth": 10,        # 10 requests/minute
        "/api/search": 100,     # 100 requests/minute
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limits before processing request."""
        from app.auth.rate_limiter import get_rate_limiter
        from fastapi.responses import JSONResponse

        user: Optional[AuthenticatedUser] = getattr(request.state, "user", None)
        path = request.url.path

        # Check fixed per-minute rate limits first (apply to all users, even unauthenticated)
        for path_prefix, limit_per_minute in self.FIXED_RATE_LIMITED_PATHS.items():
            if path.startswith(path_prefix):
                # Use IP for unauthenticated, user ID for authenticated
                identifier = user.id if user else self._get_client_ip(request)
                allowed = await self._check_fixed_rate_limit(
                    identifier, path_prefix, limit_per_minute
                )
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": f"Rate limit exceeded. Maximum {limit_per_minute} requests per minute.",
                        },
                        headers={"Retry-After": "60"},
                    )

        # Check tier-based daily limits (only for authenticated users)
        endpoint = None
        for path_prefix, category in self.TIER_RATE_LIMITED_PATHS.items():
            if path.startswith(path_prefix):
                endpoint = category
                break

        if user and endpoint:
            limiter = get_rate_limiter()
            allowed, remaining = await limiter.check_limit(
                user.id,
                user.membership_tier,
                endpoint,
            )

            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Daily rate limit exceeded. Please upgrade your plan.",
                    },
                    headers={"Retry-After": "86400"},
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining) if remaining != -1 else "unlimited"
            return response

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, considering proxy headers."""
        # Check X-Forwarded-For first (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (common alternative)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _check_fixed_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit_per_minute: int,
    ) -> bool:
        """Check fixed per-minute rate limit.

        Returns True if request is allowed, False if rate limited.
        """
        from app.services.cache import UpstashRedisClient
        from app.config import get_settings
        from datetime import datetime

        settings = get_settings()

        # Create rate limit key with minute granularity
        minute_key = datetime.utcnow().strftime("%Y%m%d%H%M")
        key = f"rate:fixed:{identifier}:{endpoint}:{minute_key}"

        # Try to use Redis
        if settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
            try:
                redis = UpstashRedisClient(
                    settings.upstash_redis_rest_url,
                    settings.upstash_redis_rest_token,
                )
                current = await redis.get(key)
                current_count = int(current) if current else 0

                if current_count >= limit_per_minute:
                    return False

                await redis.incr(key)
                # Set TTL to 60 seconds
                await redis.expire(key, 60)
                return True
            except Exception:
                # Fallback: allow request if Redis fails
                return True

        # No Redis configured, allow request
        return True
