"""FastAPI Server – REST API for controlling the automation system."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from config.settings import settings
from core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await orchestrator.start()
    yield
    await orchestrator.stop()


app = FastAPI(title="IXBrowser Automation", version="1.0.0", lifespan=lifespan)


# ── request / response models ────────────────────────────────────────

class ExecuteRequest(BaseModel):
    platform: str = Field(..., description="x | facebook | tiktok | generic")
    task_type: str = Field(..., description="post_tweet, like_tweet, warm_up, custom, …")
    params: dict[str, str] = Field(default_factory=dict, description="Template variables")
    tag_id: int = 0
    group_id: int = 0
    profile_ids: list[str] | None = None
    priority: int = 0


class BatchStatusResponse(BaseModel):
    batch_id: str
    total: int
    pending: int = 0
    running: int = 0
    done: int = 0
    failed: int = 0
    cancelled: int = 0
    tasks: list[dict[str, Any]] = []


# ── routes ───────────────────────────────────────────────────────────

@app.post("/tasks/execute", response_model=dict)
async def execute_task(req: ExecuteRequest):
    """Schedule automation tasks for matching profiles."""
    result = await orchestrator.execute(
        platform=req.platform,
        task_type=req.task_type,
        params=req.params,
        tag_id=req.tag_id,
        group_id=req.group_id,
        profile_ids=req.profile_ids,
        priority=req.priority,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/tasks/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """Poll batch execution status."""
    status = orchestrator.batch_status(batch_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return status


@app.get("/profiles")
async def list_profiles(
    group_id: int = 0,
    tag_id: int = 0,
    page: int = 1,
    limit: int = 50,
):
    """List IXBrowser profiles."""
    profiles = await orchestrator.profiles.list_profiles(
        group_id=group_id, tag_id=tag_id, page=page, limit=limit
    )
    return {
        "count": len(profiles),
        "profiles": [
            {"profile_id": p.profile_id, "name": p.name, "tags": p.tags}
            for p in profiles
        ],
    }


@app.get("/profiles/groups")
async def list_groups():
    return await orchestrator.profiles.list_groups()


@app.get("/profiles/tags")
async def list_tags():
    return await orchestrator.profiles.list_tags()


@app.get("/templates")
async def list_templates():
    """List available task templates per platform."""
    return {
        platform: orchestrator.registry.task_types(platform)
        for platform in orchestrator.registry.platforms
    }


# ── WebSocket for real-time status ───────────────────────────────────

@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            tasks = orchestrator.queue.get_all_tasks()
            summary = {
                "pending": sum(1 for t in tasks if t.status.value == "pending"),
                "running": sum(1 for t in tasks if t.status.value == "running"),
                "done": sum(1 for t in tasks if t.status.value == "done"),
                "failed": sum(1 for t in tasks if t.status.value == "failed"),
                "total": len(tasks),
            }
            await websocket.send_json(summary)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
