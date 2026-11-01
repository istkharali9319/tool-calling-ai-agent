"""Application settings loaded from environment variables and an optional .env file."""

from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from env vars (or .env via python-dotenv)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "AI Business Assistant API"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: str = Field(default="", description="Comma-separated list of allowed origins.")
    timezone: str = "UTC"

    # OpenAI
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_base_url: str | None = None
    openai_timeout_seconds: float = Field(default=60.0, gt=0)
    openai_max_retries: int = Field(default=3, ge=0, le=10)
    openai_max_output_tokens: int = Field(default=4096, ge=256)
    max_tool_iterations: int = Field(default=6, ge=1, le=20)

    # Weather (Open-Meteo, no API key needed)
    weather_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    weather_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = Field(default=10.0, gt=0)
    weather_temperature_unit: Literal["celsius", "fahrenheit"] = "celsius"
    weather_cache_seconds: float = Field(default=600, ge=0)

    # Database
    database_url: str = "sqlite:///./assistant.db"
    sql_echo: bool = False
    seed_on_startup: bool = True

    # Conversations
    history_limit: int = Field(default=20, ge=0, le=200)

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value!r}") from exc
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
