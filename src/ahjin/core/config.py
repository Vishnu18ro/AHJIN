"""Application settings via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AHJIN 2.0 configuration settings."""

    ahjin_env: str = "development"

    # Telegram
    telegram_bot_token: str = ""

    # NVIDIA Provider
    # No code defaults for credentials or model selection (ADR-003).
    # Empty string is the "not configured" sentinel.
    # NvidiaProvider validates these at construction and raises clearly if missing.
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    # model_id: no code default — must be set in environment or .env.
    # Rationale: model selection is operator-driven configuration, not a code decision.
    nvidia_model_id: str = ""
    # max_tokens budget for model generation.
    # Default 4096 allows complete responses without over-running typical Telegram payloads.
    # Operators may lower this for latency-sensitive deployments or raise it for long-form tasks.
    nvidia_max_tokens: int = 4096

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
