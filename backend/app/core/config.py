from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "DND-ai-roleplay"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_TRPG_",
        extra="ignore",
    )

    app_name: str = "DND AI Roleplay"
    api_prefix: str = "/api/v1"
    data_dir: Path = Field(default_factory=default_data_dir)
    llm_provider: Literal["google", "deepseek"] = "deepseek"
    character_model: str = "deepseek-v4-flash"
    validator_model: str = ""
    summary_model: str = ""
    memory_model: str = ""
    profile_model: str = ""
    max_parallel_llm_calls: int = Field(default=6, ge=1, le=12)
    enable_message_validator: bool = False
    log_level: str = "INFO"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"

    @property
    def character_agent_is_configured(self) -> bool:
        return (
            self.llm_provider == "deepseek"
            and bool(self.character_model.strip())
            and self.deepseek_api_key is not None
            and bool(self.deepseek_api_key.get_secret_value().strip())
        )

    @property
    def summary_agent_is_configured(self) -> bool:
        return (
            self.llm_provider == "deepseek"
            and bool(self.summary_model.strip())
            and self.deepseek_api_key is not None
            and bool(self.deepseek_api_key.get_secret_value().strip())
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app-data.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.database_path}"

    def ensure_data_directories(self) -> None:
        for path in (
            self.data_dir,
            self.data_dir / "uploads" / "avatars",
            self.data_dir / "uploads" / "character-sheets",
            self.data_dir / "temp",
            self.data_dir / "exports",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
