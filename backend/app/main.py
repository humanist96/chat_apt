"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.auth.middleware import AuthMiddleware, RateLimitMiddleware

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Sentry for error tracking
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1 if not settings.debug else 1.0,
            profiles_sample_rate=0.1 if not settings.debug else 1.0,
            environment="development" if settings.debug else "production",
            send_default_pii=False,
        )
        logger.info("Sentry error tracking initialized")
    except ImportError:
        logger.warning("Sentry SDK not installed, error tracking disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    description="Real estate listing analysis and recommendation API",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware (order matters - first added = outermost)
# 1. CORS (outermost)
# Build allowed origins from settings
_cors_origins = []
if settings.debug:
    # Development: allow localhost
    _cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
else:
    # Production: use configured frontend URL
    _cors_origins = [
        settings.frontend_url,
        "https://chat-apt.com",
        "https://www.chat-apt.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# 2. Rate limiting (after auth, before handlers)
app.add_middleware(RateLimitMiddleware)

# 3. Auth (extracts user from token)
app.add_middleware(AuthMiddleware)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Chat APT API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers
from app.api import apartments, transactions, listings, analysis, recommendations, payments, alerts, search, auth, favorites, monitoring  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(apartments.router, prefix="/api/apartments", tags=["apartments"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(listings.router, prefix="/api/listings", tags=["listings"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
