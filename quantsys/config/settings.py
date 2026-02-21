"""Pydantic settings for QuantSys."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project paths
    PROJECT_ROOT: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path("data"))

    # Database
    DATABASE_PATH: str = Field(default="data/quantsys.db")

    # LLM API
    LLM_PROVIDER: str = Field(default="anthropic")  # "anthropic" or "openai"

    # Anthropic settings
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_MODEL: str = Field(default="claude-3-5-sonnet-20241022")

    # OpenAI-compatible settings
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_BASE_URL: Optional[str] = Field(default=None)  # For custom providers
    OPENAI_MODEL: str = Field(default="gpt-4")

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: Optional[str] = Field(default="logs/quantsys.log")

    # Data Collection
    AKSHARE_TIMEOUT: int = Field(default=30)
    AKSHARE_RETRIES: int = Field(default=3)

    # Backtest defaults
    DEFAULT_INITIAL_CASH: float = Field(default=1_000_000.0)
    DEFAULT_COMMISSION_RATE: float = Field(default=0.0003)  # 万3
    DEFAULT_SLIPPAGE: float = Field(default=0.0001)  # 1bps

    @property
    def db_path(self) -> Path:
        """Get absolute database path."""
        path = Path(self.DATABASE_PATH)
        if not path.is_absolute():
            path = self.PROJECT_ROOT / path
        return path

    @property
    def log_path(self) -> Optional[Path]:
        """Get absolute log file path."""
        if self.LOG_FILE is None:
            return None
        path = Path(self.LOG_FILE)
        if not path.is_absolute():
            path = self.PROJECT_ROOT / path
        return path

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if self.LOG_FILE:
            log_dir = self.log_path.parent
            log_dir.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
