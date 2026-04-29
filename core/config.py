from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # MongoDB
    mongodb_url: str = Field(default="mongodb://localhost:27017/", alias="MONGODB_URL")
    mongodb_db_name: str = Field(default="trading_framework", alias="MONGODB_DB_NAME")

    # LLM — Gemini
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    # Financial Data APIs
    finnhub_api_key: str = Field(default="", alias="FINNHUB_API_KEY")

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
        cli_parse_args=False,
        cli_kebab_case=True,
        populate_by_name=True,
    )


settings = Settings()