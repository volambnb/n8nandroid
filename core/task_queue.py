"""Task Queue – asyncio-based queue with concurrency control and status tracking."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from config.settings import settings

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskItem:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    profile_id: str = ""
    platform: str = ""
    task_type: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    retries: int = 0
    priority: int = 0  # lower = higher priority


class TaskQueue:
    """Async task queue with bounded concurrency (IXBrowser's 3-request limit).

    Usage::

        queue = TaskQueue(worker_fn=my_worker)
        await queue.start()
        task = queue.enqueue(TaskItem(...))
        # ... later
        await queue.stop()
    """

    def __init__(
        self,
        worker_fn: Callable[[TaskItem], Coroutine[Any, Any, Any]],
        max_concurrent: int | None = None,
    ) -> None:
        self._worker_fn = worker_fn
        self._max = max_concurrent or settings.ixbrowser_max_concurrent
        self._sem = asyncio.Semaphore(self._max)
        self._queue: asyncio.PriorityQueue[tuple[int, float, TaskItem]] = (
            asyncio.PriorityQueue()
        )
        self._tasks: dict[str, TaskItem] = {}
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._loop_task: asyncio.Task | None = None

    # ── public API ───────────────────────────────────────────────────

    def enqueue(self, item: TaskItem) -> TaskItem:
        self._tasks[item.id] = item
        self._queue.put_nowait((item.priority, item.created_at, item))
        logger.info("Enqueued task %s for profile %s", item.id, item.profile_id)
        return item

    def get_task(self, task_id: str) -> TaskItem | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[TaskItem]:
        return list(self._tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    # ── lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._dispatch_loop())
        logger.info("TaskQueue started (max_concurrent=%d)", self._max)

    async def stop(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        for w in self._workers:
            w.cancel()
        self._workers.clear()
        logger.info("TaskQueue stopped")

    # ── internal ─────────────────────────────────────────────────────

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                _, _, item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                continue

            if item.status == TaskStatus.CANCELLED:
                continue

            await self._sem.acquire()
            worker = asyncio.create_task(self._run_worker(item))
            self._workers.append(worker)
            worker.add_done_callback(lambda t: self._workers.remove(t) if t in self._workers else None)

    async def _run_worker(self, item: TaskItem) -> None:
        item.status = TaskStatus.RUNNING
        item.started_at = time.time()
        try:
            item.result = await self._worker_fn(item)
            item.status = TaskStatus.DONE
        except Exception as exc:
            logger.exception("Task %s failed", item.id)
            item.error = str(exc)
            if item.retries < settings.task_max_retries:
                item.retries += 1
                item.status = TaskStatus.PENDING
                self._queue.put_nowait((item.priority, item.created_at, item))
                logger.info("Re-queued task %s (retry %d)", item.id, item.retries)
            else:
                item.status = TaskStatus.FAILED
        finally:
            item.finished_at = time.time()
            self._sem.release()
