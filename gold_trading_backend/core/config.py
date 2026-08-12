import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Gold Trading Assistant"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1")
    PORT: int = int(os.getenv("PORT", "8000"))

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    SYMBOL: str = "XAUUSD"
    MIN_RR_RATIO: float = 1.5
    RISK_PERCENT_PER_TRADE: float = 1.0
    NEWS_FILTER_ENABLED: bool = os.getenv("NEWS_FILTER_ENABLED", "true").lower() in ("true", "1", "yes")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
