from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    open_api_key: str = ""
    
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
        cli_parse_args=False,  # Set to False so it doesn't clash with uvicorn arguments
        cli_kebab_case=True,
    )

settings = Settings()