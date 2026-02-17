"""Pydantic settings for the verification service."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = {"env_prefix": "VERIFY_"}

    redis_url: str = "redis://localhost:6379/0"
    phiacta_api_url: str = "http://localhost:8000"
    phiacta_api_key: str = ""
    signing_key_path: str = "keys/ed25519.pem"
    max_concurrent_jobs: int = 4
    max_code_size_bytes: int = 1_048_576  # 1 MB
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = ["http://localhost:3000"]
