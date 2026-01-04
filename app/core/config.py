from pydantic_settings import BaseSettings
from typing import List, Union
from pydantic import field_validator
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Resume Analyzer API"

    # Database Settings
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "talent_db"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis Settings (for Celery task queue)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # OpenAI Settings
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.2

    # JWT Authentication Settings
    SECRET_KEY: str = "CHANGE_THIS_TO_RANDOM_SECRET_KEY_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Stripe Settings
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Stripe Price IDs - Monthly
    STRIPE_PRICE_ID_RECRUITER_MONTHLY: str = ""
    STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY: str = ""
    STRIPE_PRICE_ID_ENTERPRISE_MONTHLY: str = ""

    # Stripe Price IDs - Yearly
    STRIPE_PRICE_ID_RECRUITER_YEARLY: str = ""
    STRIPE_PRICE_ID_SMALL_BUSINESS_YEARLY: str = ""
    STRIPE_PRICE_ID_ENTERPRISE_YEARLY: str = ""

    # Aliases for backwards compatibility
    @property
    def STRIPE_PRICE_ID_STARTER(self) -> str:
        return self.STRIPE_PRICE_ID_RECRUITER_MONTHLY

    @property
    def STRIPE_PRICE_ID_PROFESSIONAL(self) -> str:
        return self.STRIPE_PRICE_ID_ENTERPRISE_MONTHLY

    FRONTEND_URL: str = "http://localhost:8000"  # Frontend URL for redirects

    # AWS S3 Settings
    AWS_ACCESS_KEY_ID: str = ""                 # AWS access key (optional if using IAM roles)
    AWS_SECRET_ACCESS_KEY: str = ""             # AWS secret key (optional if using IAM roles)
    AWS_REGION: str = "us-east-1"               # AWS region for S3 bucket
    S3_BUCKET_NAME: str = ""                    # S3 bucket name for resume storage
    USE_S3: bool = False                        # Toggle S3 vs local storage (for backward compatibility)

    # AWS SES Settings (Email Verification) - DEPRECATED, use Resend instead
    AWS_SES_FROM_EMAIL: str = "noreply@yourdomain.com"  # Verified sender email in AWS SES
    AWS_SES_FROM_NAME: str = "Resume Analyzer"           # Sender display name

    # Resend Settings (Email Verification)
    RESEND_API_KEY: str = ""                            # Resend API key from https://resend.com/api-keys
    RESEND_FROM_EMAIL: str = "noreply@yourdomain.com"   # Verified sender email in Resend
    RESEND_FROM_NAME: str = "Starscreen"                # Sender display name

    # Support Email Settings
    SUPPORT_FORWARD_EMAIL: str = "admin@yourdomain.com"  # Where to forward support@starscreen.net emails

    # Free Tier Settings
    FREE_TIER_CANDIDATE_LIMIT: int = 10         # Monthly candidate limit for free tier

    # Retention Policy Settings (EEOC/OFCCP Compliance)
    # Federal law requires keeping employment records for 1-3 years
    CANDIDATE_RETENTION_DAYS: int = 1095        # 3 years (conservative for OFCCP compliance)
    ENABLE_SOFT_DELETE: bool = True             # Use soft delete instead of hard delete
    AUTO_PURGE_ENABLED: bool = False            # Automatically purge records after retention period

    # CORS Settings - can be set as JSON string in .env
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        """Parse CORS origins from JSON string or list"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # If not valid JSON, split by comma
                return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env that aren't in Settings


settings = Settings()
