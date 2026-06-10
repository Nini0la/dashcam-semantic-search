from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    azure_storage_connection_string: Optional[str] = None
    azure_blob_container_name: Optional[str] = None
    video_indexer_account_id: Optional[str] = None
    video_indexer_location: Optional[str] = None
    video_indexer_api_key: Optional[str] = None
    video_indexer_account_name: Optional[str] = None
    database_url: str = "sqlite:///./dashcam.db"
    demo_mode: Optional[bool] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def db_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// DATABASE_URL values are supported by this MVP")
        return Path(self.database_url.replace("sqlite:///", "", 1))

    @property
    def has_blob_config(self) -> bool:
        return bool(self.azure_storage_connection_string and self.azure_blob_container_name)

    @property
    def has_video_indexer_config(self) -> bool:
        return bool(
            self.video_indexer_account_id
            and self.video_indexer_location
            and self.video_indexer_api_key
        )

    @property
    def use_demo_mode(self) -> bool:
        if self.demo_mode is not None:
            return self.demo_mode
        return not (self.has_blob_config and self.has_video_indexer_config)


@lru_cache
def get_settings() -> Settings:
    return Settings()
