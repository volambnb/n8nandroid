"""Local MCP bridge that lets Codex build and test autoIXB browser automations."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, ToolAnnotations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.catalog import node_catalog  # noqa: E402
from automation.compiler import GraphCompiler  # noqa: E402
from automation.models import AppGraph  # noqa: E402
from config.settings import settings  # noqa: E402

logger = logging.getLogger("autoixb.codex_mcp")
API_BASE_URL = os.getenv(
    "AUTOIXB_API_BASE_URL", f"http://127.0.0.1:{settings.api_port}"
).rstrip("/")
API_BEARER_TOKEN = settings.api_bearer_token.strip()
REDACTED = "[REDACTED]"

_parsed_api_url = urlparse(API_BASE_URL)
if _parsed_api_url.scheme not in {"http", "https"} or _parsed_api_url.hostname not in {
    "127.0.0.1",
    "localhost",
    "::1",
}:
    raise RuntimeError(
        "AUTOIXB_API_BASE_URL must point to a loopback address so the local API token stays on this computer"
    )

mcp = Server(
    "autoixb",
    version="1.0.0",
    instructions=(
        "Build workflows from get_node_catalog and validate the complete graph before saving. "
        "Resolve profile IDs with list_ixbrowser_profiles; never run a test against all profiles. "
        "Live tests affect the selected browser account: run only when requested, use exactly one profile ID, "
        "and rely on Codex write approval. After starting, inspect get_automation_run. Do not return secret values."
    ),
)

_client: httpx.AsyncClient | None = None


def _schema(
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


def _tool(
    name: str,
    title: str,
    description: str,
    schema: dict[str, Any],
    *,
    read_only: bool = False,
    destructive: bool = False,
    open_world: bool = False,
) -> Tool:
    return Tool(
        name=name,
        title=title,
        description=description,
        inputSchema=schema,
        annotations=ToolAnnotations(
            title=title,
            readOnlyHint=read_only,
            destructiveHint=destructive,
            openWorldHint=open_world,
        ),
    )


_GRAPH_SCHEMA = {
    "type": "object",
    "description": "Complete autoIXB graph with nodes, edges, and optional inputs.",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "minLength": 1},
                    "config": {"type": "object"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
                "required": ["id", "type"],
                "additionalProperties": True,
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "minLength": 1},
                    "to": {"type": "string", "minLength": 1},
                    "label": {"type": "string"},
                },
                "required": ["from", "to"],
                "additionalProperties": True,
            },
        },
        "inputs": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["nodes", "edges"],
    "additionalProperties": True,
}


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [
        _tool(
            "autoixb_health",
            "Check autoIXB connection",
            "Check whether the local autoIXB API is reachable and authenticated.",
            _schema(),
            read_only=True,
        ),
        _tool(
            "list_automation_apps",
            "List automation apps",
            "List saved autoIXB workflows. Use this before editing an existing workflow.",
            _schema(),
            read_only=True,
        ),
        _tool(
            "get_automation_app",
            "Get automation app",
            "Read a workflow and its graph. Secret-like config values are redacted; keep [REDACTED] values unchanged when updating.",
            _schema({"app_id": {"type": "string"}}, ["app_id"]),
            read_only=True,
        ),
        _tool(
            "get_node_catalog",
            "Get node catalog",
            "Return node types and default configs supported by autoIXB. Use this to design a graph.",
            _schema(),
            read_only=True,
        ),
        _tool(
            "list_ixbrowser_profiles",
            "Find IXBrowser profiles",
            "Search and list profiles so the user can select one exact profile for a test. Returns only profile ID, name, group and tags.",
            _schema(
                {
                    "keyword": {"type": "string", "description": "Optional profile name/keyword filter."},
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                }
            ),
            read_only=True,
        ),
        _tool(
            "validate_automation_graph",
            "Validate automation graph",
            "Validate graph schema, node types, edges, and reachability without saving or opening a browser.",
            _schema({"graph": _GRAPH_SCHEMA}, ["graph"]),
            read_only=True,
        ),
        _tool(
            "create_automation_app",
            "Create automation app",
            "Save a new workflow graph after validating it. This writes to autoIXB; use only when the user asks to create/save the workflow.",
            _schema(
                {
                    "name": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                    "graph": _GRAPH_SCHEMA,
                },
                ["name", "graph"],
            ),
        ),
        _tool(
            "update_automation_app",
            "Update automation app",
            "Replace a saved workflow graph after validating it. Values marked [REDACTED] are restored from the current saved workflow. This writes to autoIXB.",
            _schema(
                {
                    "app_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "graph": _GRAPH_SCHEMA,
                },
                ["app_id"],
            ),
        ),
        _tool(
            "run_automation_test",
            "Run workflow on one IXBrowser profile",
            "Start a live browser test for one saved workflow on exactly one explicit IXBrowser profile ID. This opens a real profile and may change websites; only use after the user asks to test and Codex approves the write action. No retries or parallel profiles are used.",
            _schema(
                {
                    "app_id": {"type": "string"},
                    "profile_id": {"type": "string", "description": "Exact ID returned by list_ixbrowser_profiles."},
                    "confirm_live_test": {
                        "type": "boolean",
                        "const": True,
                        "description": "Set true only for a user-requested live test on this exact profile.",
                    },
                    "idempotency_key": {
                        "type": "string",
                        "minLength": 8,
                        "maxLength": 160,
                        "description": "Unique stable key; reuse it if retrying the same MCP request.",
                    },
                    "inputs": {"type": "object"},
                    "timeout": {"type": "number", "minimum": 1, "maximum": 3600, "default": 180},
                },
                ["app_id", "profile_id", "confirm_live_test", "idempotency_key"],
            ),
            destructive=True,
            open_world=True,
        ),
        _tool(
            "get_automation_run",
            "Get automation run result",
            "Get safe run status, per-profile status, and per-node outcomes. Variable and output values are omitted.",
            _schema({"run_id": {"type": "string"}}, ["run_id"]),
            read_only=True,
        ),
        _tool(
            "get_automation_run_logs",
            "Get automation run logs",
            "Read recent run log messages for debugging. Secret patterns are redacted and output values are not included.",
            _schema(
                {
                    "run_id": {"type": "string"},
                    "after_id": {"type": "integer", "minimum": 0, "default": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                },
                ["run_id"],
            ),
            read_only=True,
        ),
        _tool(
            "stop_automation_run",
            "Stop automation run",
            "Cancel pending profile work and request a running graph to stop between nodes.",
            _schema({"run_id": {"type": "string"}}, ["run_id"]),
            destructive=True,
        ),
    ]


async def _api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Any:
    if _client is None:
        raise RuntimeError("MCP HTTP client is not initialized")
    headers: dict[str, str] = {}
    if API_BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {API_BEARER_TOKEN}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        response = await _client.request(
            method,
            path,
            params=params,
            json=payload,
            headers=headers,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Cannot reach autoIXB at {API_BASE_URL}; start the local autoIXB server first"
        ) from exc
    if response.is_error:
        try:
            data = response.json()
            detail = data.get("detail", data)
        except ValueError:
            detail = response.text
        raise RuntimeError(
            f"autoIXB API returned HTTP {response.status_code}: {_redact_text(str(detail))[:700]}"
        )
    if not response.content:
        return None
    return response.json()


def _all_catalog_types() -> set[str]:
    return {
        str(node.get("type") or "").strip()
        for category in node_catalog()
        for node in category.get("nodes", [])
        if str(node.get("type") or "").strip()
    }


def _validate_graph(graph_data: dict[str, Any]) -> dict[str, Any]:
    try:
        graph = AppGraph.model_validate(graph_data)
        compiled = GraphCompiler().compile(graph)
    except Exception as exc:  # Pydantic/compiler failures are returned as actionable validation output.
        return {"valid": False, "errors": [str(exc)], "warnings": []}

    known_types = _all_catalog_types()
    unknown = sorted({node.type for node in graph.nodes if node.type not in known_types})
    adjacency: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        adjacency.setdefault(edge.from_node, []).append(edge.to)
    reachable: set[str] = set()
    pending = [compiled.start_node_id]
    while pending:
        current = pending.pop()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(adjacency.get(current, []))
    unreachable = sorted(node.id for node in graph.nodes if node.id not in reachable)

    errors = [f"Unsupported node type: {node_type}" for node_type in unknown]
    warnings: list[str] = []
    if not any(node.type.strip().lower() == "start" for node in graph.nodes):
        warnings.append("No Start node; autoIXB will begin with the first node in the graph.")
    if unreachable:
        warnings.append("Nodes not reachable from Start: " + ", ".join(unreachable))
    if len([node for node in graph.nodes if node.type.strip().lower() == "start"]) > 1:
        warnings.append("Multiple Start nodes found; the first one in graph order will be used.")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "start_node_id": compiled.start_node_id,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "unreachable_node_ids": unreachable,
    }


_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|email|username)",
    re.IGNORECASE,
)
_SENSITIVE_STRING = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/-]+=*|"
    r"(?:password|passwd|secret|token|access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|authorization|cookie)\s*[=:]|"
    r"https?://[^\s/:@]+:[^\s/@]+@)"
)


def _redact_config(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return REDACTED if value not in (None, "") else value
    if isinstance(value, dict):
        return {str(child_key): _redact_config(child, str(child_key)) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_redact_config(child, key) for child in value]
    if isinstance(value, str) and _SENSITIVE_STRING.search(value):
        return REDACTED
    return value


def _restore_redacted_values(new_value: Any, old_value: Any) -> Any:
    if new_value == REDACTED:
        return old_value
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        return {
            key: _restore_redacted_values(value, old_value.get(key))
            if key in old_value
            else value
            for key, value in new_value.items()
        }
    if isinstance(new_value, list) and isinstance(old_value, list):
        return [
            _restore_redacted_values(value, old_value[index])
            if index < len(old_value)
            else value
            for index, value in enumerate(new_value)
        ]
    return new_value


def _redact_text(value: str) -> str:
    text = str(value or "")
    patterns = [
        (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*"), r"\1[REDACTED]"),
        (re.compile(r"(?i)(password|passwd|token|access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|authorization|cookie|secret)(\s*[=:]\s*)[^\s,;&]+"), r"\1\2[REDACTED]"),
        (re.compile(r"(?i)(https?://)[^\s/:@]+:[^\s/@]+@"), r"\1[REDACTED]@"),
        (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    ]
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text[:1200]


def _redact_app(app: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in app.items() if key != "graph"}
    graph = app.get("graph") or {}
    safe["graph"] = {
        **{key: value for key, value in graph.items() if key != "nodes"},
        "nodes": [
            {
                **{key: value for key, value in node.items() if key != "config"},
                "config": _redact_config(node.get("config") or {}),
            }
            for node in graph.get("nodes", [])
        ],
    }
    safe["secret_values_redacted"] = True
    return safe


def _merge_redacted_config(graph: dict[str, Any], old_graph: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(graph))
    old_nodes = {str(node.get("id")): node for node in old_graph.get("nodes", [])}
    for node in result.get("nodes", []):
        old_node = old_nodes.get(str(node.get("id")))
        if not old_node:
            continue
        node["config"] = _restore_redacted_values(
            node.get("config") or {}, old_node.get("config") or {}
        )
    return result


def _safe_run(run: dict[str, Any]) -> dict[str, Any]:
    safe_items = []
    for item in run.get("items", []):
        result = item.get("result") or {}
        node_results = []
        for node in result.get("nodes", []) if isinstance(result, dict) else []:
            outputs = node.get("outputs") or {}
            node_results.append(
                {
                    "node_id": node.get("node_id"),
                    "node_type": node.get("node_type"),
                    "status": node.get("status"),
                    "error": _redact_text(node.get("error") or "") or None,
                    "output_keys": sorted(str(key) for key in outputs),
                }
            )
        safe_items.append(
            {
                "profile_id": item.get("profile_id"),
                "status": item.get("status"),
                "error": _redact_text(item.get("error") or "") or None,
                "node_results": node_results,
            }
        )
    return {
        "run_id": run.get("id"),
        "app_id": run.get("app_id"),
        "status": run.get("status"),
        "summary": run.get("summary") or {},
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "items": safe_items,
    }


def _json_result(value: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(value, ensure_ascii=False, indent=2))]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "autoixb_health":
        data = await _api_request("GET", "/automation/apps")
        return _json_result({"connected": True, "api_base_url": API_BASE_URL, "saved_workflow_count": len(data)})

    if name == "list_automation_apps":
        return _json_result(await _api_request("GET", "/automation/apps"))

    if name == "get_automation_app":
        app = await _api_request("GET", f"/automation/apps/{arguments['app_id']}")
        return _json_result(_redact_app(app))

    if name == "get_node_catalog":
        return _json_result({"categories": node_catalog()})

    if name == "list_ixbrowser_profiles":
        page = max(1, int(arguments.get("page", 1)))
        limit = max(1, min(100, int(arguments.get("limit", 50))))
        params: dict[str, Any] = {"page": page, "limit": limit}
        keyword = str(arguments.get("keyword") or "").strip()
        if keyword:
            params["keyword"] = keyword
        data = await _api_request("GET", "/ix/profiles", params=params)
        profiles = [
            {
                "profile_id": str(profile.get("profile_id") or profile.get("id") or ""),
                "name": str(profile.get("name") or ""),
                "group_id": profile.get("group_id"),
                "tags": [tag.get("title", "") if isinstance(tag, dict) else str(tag) for tag in profile.get("tags", [])],
            }
            for profile in data.get("profiles", [])
        ]
        return _json_result({"total": int(data.get("total", len(profiles))), "page": page, "limit": limit, "profiles": profiles})

    if name == "validate_automation_graph":
        return _json_result(_validate_graph(arguments["graph"]))

    if name == "create_automation_app":
        validation = _validate_graph(arguments["graph"])
        if not validation["valid"]:
            raise ValueError("Graph validation failed: " + "; ".join(validation["errors"]))
        graph = AppGraph.model_validate(arguments["graph"]).model_dump(mode="json", by_alias=True)
        app = await _api_request(
            "POST",
            "/automation/apps",
            payload={"name": str(arguments["name"]).strip(), "description": arguments.get("description", ""), "graph": graph},
        )
        return _json_result({"app_id": app.get("id"), "name": app.get("name"), "version": app.get("version"), "node_count": len(graph["nodes"])})

    if name == "update_automation_app":
        app_id = str(arguments["app_id"])
        old_app = await _api_request("GET", f"/automation/apps/{app_id}")
        payload: dict[str, Any] = {}
        for key in ("name", "description"):
            if key in arguments:
                payload[key] = arguments[key]
        if "graph" in arguments:
            validation = _validate_graph(arguments["graph"])
            if not validation["valid"]:
                raise ValueError("Graph validation failed: " + "; ".join(validation["errors"]))
            graph = AppGraph.model_validate(arguments["graph"]).model_dump(mode="json", by_alias=True)
            payload["graph"] = _merge_redacted_config(graph, old_app.get("graph") or {})
        app = await _api_request("PUT", f"/automation/apps/{app_id}", payload=payload)
        return _json_result({"app_id": app.get("id"), "name": app.get("name"), "version": app.get("version"), "node_count": len((app.get("graph") or {}).get("nodes", []))})

    if name == "run_automation_test":
        if arguments.get("confirm_live_test") is not True:
            raise ValueError("A live test requires confirm_live_test=true after user approval.")
        app_id = str(arguments["app_id"])
        profile_id = str(arguments["profile_id"]).strip()
        if not profile_id.isdigit():
            raise ValueError("profile_id must be the exact numeric ID returned by list_ixbrowser_profiles.")
        app = await _api_request("GET", f"/automation/apps/{app_id}")
        validation = _validate_graph(app.get("graph") or {})
        if not validation["valid"]:
            raise ValueError("Saved workflow is invalid: " + "; ".join(validation["errors"]))
        profile_data = await _api_request("GET", "/ix/profiles", params={"profile_id": int(profile_id), "page": 1, "limit": 1})
        match = next(
            (p for p in profile_data.get("profiles", []) if str(p.get("profile_id") or p.get("id") or "") == profile_id),
            None,
        )
        if not match:
            raise ValueError(f"IXBrowser profile {profile_id} was not found. Refresh the profile list and choose an exact ID.")
        timeout = max(1, min(3600, float(arguments.get("timeout", 180))))
        request = {
            "app_id": app_id,
            "inputs": arguments.get("inputs") or {},
            "profile_selector": {"profile_ids": [profile_id]},
            "concurrency": 1,
            "retry": 0,
            "timeout": timeout,
            "stop_on_error": True,
            "close_profile_on_finish": False,
        }
        run = await _api_request(
            "POST",
            "/automation/runs",
            payload=request,
            idempotency_key=str(arguments["idempotency_key"]).strip(),
        )
        return _json_result(
            {
                "run_id": run.get("run_id"),
                "app_id": app_id,
                "profile_id": profile_id,
                "profile_name": match.get("name", ""),
                "status": "queued",
                "next_tool": "get_automation_run",
            }
        )

    if name == "get_automation_run":
        run = await _api_request("GET", f"/automation/runs/{arguments['run_id']}")
        return _json_result(_safe_run(run))

    if name == "get_automation_run_logs":
        logs = await _api_request(
            "GET",
            f"/automation/runs/{arguments['run_id']}/logs",
            params={"after_id": max(0, int(arguments.get("after_id", 0))), "limit": max(1, min(100, int(arguments.get("limit", 50))))},
        )
        safe_logs = [
            {
                "id": entry.get("id"),
                "ts": entry.get("ts"),
                "level": entry.get("level"),
                "node_id": entry.get("node_id"),
                "message": _redact_text(entry.get("message") or ""),
            }
            for entry in logs
        ]
        return _json_result(safe_logs)

    if name == "stop_automation_run":
        return _json_result(await _api_request("POST", f"/automation/runs/{arguments['run_id']}/stop"))

    raise ValueError(f"Unknown autoIXB tool: {name}")


async def run_mcp_server() -> None:
    global _client
    timeout = httpx.Timeout(30.0, connect=5.0)
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=timeout, trust_env=False) as client:
        _client = client
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp.run(read_stream, write_stream, mcp.create_initialization_options())
        finally:
            _client = None


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
