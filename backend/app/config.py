"""Application configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "Chat APT API"
    debug: bool = False
    frontend_url: str = "https://chat-apt.com"

    # Database (Supabase)
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""

    # Redis (Upstash)
    redis_url: str = ""  # Standard Redis URL (redis://...)
    upstash_redis_rest_url: str = ""  # Upstash REST API URL
    upstash_redis_rest_token: str = ""  # Upstash REST API Token

    # Public Data API (국토교통부 실거래가)
    public_data_api_key: str = ""

    # Payment (TossPayments)
    toss_client_key: str = ""
    toss_secret_key: str = ""

    # OpenSearch (no defaults - must be configured in .env)
    opensearch_host: str = ""
    opensearch_port: int = 9200
    opensearch_username: str = ""
    opensearch_password: str = ""

    # Crawler
    proxy_list: str = ""  # comma-separated proxy URLs

    # Telegram Notifications
    telegram_bot_token: str = ""  # Bot token from @BotFather
    telegram_chat_id: str = ""  # Chat ID for notifications

    # Sentry Error Tracking
    sentry_dsn: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
