"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.auth.middleware import AuthMiddleware, RateLimitMiddleware


settings = get_settings()


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
from app.api import apartments, transactions, listings

app.include_router(apartments.router, prefix="/api/apartments", tags=["apartments"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(listings.router, prefix="/api/listings", tags=["listings"])
