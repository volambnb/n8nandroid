from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Platform(str, Enum):
    X = "x"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- IXBrowser ---
    ixbrowser_host: str = "127.0.0.1"
    ixbrowser_port: int = 53200
    ixbrowser_max_concurrent: int = 3  # API hard limit

    # --- OpenAI / LLM for Page-Agent ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # --- Page-Agent ---
    page_agent_cdn: str = (
        "https://cdn.jsdelivr.net/npm/page-agent@latest/dist/iife/page-agent.js"
    )
    page_agent_language: str = "en-US"

    # --- Telegram Bot ---
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: list[int] = Field(default_factory=list)

    # --- FastAPI ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # --- OpenFang ---
    openfang_url: str = "http://127.0.0.1:3000"

    # --- Task defaults ---
    task_min_delay: float = 2.0   # seconds between actions
    task_max_delay: float = 8.0   # seconds between actions
    task_timeout: float = 300.0   # max seconds per task
    task_max_retries: int = 2

    # --- Paths ---
    task_templates_path: str = str(BASE_DIR / "config" / "task_templates.yaml")


settings = Settings()
