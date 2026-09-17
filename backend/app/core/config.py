from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:flagops@localhost:5432/flagops"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_ENABLED: bool = Field(default=True)
    RULESET_CACHE_TTL_SECONDS: int = Field(default=300)
    EVAL_RATE_LIMIT_PER_MINUTE: int = Field(default=1000)

    SECRET_KEY: str = Field(default="change-me-to-a-random-string-at-least-32-chars")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    CONFIG_MASTER_KEY: str = Field(default="change-me-32-bytes-key-here!!!!")

    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")

    CORS_ORIGINS: str = Field(default="http://localhost:3000,http://localhost:5173")

    ENVIRONMENT: str = Field(default="development")

    # Flag lifecycle debt score weights (must sum to 1.0)
    DEBT_W_AGE: float = Field(default=0.25)
    DEBT_W_ROLLOUT: float = Field(default=0.35)
    DEBT_W_STALENESS: float = Field(default=0.25)
    DEBT_W_TEMPORARY: float = Field(default=0.15)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def validate_production_security(self) -> None:
        """Enforce fail-secure startup rules in production/staging or non-debug mode."""
        is_prod = self.ENVIRONMENT.lower() in ("production", "staging") or not self.DEBUG
        if is_prod:
            if (
                self.CONFIG_MASTER_KEY == "change-me-32-bytes-key-here!!!!"
                or len(self.CONFIG_MASTER_KEY.encode("utf-8")) != 32
            ):
                raise RuntimeError(
                    "FATAL: Insecure CONFIG_MASTER_KEY detected in production environment. Application halted."
                )
            if (
                self.SECRET_KEY == "change-me-to-a-random-string-at-least-32-chars"
                or len(self.SECRET_KEY) < 32
            ):
                raise RuntimeError(
                    "FATAL: Insecure SECRET_KEY detected in production environment. Application halted."
                )


settings = Settings()

