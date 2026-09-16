from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:flagops@localhost:5432/flagops"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

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

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
