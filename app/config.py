"""
DRX Configuration
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "ProxzarDRxDb"

    SECRET_KEY: str = "drx-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Proxzar Global Auth (inbound — DRX trusts Proxzar-issued JWTs)
    PROXZAR_JWKS_URL: str = "https://oauth2.proxzar.ai/api/v1/jwks"
    PROXZAR_ISSUER: str = "https://oauth2.proxzar.ai"
    PROXZAR_AUDIENCE: str = "DRX"

    # MRX integration endpoint prefix (used by mrx_client when calling MRX)
    MRX_API_PREFIX: str = "/mrxdb/integration"

    APP_NAME: str = "DRx: AI-Powered Doctor-Pharma Platform"
    APP_VERSION: str = "1.0.0"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "DRX Platform"

    DEFAULT_USER_PASSWORD: str = "Welcome@123"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
