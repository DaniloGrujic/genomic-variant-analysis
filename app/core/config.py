from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    storage_backend: Literal["local", "s3"] = "local"
    aws_region: str = "eu-north-1"
    s3_bucket_name: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
