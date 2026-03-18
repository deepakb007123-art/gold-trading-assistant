import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "Institutional Gold Trading Assistant"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Telegram Config
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Trading Config
    SYMBOL: str = "XAUUSD"
    MIN_RR_RATIO: float = 1.5
    RISK_PERCENT_PER_TRADE: float = 1.0  # 1% standard risk

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
