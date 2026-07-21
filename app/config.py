"""
DRX Configuration
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "drx_doctor_platform_db"

    SECRET_KEY: str = "drx-secret-key-change-in-production-min-32-chars"
    SERVICE_JWT_SECRET: str = "drx-service-jwt-secret-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # DRX calls MRX (outbound) — same credentials for all MRX deployments
    DRX_TO_MRX_CLIENT_ID: str = "drx_doctor_platform"
    DRX_TO_MRX_SECRET: str = "DRX2024SecureServiceKey"

    APP_NAME: str = "DRX - Doctor Platform"
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
