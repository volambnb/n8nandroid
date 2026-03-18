"""Profile Manager – wraps IXBrowserClient with async helpers and batch ops."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from ixbrowser_local_api import IXBrowserClient

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ProfileInfo:
    profile_id: str
    name: str
    group_id: int = 0
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class OpenResult:
    profile_id: str
    webdriver: str
    debugging_address: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class ProfileManager:
    """Thread-safe wrapper around IXBrowserClient.

    All heavy calls are offloaded to a thread-pool so they don't block
    the asyncio event loop.  A semaphore enforces the IXBrowser API
    concurrency limit (default 3).
    """

    def __init__(self) -> None:
        self._client = IXBrowserClient(
            target=settings.ixbrowser_host,
            port=settings.ixbrowser_port,
        )
        self._sem = asyncio.Semaphore(settings.ixbrowser_max_concurrent)
        self._open_profiles: dict[str, OpenResult] = {}

    # ── helpers ──────────────────────────────────────────────────────

    async def _run(self, func, *args, **kwargs):
        """Run a blocking IXBrowserClient method in the default executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _check_error(self, result: Any, action: str) -> None:
        if result is None:
            raise RuntimeError(
                f"IXBrowser {action} failed: "
                f"code={self._client.code} msg={self._client.message}"
            )

    # ── profile listing ──────────────────────────────────────────────

    async def list_profiles(
        self,
        *,
        keyword: str | None = None,
        group_id: int = 0,
        tag_id: int = 0,
        page: int = 1,
        limit: int = 100,
    ) -> list[ProfileInfo]:
        async with self._sem:
            data = await self._run(
                self._client.get_profile_list,
                keyword=keyword,
                group_id=group_id,
                tag_id=tag_id,
                page=page,
                limit=limit,
            )
        self._check_error(data, "get_profile_list")
        return [
            ProfileInfo(
                profile_id=item["profile_id"],
                name=item.get("name", ""),
                group_id=item.get("group_id", 0),
                tags=[t.get("title", "") for t in item.get("tags", [])],
                raw=item,
            )
            for item in data
        ]

    async def list_all_profiles(
        self, *, group_id: int = 0, tag_id: int = 0, batch_size: int = 100
    ) -> list[ProfileInfo]:
        """Paginate through all profiles matching the filter."""
        all_profiles: list[ProfileInfo] = []
        page = 1
        while True:
            batch = await self.list_profiles(
                group_id=group_id, tag_id=tag_id, page=page, limit=batch_size
            )
            all_profiles.extend(batch)
            if len(batch) < batch_size:
                break
            page += 1
        return all_profiles

    # ── open / close ─────────────────────────────────────────────────

    async def open_profile(self, profile_id: str) -> OpenResult:
        async with self._sem:
            result = await self._run(
                self._client.open_profile,
                profile_id,
                cookies_backup=False,
                load_profile_info_page=False,
            )
        self._check_error(result, "open_profile")
        opened = OpenResult(
            profile_id=profile_id,
            webdriver=result["webdriver"],
            debugging_address=result["debugging_address"],
            raw=result,
        )
        self._open_profiles[profile_id] = opened
        logger.info("Opened profile %s → %s", profile_id, opened.debugging_address)
        return opened

    async def close_profile(self, profile_id: str) -> None:
        async with self._sem:
            result = await self._run(self._client.close_profile, profile_id)
        self._check_error(result, "close_profile")
        self._open_profiles.pop(profile_id, None)
        logger.info("Closed profile %s", profile_id)

    async def close_profiles_batch(self, profile_ids: list[str]) -> None:
        async with self._sem:
            result = await self._run(
                self._client.close_profile_in_batches, profile_ids
            )
        self._check_error(result, "close_profile_in_batches")
        for pid in profile_ids:
            self._open_profiles.pop(pid, None)
        logger.info("Closed %d profiles in batch", len(profile_ids))

    # ── group / tag helpers ──────────────────────────────────────────

    async def list_groups(self) -> list[dict[str, Any]]:
        async with self._sem:
            data = await self._run(self._client.get_group_list)
        self._check_error(data, "get_group_list")
        return data

    async def list_tags(self) -> list[dict[str, Any]]:
        async with self._sem:
            data = await self._run(self._client.get_tag_list)
        self._check_error(data, "get_tag_list")
        return data

    # ── state ────────────────────────────────────────────────────────

    @property
    def open_profiles(self) -> dict[str, OpenResult]:
        return dict(self._open_profiles)

    async def get_opened_list(self) -> list[dict[str, Any]]:
        async with self._sem:
            data = await self._run(self._client.get_opened_profile_list)
        self._check_error(data, "get_opened_profile_list")
        return data
