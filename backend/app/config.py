"""Application configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "Chat APT API"
    debug: bool = False

    # Database (Supabase)
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""

    # Redis (Upstash)
    redis_url: str = ""

    # Public Data API
    public_data_api_key: str = ""

    # Payment (TossPayments)
    toss_client_key: str = ""
    toss_secret_key: str = ""

    # Crawler
    proxy_list: str = ""  # comma-separated proxy URLs

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
