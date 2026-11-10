from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    DEBUG: bool = True

    DATABASE_URL: str
    REDIS_URL: str

    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_FROM: str | None = None
    EMAIL_PORT: int = 587
    EMAIL_USE_TLS: bool = True
    EMAIL_USE_SSL: bool = False

    FRONTEND_URL: str = "http://localhost:3000"
    DOMAIN_URL: str = "http://localhost:8000"

    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "my-app"
    JWT_AUDIENCE: str = "my-users"
    ACCESS_TOKEN_LIFETIME: int = 15
    REFRESH_TOKEN_LIFETIME: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def DEFAULT_FROM_EMAIL(self) -> str:
        return self.EMAIL_FROM or self.EMAIL_HOST_USER


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
