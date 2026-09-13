"""Application settings using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for pyknic-todo."""

    model_config = SettingsConfigDict(
        env_prefix="PYKNIC_TODO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(
        default=Path("./data"),
        validation_alias=AliasChoices(
            "PYKNIC_TODO_DATA_DIR", "TODO_DATA_DIR", "data_dir"
        ),
        description="Directory to store JSON data",
    )
    schema_version: str = Field(
        default="1.0.0",
        description="Data schema version for storage files",
    )
    client_id_prefix: str = Field(
        default="cli",
        description="Prefix for generated client IDs",
    )
    default_priority: str = Field(
        default="medium",
        description="Default priority for new tasks",
    )
    default_status: str = Field(
        default="pending",
        description="Default status for new tasks",
    )
    storage_type: str = Field(
        default="json",
        validation_alias=AliasChoices(
            "PYKNIC_TODO_STORAGE_TYPE", "TODO_STORAGE_TYPE", "storage_type"
        ),
        description="Storage backend type ('json', etc.)",
    )
