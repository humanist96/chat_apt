"""JWT authentication utilities."""
import logging
from typing import Optional
from dataclasses import dataclass
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

from app.config import get_settings


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# Cache for JWKS client
_jwks_client: Optional[PyJWKClient] = None


@dataclass
class AuthenticatedUser:
    """Authenticated user data."""
    id: str
    email: Optional[str] = None
    membership_tier: str = "free"


class JWTAuth:
    """JWT authentication handler for Supabase tokens."""

    def __init__(self):
        settings = get_settings()
        self.supabase_url = settings.supabase_url
        self._jwks_client: Optional[PyJWKClient] = None

    def _get_jwks_client(self) -> PyJWKClient:
        """Get or create JWKS client for Supabase.

        Supabase exposes JWKS at /.well-known/jwks.json
        """
        global _jwks_client
        if _jwks_client is None:
            if not self.supabase_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Supabase URL not configured",
                )
            jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
            _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        return _jwks_client

    def decode_token(self, token: str) -> dict:
        """Decode and verify JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Get the signing key from Supabase JWKS
            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Decode and verify the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="authenticated",
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "require": ["sub", "exp", "aud"],
                },
            )
            return payload

        except jwt.exceptions.PyJWKClientError as e:
            logger.warning(f"JWKS client error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify token signature",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def get_user_from_token(self, token: str) -> AuthenticatedUser:
        """Extract user information from JWT token.

        Args:
            token: JWT token string

        Returns:
            AuthenticatedUser with extracted data
        """
        payload = self.decode_token(token)

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
            )

        # Extract app metadata for membership tier
        app_metadata = payload.get("app_metadata", {})

        return AuthenticatedUser(
            id=user_id,
            email=payload.get("email"),
            membership_tier=app_metadata.get("membership_tier", "free"),
        )


jwt_auth = JWTAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthenticatedUser:
    """Dependency to get current authenticated user.

    Raises:
        HTTPException: If no valid credentials provided
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return jwt_auth.get_user_from_token(credentials.credentials)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[AuthenticatedUser]:
    """Dependency to get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        return jwt_auth.get_user_from_token(credentials.credentials)
    except HTTPException:
        return None


def require_tier(min_tier: str):
    """Decorator to require minimum membership tier.

    Args:
        min_tier: Minimum required tier ('free', 'basic', 'premium')

    Usage:
        @app.get("/premium-feature")
        @require_tier("premium")
        async def premium_feature(user: AuthenticatedUser = Depends(get_current_user)):
            return {"data": "premium content"}
    """
    tier_levels = {"free": 0, "basic": 1, "premium": 2}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the user in the kwargs (from Depends)
            user = kwargs.get("user") or kwargs.get("current_user")

            if not user:
                # Try to find it in args (less common)
                for arg in args:
                    if isinstance(arg, AuthenticatedUser):
                        user = arg
                        break

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_level = tier_levels.get(user.membership_tier, 0)
            required_level = tier_levels.get(min_tier, 0)

            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This feature requires {min_tier} tier or higher",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
