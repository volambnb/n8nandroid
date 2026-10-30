"""Orchestrator – central coordinator that turns commands into queued tasks."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from core.browser_agent import BrowserAgent, TaskResult
from core.profile_manager import ProfileManager
from core.task_queue import TaskItem, TaskQueue, TaskStatus
from core.task_registry import TaskRegistry

logger = logging.getLogger(__name__)


class Orchestrator:
    """High-level entry-point for the automation system.

    Typical flow:
        1. Caller invokes ``execute(...)`` with platform, task_type, params,
           and a profile filter (tag_id, group_id, or explicit list).
        2. Orchestrator resolves matching profiles.
        3. Creates a ``TaskItem`` for every profile.
        4. Enqueues them into the ``TaskQueue``.
        5. Returns a batch_id the caller can poll for status.
    """

    def __init__(self) -> None:
        self.profiles = ProfileManager()
        self.registry = TaskRegistry()
        self.agent = BrowserAgent()
        self.close_profile_on_finish = False
        self.queue = TaskQueue(worker_fn=self._worker)
        self._batches: dict[str, list[str]] = {}  # batch_id → [task_ids]

    async def start(self) -> None:
        await self.queue.start()
        logger.info("Orchestrator started")

    async def stop(self) -> None:
        await self.queue.stop()
        await self.agent.close()
        logger.info("Orchestrator stopped")

    # ── main command entry-point ─────────────────────────────────────

    async def execute(
        self,
        platform: str,
        task_type: str,
        params: dict[str, str] | None = None,
        *,
        tag_id: int = 0,
        group_id: int = 0,
        profile_ids: list[str] | None = None,
        priority: int = 0,
    ) -> dict[str, Any]:
        """Schedule tasks for matching profiles. Returns batch info."""

        # 1. Resolve the prompt template
        resolved = self.registry.resolve(platform, task_type, params)

        # 2. Get target profiles
        if profile_ids:
            all_profiles = await self.profiles.list_all_profiles(
                group_id=group_id, tag_id=tag_id
            )
            wanted = {str(pid).strip() for pid in profile_ids if str(pid).strip()}
            profiles = [p for p in all_profiles if str(p.profile_id) in wanted]
        else:
            profiles = await self.profiles.list_all_profiles(
                group_id=group_id, tag_id=tag_id
            )

        if not profiles:
            return {"error": "No matching profiles found", "count": 0}

        # 3. Create and enqueue tasks
        batch_id = uuid.uuid4().hex[:10]
        task_ids: list[str] = []
        for prof in profiles:
            item = TaskItem(
                profile_id=prof.profile_id,
                platform=platform,
                task_type=task_type,
                params={
                    "prompt": resolved.prompt,
                    "url": resolved.url,
                    "min_delay": resolved.min_delay,
                    "max_delay": resolved.max_delay,
                    **(params or {}),
                },
                priority=priority,
            )
            self.queue.enqueue(item)
            task_ids.append(item.id)

        self._batches[batch_id] = task_ids
        logger.info(
            "Batch %s: enqueued %d tasks (%s/%s)",
            batch_id,
            len(task_ids),
            platform,
            task_type,
        )
        return {
            "batch_id": batch_id,
            "count": len(task_ids),
            "task_ids": task_ids,
            "platform": platform,
            "task_type": task_type,
        }

    # ── batch status ─────────────────────────────────────────────────

    def batch_status(self, batch_id: str) -> dict[str, Any] | None:
        task_ids = self._batches.get(batch_id)
        if task_ids is None:
            return None

        tasks = [self.queue.get_task(tid) for tid in task_ids]
        tasks = [t for t in tasks if t is not None]

        summary = {s.value: 0 for s in TaskStatus}
        for t in tasks:
            summary[t.status.value] += 1

        return {
            "batch_id": batch_id,
            "total": len(tasks),
            **summary,
            "tasks": [
                {
                    "id": t.id,
                    "profile_id": t.profile_id,
                    "status": t.status.value,
                    "error": t.error,
                }
                for t in tasks
            ],
        }

    # ── worker (called by TaskQueue) ─────────────────────────────────

    async def _worker(self, item: TaskItem) -> TaskResult:
        """Open profile → run Page-Agent → close profile."""
        opened = await self.profiles.open_profile(item.profile_id)
        try:
            result = await self.agent.execute_task(
                profile=opened,
                task_prompt=item.params["prompt"],
                url=item.params.get("url"),
                min_delay=item.params.get("min_delay"),
                max_delay=item.params.get("max_delay"),
            )
            if not result.success:
                raise RuntimeError(result.error or "Page-Agent task failed")
            return result
        finally:
            if self.close_profile_on_finish:
                await self.profiles.close_profile(item.profile_id)
