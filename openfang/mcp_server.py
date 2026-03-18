"""OpenFang MCP Server – exposes automation tools to OpenFang via Model Context Protocol."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Shared orchestrator instance (initialised in main)
_orchestrator: Orchestrator | None = None


def _get_orch() -> Orchestrator:
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialised")
    return _orchestrator


# ── MCP Server definition ───────────────────────────────────────────

mcp = Server("ixbrowser-automation")


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="execute_task",
            description=(
                "Execute an automation task on IXBrowser profiles. "
                "Supports platforms: x, facebook, tiktok, generic. "
                "Tasks include: post_tweet, like_tweet, follow_user, "
                "post_status, like_video, warm_up, custom, and more."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["x", "facebook", "tiktok", "generic"],
                        "description": "Target platform",
                    },
                    "task_type": {
                        "type": "string",
                        "description": "Task template name (e.g. post_tweet, warm_up, custom)",
                    },
                    "params": {
                        "type": "object",
                        "description": "Template variables (content, target_user, instruction, etc.)",
                        "additionalProperties": {"type": "string"},
                    },
                    "tag_id": {
                        "type": "integer",
                        "description": "Filter profiles by tag ID (0 = all)",
                        "default": 0,
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "Filter profiles by group ID (0 = all)",
                        "default": 0,
                    },
                    "profile_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific profile IDs to target (overrides tag/group filter)",
                    },
                },
                "required": ["platform", "task_type"],
            },
        ),
        Tool(
            name="list_profiles",
            description="List IXBrowser profiles, optionally filtered by group or tag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer", "default": 0},
                    "tag_id": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="get_task_status",
            description="Get the status of a batch of tasks by batch_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string", "description": "Batch ID returned by execute_task"},
                },
                "required": ["batch_id"],
            },
        ),
        Tool(
            name="list_templates",
            description="List available task templates per platform.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="stop_batch",
            description="Cancel all pending tasks in a batch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string"},
                },
                "required": ["batch_id"],
            },
        ),
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    orch = _get_orch()

    if name == "execute_task":
        result = await orch.execute(
            platform=arguments["platform"],
            task_type=arguments["task_type"],
            params=arguments.get("params"),
            tag_id=arguments.get("tag_id", 0),
            group_id=arguments.get("group_id", 0),
            profile_ids=arguments.get("profile_ids"),
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "list_profiles":
        profiles = await orch.profiles.list_profiles(
            group_id=arguments.get("group_id", 0),
            tag_id=arguments.get("tag_id", 0),
            limit=arguments.get("limit", 50),
        )
        data = [
            {"profile_id": p.profile_id, "name": p.name, "tags": p.tags}
            for p in profiles
        ]
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "get_task_status":
        status = orch.batch_status(arguments["batch_id"])
        if status is None:
            return [TextContent(type="text", text="Batch not found")]
        return [TextContent(type="text", text=json.dumps(status, indent=2))]

    if name == "list_templates":
        templates = {
            plat: orch.registry.task_types(plat)
            for plat in orch.registry.platforms
        }
        return [TextContent(type="text", text=json.dumps(templates, indent=2))]

    if name == "stop_batch":
        status = orch.batch_status(arguments["batch_id"])
        if status is None:
            return [TextContent(type="text", text="Batch not found")]
        cancelled = sum(
            1 for t in status.get("tasks", []) if orch.queue.cancel_task(t["id"])
        )
        return [TextContent(type="text", text=f"Cancelled {cancelled} pending tasks")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── entry-point ──────────────────────────────────────────────────────

async def run_mcp_server() -> None:
    global _orchestrator
    _orchestrator = Orchestrator()
    await _orchestrator.start()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(read_stream, write_stream, mcp.create_initialization_options())
    finally:
        await _orchestrator.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
