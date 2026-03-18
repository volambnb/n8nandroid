"""Task Registry – loads YAML templates and resolves task prompts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import yaml

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ResolvedTask:
    platform: str
    task_type: str
    prompt: str
    url: str | None
    min_delay: float
    max_delay: float


class TaskRegistry:
    """Loads task templates from YAML and resolves them with runtime params."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or settings.task_templates_path
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        with open(self._path, "r", encoding="utf-8") as fh:
            self._data = yaml.safe_load(fh) or {}
        logger.info("Loaded task templates from %s", self._path)

    @property
    def platforms(self) -> list[str]:
        return list((self._data.get("platforms") or {}).keys())

    def task_types(self, platform: str) -> list[str]:
        plat = (self._data.get("platforms") or {}).get(platform, {})
        return list((plat.get("tasks") or {}).keys())

    def resolve(
        self,
        platform: str,
        task_type: str,
        params: dict[str, str] | None = None,
    ) -> ResolvedTask:
        params = params or {}
        plat = (self._data.get("platforms") or {}).get(platform)
        if plat is None:
            raise ValueError(f"Unknown platform: {platform}")

        tmpl = (plat.get("tasks") or {}).get(task_type)
        if tmpl is None:
            raise ValueError(f"Unknown task type: {platform}/{task_type}")

        prompt = tmpl["prompt"].strip().format_map(_SafeFormatDict(params))

        raw_url = tmpl.get("url")
        url: str | None = None
        if raw_url:
            url = raw_url.strip().format_map(_SafeFormatDict(params))
        elif plat.get("base_url"):
            url = plat["base_url"]

        return ResolvedTask(
            platform=platform,
            task_type=task_type,
            prompt=prompt,
            url=url,
            min_delay=tmpl.get("min_delay", settings.task_min_delay),
            max_delay=tmpl.get("max_delay", settings.task_max_delay),
        )


class _SafeFormatDict(dict):
    """Returns the placeholder unchanged when a key is missing."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
