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
    """Middleware for rate limiting based on user tier."""

    # Endpoints that require rate limiting
    RATE_LIMITED_PATHS = {
        "/api/listings": "listings",
        "/api/analysis": "analysis",
        "/api/reports": "report",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limits before processing request."""
        from app.auth.rate_limiter import get_rate_limiter

        user: Optional[AuthenticatedUser] = getattr(request.state, "user", None)

        # Determine endpoint category
        endpoint = None
        for path_prefix, category in self.RATE_LIMITED_PATHS.items():
            if request.url.path.startswith(path_prefix):
                endpoint = category
                break

        # Check rate limit if user is authenticated and endpoint is rate-limited
        if user and endpoint:
            limiter = get_rate_limiter()
            allowed, remaining = await limiter.check_limit(
                user.id,
                user.membership_tier,
                endpoint,
            )

            if not allowed:
                from fastapi.responses import JSONResponse
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
