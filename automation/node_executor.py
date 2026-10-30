from __future__ import annotations

import asyncio
import base64
import csv
import imaplib
import json
import os
import random
import re
import time
import traceback
from dataclasses import dataclass, field
from email import message_from_bytes
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx
from playwright.async_api import Browser, BrowserContext, Frame, Page, Playwright

from automation.compiler import CompiledGraph
from automation.apk_installer import apk_asset_path, apk_identity, device_model, device_version, install_apk, validate_apk
from automation.error_diagnostics import diagnose_node_error, selector_match_count
from automation.models import Node
from automation.variable_sources import read_variable_cell
from config.settings import settings


_SENSITIVE_LOG_KEY = re.compile(
    r"(?:password|passwd|passphrase|secret|token|authorization|cookie|credential|api[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|passphrase|secret|token|authorization|cookie|api[_-]?key)\b"
    r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_EMAIL_VALUE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def _safe_log_text(value: Any, *, limit: int = 2000) -> str:
    text = str(value or "")
    text = _SENSITIVE_ASSIGNMENT.sub(r"\1\2[REDACTED]", text)
    text = _BEARER_VALUE.sub("Bearer [REDACTED]", text)
    text = _EMAIL_VALUE.sub("[REDACTED_EMAIL]", text)
    if len(text) > limit:
        text = text[:limit] + "… [truncated]"
    return text


def _safe_log_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _SENSITIVE_LOG_KEY.search(key):
        return "[REDACTED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_log_text(value, limit=320)
    if depth >= 4:
        return f"<{type(value).__name__}>"
    if isinstance(value, dict):
        items = list(value.items())
        summary = {
            str(item_key)[:80]: _safe_log_value(item_value, key=str(item_key), depth=depth + 1)
            for item_key, item_value in items[:12]
        }
        if len(items) > 12:
            summary["_truncated_items"] = len(items) - 12
        return summary
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        summary = [_safe_log_value(item, depth=depth + 1) for item in items[:10]]
        if len(items) > 10:
            summary.append(f"… {len(items) - 10} more")
        return summary
    if isinstance(value, bytes):
        return f"<bytes: {len(value)} bytes>"
    return _safe_log_text(repr(value), limit=320)


def _safe_page_url(page: Page) -> str:
    try:
        parts = urlsplit(page.url)
        hostname = parts.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        if parts.port:
            hostname = f"{hostname}:{parts.port}"
        if parts.netloc and not hostname:
            return "[URL unavailable]"
        if parts.netloc:
            return urlunsplit((parts.scheme, hostname, parts.path, "", ""))
        return urlunsplit((parts.scheme, "", parts.path, "", ""))
    except Exception:  # noqa: BLE001
        return "[URL unavailable]"


@dataclass
class NodeExecutionResult:
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    next_label: str = "next"
    error: str | None = None
    capability_flags: list[str] = field(default_factory=list)


class RunStopRequested(Exception):
    """Raised when a run is explicitly stopped while a node is executing."""


@dataclass
class NodeRunRecord:
    node_id: str
    node_type: str
    status: str
    started_at: float
    finished_at: float
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    capability_flags: list[str] = field(default_factory=list)


@dataclass
class NodeExecutionContext:
    run_id: str
    run_item_id: str
    profile_id: str
    playwright: Playwright
    browser: Browser
    browser_context: BrowserContext
    active_page: Page
    profile_debug_url: str
    variables: dict[str, Any]
    secret_variables: set[str] = field(default_factory=set)
    secret_values: set[str] = field(default_factory=set)
    loop_state: dict[str, Any] = field(default_factory=dict)
    stop_requested: bool = False
    active_frame: Frame | None = None
    dialog_handler_registered: bool = False
    run_timeout: float = 300.0
    log: Callable[[str, str, str | None, dict[str, Any] | None], Awaitable[None]] | None = None
    should_stop: Callable[[], Awaitable[bool]] | None = None
    stop_event: asyncio.Event | None = None
    reconnect: Callable[[], Awaitable[tuple[Browser, BrowserContext, Page]]] | None = None
    profile_field_get: Callable[[str, str], Awaitable[str | None]] | None = None
    profile_field_set: Callable[[str, str, str], Awaitable[None]] | None = None
    profile_tag_get: Callable[[str], Awaitable[list[str]]] | None = None
    profile_tag_set: Callable[[str, list[str]], Awaitable[None]] | None = None
    phone_workers: Any = None
    image_asset_get: Callable[[str], Awaitable[dict[str, Any] | None]] | None = None
    called_apps: dict[str, CompiledGraph] = field(default_factory=dict)
    app_depth: int = 0
    app_stack: list[str] = field(default_factory=list)
    last_node_error: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in self.secret_variables:
            value = self.variables.get(name)
            if value is not None:
                self.secret_values.add(str(value))

    def redact_log_value(self, value: Any, *, key: str = "", depth: int = 0) -> Any:
        if key.casefold() in {name.casefold() for name in self.secret_variables}:
            return "[REDACTED]"
        if _SENSITIVE_LOG_KEY.search(key):
            return "[REDACTED]"
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            redacted = value
            for secret in sorted(self.secret_values, key=len, reverse=True):
                if not secret:
                    continue
                if redacted == secret:
                    return "[REDACTED]"
                if len(secret) >= 4:
                    redacted = redacted.replace(secret, "[REDACTED]")
            return _safe_log_text(redacted, limit=320)
        if depth >= 4:
            return f"<{type(value).__name__}>"
        if isinstance(value, dict):
            return {
                str(item_key)[:80]: self.redact_log_value(item_value, key=str(item_key), depth=depth + 1)
                for item_key, item_value in list(value.items())[:12]
            }
        if isinstance(value, (list, tuple, set)):
            return [self.redact_log_value(item, depth=depth + 1) for item in list(value)[:10]]
        if isinstance(value, bytes):
            return f"<bytes: {len(value)} bytes>"
        return _safe_log_text(repr(value), limit=320)

    async def emit_log(
        self,
        level: str,
        message: str,
        node_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self.log:
            safe_message = self.redact_log_value(str(message))
            safe_data = self.redact_log_value(data) if data is not None else None
            await self.log(level, str(safe_message), node_id, safe_data)

    def get_target(self) -> Page | Frame:
        return self.active_frame if self.active_frame else self.active_page

    def set_var(self, name: str, value: Any) -> None:
        self.variables[name] = value
        if name in self.secret_variables and value is not None:
            self.secret_values.add(str(value))

    def get_var(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)


class NodeExecutor:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[NodeExecutionContext, Node], Awaitable[NodeExecutionResult]]] = {
            "start": self._h_start,
            "variables": self._h_variables,
            "stop": self._h_stop,
            "new_tab": self._h_new_tab,
            "open_url": self._h_open_url,
            "activate_tab": self._h_activate_tab,
            "close_tab": self._h_close_tab,
            "reload_tab": self._h_reload_tab,
            "click": self._h_click,
            "mouse_movement": self._h_mouse_movement,
            "scroll": self._h_scroll,
            "press_key": self._h_press_key,
            "type_text": self._h_type_text,
            "element_exist": self._h_element_exist,
            "element_exists": self._h_element_exist,
            "get_url": self._h_get_url,
            "get_text": self._h_get_text,
            "get_value": self._h_get_value,
            "get_attribute": self._h_get_attribute,
            "select_dropdown": self._h_select_dropdown,
            "random": self._h_random,
            "file_upload": self._h_file_upload,
            "http": self._h_http,
            "read_file_variable": self._h_read_file_variable,
            "write_file": self._h_write_file,
            "cookies": self._h_cookies,
            "save_asset": self._h_save_asset,
            "spreadsheet": self._h_spreadsheet,
            "open_ai": self._h_open_ai,
            "case_path": self._h_case_path,
            "insert_data": self._h_insert_data,
            "regexp_data_extraction": self._h_regexp_extraction,
            "imap_read_mail": self._h_imap_read_mail,
            "update_field": self._h_update_field,
            "two_fa": self._h_two_fa,
            "bypass": self._h_bypass,
            "cmd": self._h_cmd,
            "artemis": self._h_artemis,
            "artemis_open_app": self._h_artemis_phone_action,
            "artemis_install_apks": self._h_artemis_install_apks,
            "artemis_stop_app": self._h_artemis_phone_action,
            "artemis_get_ui": self._h_artemis_phone_action,
            "artemis_find_element": self._h_artemis_phone_action,
            "artemis_wait_element": self._h_artemis_phone_action,
            "artemis_read_text": self._h_artemis_phone_action,
            "artemis_tap": self._h_artemis_phone_action,
            "artemis_long_press": self._h_artemis_phone_action,
            "artemis_double_tap": self._h_artemis_phone_action,
            "artemis_swipe": self._h_artemis_phone_action,
            "artemis_type_text": self._h_artemis_phone_action,
            "artemis_clear_text": self._h_artemis_phone_action,
            "artemis_set_clipboard": self._h_artemis_phone_action,
            "artemis_key_event": self._h_artemis_phone_action,
            "artemis_screenshot": self._h_artemis_phone_action,
            "log": self._h_log,
            "disconnect": self._h_disconnect,
            "update_tag": self._h_update_tag,
            "get_tag": self._h_get_tag,
            "profile_note": self._h_profile_note,
            "image_search": self._h_image_search,
            "screenshot": self._h_screenshot,
            "clipboard": self._h_clipboard,
            "switch_frame": self._h_switch_frame,
            "switch_page": self._h_switch_page,
            "switch_extension_popup_v2": self._h_switch_extension_popup_v2,
            "trigger_extension": self._h_trigger_extension,
            "dialog_alert": self._h_dialog_alert,
            "sleep": self._h_sleep,
            "if": self._h_if,
            "eval": self._h_eval,
            "javascript": self._h_javascript,
            "loop": self._h_loop,
            "loop_v2_break_loop": self._h_loop_break,
            "emulate": self._h_emulate,
            "comment": self._h_comment,
            "call_app": self._h_call_app,
            "artemis_find_image": self._h_artemis_phone_action,
            "artemis_tap_image": self._h_artemis_phone_action,
            "analyze_error": self._h_artemis_analyze_error,
            "artemis_analyze_error": self._h_artemis_analyze_error,
        }

    async def execute_graph(
        self,
        compiled: CompiledGraph,
        ctx: NodeExecutionContext,
    ) -> dict[str, Any]:
        start_time = time.time()
        current = compiled.start_node_id
        results: list[NodeRunRecord] = []
        max_steps = 4000
        step = 0

        while current:
            step += 1
            if step > max_steps:
                raise RuntimeError("Graph exceeded max steps (possible infinite loop)")
            if await self._stop_requested(ctx):
                ctx.stop_requested = True
            if ctx.stop_requested:
                break
            if time.time() - start_time > ctx.run_timeout:
                raise RuntimeError(f"Run exceeded timeout ({ctx.run_timeout}s)")

            node = compiled.nodes[current]
            default_sleep = 1 if self._normalise_type(node.type).startswith("artemis") else 2
            sleep_before = float(
                self._resolve(ctx, node.config.get("sleep_before_run_seconds", default_sleep)) or 0
            )
            if sleep_before > 0:
                await ctx.emit_log(
                    "info",
                    f"Sleep before node: {sleep_before:.2f}s",
                    node.id,
                    {"sleep_before_run_seconds": sleep_before, "app_path": list(ctx.app_stack)},
                )
                if not await self._sleep_or_stop(ctx, sleep_before):
                    ctx.stop_requested = True
                    await ctx.emit_log(
                        "warning",
                        "Node cancelled before it started: stop requested",
                        node.id,
                        {
                            "event": "node_cancelled",
                            "node_type": node.type,
                            "step": step,
                            "duration_ms": 0,
                            "started": False,
                            "app_path": list(ctx.app_stack),
                        },
                    )
                    break

            started = time.time()
            await ctx.emit_log(
                "info",
                f"Node started: {node.type}",
                node.id,
                {
                    "event": "node_started",
                    "node_type": node.type,
                    "step": step,
                    "config_fields": sorted(str(key) for key in node.config),
                    "page_url": _safe_page_url(ctx.active_page),
                    "app_path": list(ctx.app_stack),
                },
            )
            failure_traceback = ""
            failure_type = ""
            try:
                result = await self.run_node(ctx, node)
                status = result.status
                error = result.error
            except RunStopRequested:
                ctx.stop_requested = True
                error = "Run stopped by user"
                result = NodeExecutionResult(status="cancelled", error=error, next_label="stop")
                status = "cancelled"
            except Exception as exc:  # noqa: BLE001
                failure_type = type(exc).__name__
                error = str(ctx.redact_log_value(str(exc).strip() or repr(exc)))
                failure_traceback = str(ctx.redact_log_value(
                    "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                ))[:8000]
                result = NodeExecutionResult(status="failed", error=error, next_label="error")
                status = "failed"

            finished = time.time()
            duration_ms = round(max(0.0, finished - started) * 1000, 1)
            if str(status).lower() == "failed":
                error = _safe_log_text(error or "Node returned a failed status without an error message.", limit=2000)
                diagnostic_config_keys = {
                    "package_name", "activity", "selector", "selector_by", "selector_type",
                    "match_mode", "wait_state", "wait_timeout_seconds", "timeout",
                    "threshold", "image_asset_id", "method",
                }
                ctx.last_node_error = {
                    "node_id": node.id,
                    "node_type": node.type,
                    "step": step,
                    "duration_ms": duration_ms,
                    "error_type": failure_type or "NodeExecutionError",
                    "error": error,
                    "traceback": failure_traceback,
                    "page_url": _safe_page_url(ctx.active_page),
                    "config_summary": {
                        key: ctx.redact_log_value(value, key=key)
                        for key, value in node.config.items()
                        if key in diagnostic_config_keys
                    },
                    "app_path": list(ctx.app_stack),
                }
                await ctx.emit_log(
                    "error",
                    f"Node failed: {error}",
                    node.id,
                    {
                        "event": "node_failed",
                        "node_type": node.type,
                        "step": step,
                        "duration_ms": duration_ms,
                        "error_type": failure_type or "NodeExecutionError",
                        "error": error,
                        "page_url": _safe_page_url(ctx.active_page),
                        "config_fields": sorted(str(key) for key in node.config),
                        "traceback": failure_traceback,
                        "app_path": list(ctx.app_stack),
                    },
                )
            elif str(status).lower() == "cancelled":
                await ctx.emit_log(
                    "warning",
                    "Node cancelled: stop requested; no following node will run",
                    node.id,
                    {
                        "event": "node_cancelled",
                        "node_type": node.type,
                        "step": step,
                        "duration_ms": duration_ms,
                        "started": True,
                        "app_path": list(ctx.app_stack),
                    },
                )
            else:
                output_summary = _safe_log_value(result.outputs)
                output_json = json.dumps(output_summary, ensure_ascii=False, default=str)
                if len(output_json) > 3500:
                    output_summary = {
                        "summary": output_json[:3400] + "… [truncated]",
                        "output_keys": sorted(str(key) for key in result.outputs)[:30],
                    }
                await ctx.emit_log(
                    "info",
                    f"Node succeeded: {node.type}",
                    node.id,
                    {
                        "event": "node_succeeded",
                        "node_type": node.type,
                        "step": step,
                        "duration_ms": duration_ms,
                        "next_label": result.next_label,
                        "outputs": output_summary,
                        "capability_flags": list(result.capability_flags),
                        "app_path": list(ctx.app_stack),
                    },
                )
            results.append(
                NodeRunRecord(
                    node_id=node.id,
                    node_type=node.type,
                    status=status,
                    started_at=started,
                    finished_at=finished,
                    outputs=result.outputs,
                    error=error,
                    capability_flags=result.capability_flags,
                )
            )
            for k, v in result.outputs.items():
                ctx.set_var(k, v)

            if status == "cancelled":
                break
            if result.next_label == "stop":
                break
            if status == "failed" and not compiled.next_node(node.id, "error"):
                raise RuntimeError(error or f"Node {node.id} failed")

            current = compiled.next_node(node.id, result.next_label)

        return ctx.redact_log_value({
            "steps": len(results),
            "finished": not ctx.stop_requested,
            "stopped": ctx.stop_requested,
            "variables": ctx.variables,
            "nodes": [r.__dict__ for r in results],
        })

    async def run_node(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        key = self._normalise_type(node.type)
        handler = self._handlers.get(key, self._h_unknown)
        timeout = float(self._resolve(ctx, node.config.get("timeout", 120)))
        # Element Exist has its own locator timeout and converts a miss into
        # the explicit false branch. Give that handler a small outer cushion
        # so asyncio.wait_for does not cancel it at the same deadline first.
        execution_timeout = timeout + 1.0 if timeout > 0 and key == "element_exists" else timeout
        return await self._run_handler_until_stopped(
            ctx,
            handler(ctx, node),
            execution_timeout if execution_timeout > 0 else None,
        )

    async def _run_handler_until_stopped(
        self,
        ctx: NodeExecutionContext,
        handler_awaitable: Awaitable[NodeExecutionResult],
        timeout: float | None,
    ) -> NodeExecutionResult:
        if ctx.stop_event is not None and ctx.stop_event.is_set():
            raise RunStopRequested

        handler_task = asyncio.create_task(handler_awaitable)
        stop_task = asyncio.create_task(ctx.stop_event.wait()) if ctx.stop_event is not None else None
        wait_tasks = {handler_task}
        if stop_task is not None:
            wait_tasks.add(stop_task)

        try:
            done, _ = await asyncio.wait(
                wait_tasks,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task is not None and stop_task in done:
                handler_task.cancel()
                await asyncio.gather(handler_task, return_exceptions=True)
                raise RunStopRequested
            if handler_task in done:
                return await handler_task

            handler_task.cancel()
            await asyncio.gather(handler_task, return_exceptions=True)
            if timeout is not None:
                raise TimeoutError(f"Node execution exceeded its {timeout:g}s timeout.")
            raise RuntimeError("Node handler ended without a result")
        finally:
            if stop_task is not None:
                stop_task.cancel()
                await asyncio.gather(stop_task, return_exceptions=True)

    @staticmethod
    async def _stop_requested(ctx: NodeExecutionContext) -> bool:
        if ctx.stop_event is not None and ctx.stop_event.is_set():
            return True
        return bool(ctx.should_stop is not None and await ctx.should_stop())

    async def _sleep_or_stop(self, ctx: NodeExecutionContext, seconds: float) -> bool:
        if ctx.stop_event is None:
            await asyncio.sleep(seconds)
            return not await self._stop_requested(ctx)
        if ctx.stop_event.is_set():
            return False

        sleep_task = asyncio.create_task(asyncio.sleep(seconds))
        stop_task = asyncio.create_task(ctx.stop_event.wait())
        try:
            done, _ = await asyncio.wait(
                {sleep_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done:
                return False
            return True
        finally:
            for task in (sleep_task, stop_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(sleep_task, stop_task, return_exceptions=True)

    def _normalise_type(self, value: str) -> str:
        value = value.strip().lower()
        for token in ("(", ")", "-", ":", "/", "."):
            value = value.replace(token, " ")
        value = "_".join(value.split())
        aliases = {
            "start_stop": "start",
            "variable": "variables",
            "element_exist": "element_exists",
            "regexp": "regexp_data_extraction",
            "regexp_data": "regexp_data_extraction",
            "regexp_data_extraction_data_extraction": "regexp_data_extraction",
            "imap_read_mail": "imap_read_mail",
            "twofa": "two_fa",
            "loop_v2_break": "loop_v2_break_loop",
            "switch_extension_popup": "switch_extension_popup_v2",
            "dialog": "dialog_alert",
            "alert": "dialog_alert",
            "openai": "open_ai",
            # Older recorder builds serialized the palette label as a type.
            "artemis_connect": "artemis",
        }
        return aliases.get(value, value)

    def _resolve(self, ctx: NodeExecutionContext, value: Any) -> Any:
        if isinstance(value, str):
            resolved = value
            for key, var in ctx.variables.items():
                resolved = resolved.replace("{{" + key + "}}", str(var))

            class _Safe(dict):
                def __missing__(self, key: str) -> str:
                    return "{" + key + "}"

            try:
                resolved = resolved.format_map(_Safe({k: str(v) for k, v in ctx.variables.items()}))
            except Exception:
                pass
            return resolved
        if isinstance(value, dict):
            return {k: self._resolve(ctx, v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._resolve(ctx, v) for v in value]
        return value

    def _selector(self, node: Node) -> str:
        stype = str(node.config.get("selector_type", "css")).strip().lower()
        selector = str(node.config.get("selector", "")).strip()
        if not selector:
            raise ValueError("Missing selector")
        if stype == "xpath":
            return f"xpath={selector}"
        if stype == "text":
            return f"text={selector}"
        return selector

    async def _expect_locator(self, ctx: NodeExecutionContext, node: Node):
        selector = self._selector(node)
        return ctx.get_target().locator(selector)

    def _bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)

    def _eval_expr(self, ctx: NodeExecutionContext, expr: str) -> Any:
        resolved = str(self._resolve(ctx, expr))
        return eval(  # noqa: S307
            resolved,
            {"__builtins__": {"len": len, "int": int, "float": float, "str": str, "bool": bool}},
            dict(ctx.variables),
        )

    async def _not_implemented(
        self,
        ctx: NodeExecutionContext,
        node: Node,
        reason: str,
        *,
        next_label: str = "next",
    ) -> NodeExecutionResult:
        await ctx.emit_log(
            "warning",
            f"Capability fallback for node '{node.type}': {reason}",
            node.id,
            {"capability_flag": reason},
        )
        return NodeExecutionResult(status="ok", next_label=next_label, capability_flags=[reason])

    async def _h_start(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        return NodeExecutionResult(status="ok")

    async def _h_variables(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        raw_items = node.config.get("custom_variables", [])
        if not isinstance(raw_items, list):
            raw_items = []
        outputs: dict[str, Any] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ValueError(f"Invalid variable name: {name}")
            if item.get("secret"):
                ctx.secret_variables.add(name)
            source = str(item.get("source") or "value").strip().lower()
            if source in {"value", "static"}:
                if item.get("allow_override") and name in ctx.variables:
                    value = self._resolve(ctx, ctx.variables[name])
                else:
                    value = self._resolve(ctx, item.get("value", ""))
            elif source in {"input", "run_input"}:
                input_name = str(item.get("input_name") or name).strip()
                value = ctx.get_var(input_name)
                if value is None:
                    raise ValueError(f"Run input for variable '{name}' is missing: {input_name}")
            elif source == "file":
                file_path = str(self._resolve(ctx, item.get("file_path", ""))).strip()
                row_input = str(item.get("row_input") or "").strip()
                row_value = ctx.get_var(row_input) if row_input else self._resolve(ctx, item.get("row_index", 1))
                try:
                    row_index = int(row_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Variable '{name}' needs a numeric data row.") from exc
                value = await asyncio.to_thread(
                    read_variable_cell, file_path, row_index=row_index,
                    column=str(self._resolve(ctx, item.get("column", ""))),
                    sheet_name=str(self._resolve(ctx, item.get("sheet_name", ""))),
                    has_header=self._bool(item.get("has_header", True)),
                )
            else:
                raise ValueError(f"Unsupported variable source for '{name}': {source}")
            ctx.set_var(name, value)
            outputs[name] = value
        return NodeExecutionResult(status="ok", outputs=outputs)

    async def _h_stop(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        # In a called graph Stop is a return to its caller. It must not cancel
        # the outer graph or close the shared IXBrowser session.
        if ctx.app_depth == 0:
            ctx.stop_requested = True
        if ctx.app_depth == 0 and self._bool(node.config.get("stop_browser", True)):
            try:
                await ctx.browser.close()
            except Exception:
                pass
        return NodeExecutionResult(status="ok", next_label="stop")

    async def _h_call_app(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        app_id = str(node.config.get("app_id", "")).strip()
        child = ctx.called_apps.get(app_id)
        if not app_id or child is None:
            raise ValueError(f"Call App references an unavailable app: {app_id or '(empty)'}")
        if app_id in ctx.app_stack:
            raise ValueError(f"Recursive app call detected: {' -> '.join([*ctx.app_stack, app_id])}")
        if ctx.app_depth >= 8:
            raise ValueError("Call App exceeded the maximum nesting depth of 8.")

        parent_variables = ctx.variables
        child_variables = dict(parent_variables)
        for key, default in child.input_defaults.items():
            if key not in child_variables:
                child_variables[key] = self._resolve(ctx, default)
        input_mapping = node.config.get("input_mapping", {})
        if isinstance(input_mapping, dict):
            for child_key, source in input_mapping.items():
                if isinstance(source, str) and source.startswith("{") and source.endswith("}"):
                    child_variables[str(child_key)] = ctx.get_var(source[1:-1])
                else:
                    child_variables[str(child_key)] = self._resolve(ctx, source)

        for secret_name in child.secret_inputs:
            ctx.secret_variables.add(secret_name)
            secret_value = child_variables.get(secret_name)
            if secret_value is not None:
                ctx.secret_values.add(str(secret_value))

        call_path = [*ctx.app_stack, app_id]
        await ctx.emit_log("info", f"Calling app {app_id}", node.id,
                           {"event": "child_app_started", "app_id": app_id, "app_path": call_path})
        ctx.variables = child_variables
        ctx.app_depth += 1
        ctx.app_stack = call_path
        try:
            child_result = await self.execute_graph(child, ctx)
        finally:
            child_outputs = ctx.variables
            ctx.variables = parent_variables
            ctx.app_depth -= 1
            ctx.app_stack = call_path[:-1]

        output_mapping = node.config.get("output_mapping", {})
        outputs: dict[str, Any] = {}
        if isinstance(output_mapping, dict):
            for parent_key, child_key in output_mapping.items():
                key = str(child_key)
                if key in child_outputs:
                    outputs[str(parent_key)] = child_outputs[key]
                    if key in ctx.secret_variables:
                        ctx.secret_variables.add(str(parent_key))
                        if child_outputs[key] is not None:
                            ctx.secret_values.add(str(child_outputs[key]))
        await ctx.emit_log("info", f"Returned from app {app_id}", node.id,
                           {"event": "child_app_succeeded", "app_id": app_id, "app_path": call_path,
                            "child_steps": child_result.get("steps", 0)})
        return NodeExecutionResult(status="ok", outputs=outputs)

    async def _h_new_tab(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        page = await ctx.browser_context.new_page()
        ctx.active_page = page
        ctx.active_frame = None
        return NodeExecutionResult(status="ok")

    async def _h_open_url(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        url = str(self._resolve(ctx, node.config.get("url", "")))
        if not url:
            raise ValueError("open_url requires config.url")
        url = url.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", url):
            url = f"https://{url}"
        wait_for = str(
            node.config.get("wait_for_navigation", node.config.get("wait_until", "domcontentloaded"))
        ).strip().lower()
        wait_until_map = {
            "load": "load",
            "domcontentloaded": "domcontentloaded",
            "networkidle": "networkidle",
            "networkidle0": "networkidle",
            "networkidle2": "networkidle",
        }
        wait_until = wait_until_map.get(wait_for, "domcontentloaded")
        nav_timeout_seconds = float(node.config.get("navigation_timeout_seconds", 90))
        nav_timeout_ms = int(max(1, nav_timeout_seconds) * 1000)
        await ctx.active_page.goto(url, wait_until=wait_until, timeout=nav_timeout_ms)

        wait_time_ms_raw = node.config.get("wait_time_ms")
        if wait_time_ms_raw is None:
            settle_seconds = float(node.config.get("settle_seconds", 0))
            wait_time_ms = max(0, int(settle_seconds * 1000))
        else:
            wait_time_ms = max(0, int(float(self._resolve(ctx, wait_time_ms_raw))))
        if wait_time_ms:
            await asyncio.sleep(wait_time_ms / 1000)
        return NodeExecutionResult(status="ok", outputs={"url": ctx.active_page.url})

    async def _h_activate_tab(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        pages = ctx.browser_context.pages
        index = node.config.get("index")
        title_contains = str(self._resolve(ctx, node.config.get("title_contains", ""))).strip()
        url_contains = str(self._resolve(ctx, node.config.get("url_contains", ""))).strip()
        if index is not None:
            idx = int(index)
            if idx < 0 or idx >= len(pages):
                raise ValueError(f"Tab index out of range: {idx}")
            ctx.active_page = pages[idx]
            ctx.active_frame = None
            return NodeExecutionResult(status="ok")
        for page in pages:
            if url_contains and url_contains in page.url:
                ctx.active_page = page
                ctx.active_frame = None
                return NodeExecutionResult(status="ok")
            if title_contains:
                title = await page.title()
                if title_contains in title:
                    ctx.active_page = page
                    ctx.active_frame = None
                    return NodeExecutionResult(status="ok")
        raise ValueError("No tab matched")

    async def _h_close_tab(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        if len(ctx.browser_context.pages) <= 1:
            return NodeExecutionResult(status="ok", capability_flags=["close_tab_ignored_single_tab"])
        await ctx.active_page.close()
        ctx.active_page = ctx.browser_context.pages[0]
        ctx.active_frame = None
        return NodeExecutionResult(status="ok")

    async def _h_reload_tab(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        await ctx.active_page.reload(wait_until="domcontentloaded")
        return NodeExecutionResult(status="ok")

    async def _h_click(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        button = str(node.config.get("button", "left")).strip().lower()
        if button == "center":
            button = "middle"
        if button not in {"left", "right", "middle"}:
            button = "left"
        click_count = max(1, int(self._resolve(ctx, node.config.get("click_count", 1))))
        timeout = int(float(node.config.get("timeout", 10)) * 1000)
        if "x" in node.config and "y" in node.config:
            x = float(self._resolve(ctx, node.config["x"]))
            y = float(self._resolve(ctx, node.config["y"]))
            await ctx.active_page.mouse.click(
                x, y, button=button, click_count=click_count
            )
            return NodeExecutionResult(status="ok")
        locator = await self._expect_locator(ctx, node)
        await locator.first.click(
            timeout=timeout,
            force=self._bool(node.config.get("force", False)),
            button=button,
            click_count=click_count,
        )
        return NodeExecutionResult(status="ok")

    async def _h_mouse_movement(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        x = float(self._resolve(ctx, node.config.get("x", 0)))
        y = float(self._resolve(ctx, node.config.get("y", 0)))
        steps = int(node.config.get("steps", 25))
        await ctx.active_page.mouse.move(x, y, steps=steps)
        return NodeExecutionResult(status="ok")

    async def _h_scroll(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        delta_x = float(self._resolve(ctx, node.config.get("delta_x", 0)))
        delta_y = float(self._resolve(ctx, node.config.get("delta_y", 800)))
        await ctx.active_page.mouse.wheel(delta_x, delta_y)
        return NodeExecutionResult(status="ok")

    async def _h_press_key(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        key = str(self._resolve(ctx, node.config.get("key", "")))
        if not key:
            raise ValueError("press_key requires config.key")
        await ctx.active_page.keyboard.press(key)
        return NodeExecutionResult(status="ok")

    async def _h_type_text(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        secret_file = str(self._resolve(ctx, node.config.get("text_file_path", ""))).strip()
        if secret_file:
            # Read one credential line only at the point of use. Do not put the
            # file contents in workflow variables or node outputs, which are
            # retained in execution records.
            line_index = int(self._resolve(ctx, node.config.get("text_file_line_index", 0)))
            lines = Path(secret_file).read_text(encoding="utf-8-sig").splitlines()
            if line_index < 0 or line_index >= len(lines):
                raise IndexError("Type Text credential line index is outside the file")
            text = lines[line_index].strip()
            if not text:
                raise ValueError("Type Text credential file line is empty")
        else:
            text = str(self._resolve(ctx, node.config.get("text", "")))
        selector = str(node.config.get("selector", "")).strip()
        timeout = int(float(node.config.get("timeout", 10)) * 1000)
        if selector:
            locator = await self._expect_locator(ctx, node)
            if self._bool(node.config.get("fill", True)):
                await locator.first.fill(text, timeout=timeout)
            else:
                await locator.first.type(
                    text,
                    delay=float(node.config.get("delay_ms", 25)),
                    timeout=timeout,
                )
        else:
            await ctx.active_page.keyboard.type(text, delay=float(node.config.get("delay_ms", 25)))
        return NodeExecutionResult(status="ok")

    async def _h_element_exist(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        locator = await self._expect_locator(ctx, node)
        timeout = int(float(node.config.get("timeout", 5)) * 1000)
        wait_state = str(node.config.get("wait_state", "visible")).strip().lower()
        if wait_state not in {"visible", "attached", "hidden", "detached"}:
            wait_state = "visible"
        try:
            await locator.first.wait_for(timeout=timeout, state=wait_state)
            output_var = node.config.get("output_variable")
            outputs = {output_var: True} if output_var else {}
            return NodeExecutionResult(status="ok", outputs=outputs, next_label="true")
        except Exception:
            output_var = node.config.get("output_variable")
            outputs = {output_var: False} if output_var else {}
            return NodeExecutionResult(status="ok", outputs=outputs, next_label="false")

    async def _h_get_url(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        output = str(node.config.get("output_variable", "url"))
        return NodeExecutionResult(status="ok", outputs={output: ctx.active_page.url})

    async def _h_get_text(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        locator = await self._expect_locator(ctx, node)
        timeout = int(float(node.config.get("timeout", 10)) * 1000)
        text = await locator.first.text_content(timeout=timeout)
        if self._bool(node.config.get("trim_output", True)):
            text = (text or "").strip()
        output = str(node.config.get("output_variable", "text"))
        return NodeExecutionResult(status="ok", outputs={output: text or ""})

    async def _h_get_value(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        locator = await self._expect_locator(ctx, node)
        timeout = int(float(node.config.get("timeout", 10)) * 1000)
        value = await locator.first.input_value(timeout=timeout)
        if self._bool(node.config.get("trim_output", True)):
            value = value.strip()
        output = str(node.config.get("output_variable", "value"))
        return NodeExecutionResult(status="ok", outputs={output: value})

    async def _h_get_attribute(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        locator = await self._expect_locator(ctx, node)
        attr = str(node.config.get("attribute", node.config.get("attribute_name", "value")))
        value = await locator.first.get_attribute(attr)
        output = str(node.config.get("output_variable", "attribute"))
        return NodeExecutionResult(status="ok", outputs={output: value})

    async def _h_select_dropdown(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        locator = await self._expect_locator(ctx, node)
        timeout = int(float(node.config.get("timeout", 10)) * 1000)
        option_by = str(node.config.get("select_option_by", "")).strip().lower()
        if not option_by:
            if node.config.get("option_label") is not None:
                option_by = "label"
            elif node.config.get("option_index") is not None:
                option_by = "index"
            else:
                option_by = "value"

        if option_by == "index":
            option_index = int(self._resolve(ctx, node.config.get("option_index", 0)))
            await locator.first.select_option(index=option_index, timeout=timeout)
            return NodeExecutionResult(status="ok", outputs={"selected_option_index": option_index})
        if option_by == "label":
            option_label = self._resolve(
                ctx, node.config.get("option_label", node.config.get("option_value"))
            )
            if option_label is None or str(option_label).strip() == "":
                raise ValueError("select_dropdown requires option_label when select_option_by=label")
            label_value = str(option_label)
            await locator.first.select_option(label=label_value, timeout=timeout)
            return NodeExecutionResult(status="ok", outputs={"selected_option_label": label_value})

        option_value = self._resolve(
            ctx, node.config.get("option_value", node.config.get("option_label"))
        )
        if option_value is None or str(option_value).strip() == "":
            raise ValueError("select_dropdown requires option_value when select_option_by=value")
        value_str = str(option_value)
        await locator.first.select_option(value=value_str, timeout=timeout)
        return NodeExecutionResult(status="ok", outputs={"selected_option_value": value_str})

    async def _h_random(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        data_type = str(node.config.get("type", "text")).lower()
        output = str(node.config.get("output_variable", "random"))
        if data_type in {"number", "int"}:
            min_v = int(node.config.get("min", 0))
            max_v = int(node.config.get("max", 999999))
            value: Any = random.randint(min_v, max_v)
        elif data_type == "email":
            value = f"user{random.randint(1000, 999999)}@example.com"
        elif data_type == "password":
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            size = int(node.config.get("length", 14))
            value = "".join(random.choice(chars) for _ in range(size))
        else:
            size = int(node.config.get("length", 16))
            value = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(size))
        return NodeExecutionResult(status="ok", outputs={output: value})

    async def _h_file_upload(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        locator = await self._expect_locator(ctx, node)
        timeout = int(float(node.config.get("timeout", 30)) * 1000)
        wait_state = str(node.config.get("wait_state", "attached")).strip().lower()
        if wait_state not in {"attached", "visible"}:
            wait_state = "attached"
        await locator.first.wait_for(timeout=timeout, state=wait_state)
        file_type = str(node.config.get("file_type", "file")).lower()
        raw_path = self._resolve(ctx, node.config.get("file_path", ""))
        output = str(node.config.get("output_variable", "uploaded_file"))
        default_name = "image.png" if file_type in {"url image", "url_image", "url"} else "upload.bin"
        filename = str(node.config.get("filename", default_name))
        if file_type == "file":
            path = Path(str(raw_path))
            if not path.exists():
                raise FileNotFoundError(str(path))
            await locator.first.set_input_files(str(path))
            return NodeExecutionResult(status="ok", outputs={output: str(path)})
        if file_type == "base64":
            payload = str(raw_path)
            if "," in payload:
                payload = payload.split(",", 1)[1]
            content = base64.b64decode(payload)
            await locator.first.set_input_files(
                [{"name": filename, "mimeType": "application/octet-stream", "buffer": content}]
            )
            return NodeExecutionResult(status="ok", outputs={output: filename})
        if file_type in {"url image", "url_image", "url"}:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(str(raw_path))
                resp.raise_for_status()
                content = resp.content
            await locator.first.set_input_files(
                [{"name": filename or "image.png", "mimeType": "image/png", "buffer": content}]
            )
            return NodeExecutionResult(status="ok", outputs={output: filename or "image.png"})
        raise ValueError(f"Unsupported file_type: {file_type}")

    async def _h_http(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        method = str(node.config.get("method", "GET")).upper()
        url = str(self._resolve(ctx, node.config.get("url", "")))
        if not url:
            raise ValueError("HTTP node requires url")
        headers = self._resolve(ctx, node.config.get("headers", {}))
        params = self._resolve(ctx, node.config.get("params", {}))
        body = self._resolve(ctx, node.config.get("body", None))
        response_type = str(node.config.get("response_type", "json")).lower()
        output = str(node.config.get("output_variable", "http_response"))
        timeout = float(node.config.get("request_timeout", 45))
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=body if isinstance(body, dict) else None,
                content=body if isinstance(body, str) else None,
            )
            if response_type == "raw":
                data: Any = resp.text
            else:
                try:
                    data = resp.json()
                except Exception:
                    data = {"raw": resp.text}
            return NodeExecutionResult(
                status="ok",
                outputs={
                    output: data,
                    f"{output}_status": resp.status_code,
                    f"{output}_headers": dict(resp.headers),
                },
            )

    async def _h_read_file_variable(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        input_type = str(node.config.get("input_type", "file")).lower()
        mode = str(node.config.get("mode", "line_by_line")).lower()
        output = str(node.config.get("output_variable", "data"))
        delimiter = str(node.config.get("delimiter", ","))

        if input_type == "variable":
            variable_name = str(node.config.get("variable", ""))
            value = str(ctx.get_var(variable_name, ""))
            if mode == "line_by_line":
                data: Any = [line for line in value.splitlines() if line]
            elif mode == "line_by_line_with_delimiter":
                data = [part for line in value.splitlines() for part in line.split(delimiter)]
            else:
                data = value
            return NodeExecutionResult(status="ok", outputs={output: data})

        file_path = Path(str(self._resolve(ctx, node.config.get("file_path", ""))))
        if not file_path.exists():
            raise FileNotFoundError(str(file_path))
        content = file_path.read_text(encoding="utf-8")
        if mode == "line_by_line":
            data = [line for line in content.splitlines() if line]
        elif mode == "line_by_line_with_delimiter":
            data = [part for line in content.splitlines() for part in line.split(delimiter)]
        else:
            data = content
        return NodeExecutionResult(status="ok", outputs={output: data})

    async def _h_write_file(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        file_path = Path(str(self._resolve(ctx, node.config.get("file_path", ""))))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._resolve(
            ctx, node.config.get("data", ctx.get_var(node.config.get("input_variable", ""), ""))
        )
        mode = str(node.config.get("mode", "append")).lower()
        write_mode = "a" if mode == "append" else "w"
        format_type = str(node.config.get("format", "txt")).lower()
        if format_type == "json":
            with file_path.open(write_mode, encoding="utf-8") as fh:
                fh.write(json.dumps(data, ensure_ascii=False) + ("\n" if write_mode == "a" else ""))
        elif format_type == "csv":
            with file_path.open(write_mode, encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter=str(node.config.get("delimiter", ",")))
                if isinstance(data, list):
                    if data and isinstance(data[0], list):
                        writer.writerows(data)
                    else:
                        writer.writerow(data)
                elif isinstance(data, dict):
                    writer.writerow(list(data.values()))
                else:
                    writer.writerow([data])
        else:
            with file_path.open(write_mode, encoding="utf-8") as fh:
                fh.write(str(data))
                if write_mode == "a":
                    fh.write("\n")
        return NodeExecutionResult(status="ok", outputs={"written_file": str(file_path)})

    async def _h_cookies(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        action = str(node.config.get("action", "export")).lower()
        file_path = Path(str(self._resolve(ctx, node.config.get("file_path", "cookies.json"))))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if action == "export":
            cookies = await ctx.browser_context.cookies()
            file_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
            return NodeExecutionResult(
                status="ok",
                outputs={"cookies_path": str(file_path), "cookies_count": len(cookies)},
            )
        if action == "import":
            data = json.loads(file_path.read_text(encoding="utf-8"))
            await ctx.browser_context.add_cookies(data)
            return NodeExecutionResult(status="ok", outputs={"cookies_count": len(data)})
        raise ValueError(f"Unsupported cookies action: {action}")

    async def _h_save_asset(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        output_dir = Path(str(self._resolve(ctx, node.config.get("output_path", "artifacts"))))
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = str(self._resolve(ctx, node.config.get("filename", ""))).strip()
        source_mode = str(node.config.get("save_asset_by", "url")).lower()
        if source_mode == "selector":
            locator = await self._expect_locator(ctx, node)
            url = await locator.first.get_attribute("src")
        else:
            url = str(
                self._resolve(ctx, node.config.get("url", node.config.get("asset_url", "")))
            )
        if not url:
            raise ValueError("No asset url resolved")
        if not filename:
            filename = os.path.basename(url.split("?", 1)[0]) or f"asset_{int(time.time())}"
        path = output_dir / filename
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            path.write_bytes(resp.content)
        output_var = str(node.config.get("output_variable", "asset_path"))
        return NodeExecutionResult(status="ok", outputs={output_var: str(path)})

    async def _h_spreadsheet(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        path = Path(str(self._resolve(ctx, node.config.get("file_path", ""))))
        operation = str(node.config.get("operation", "read")).lower()
        output = str(node.config.get("output_variable", "sheet_data"))
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".csv":
            if operation == "read":
                if not path.exists():
                    return NodeExecutionResult(status="ok", outputs={output: []})
                with path.open("r", encoding="utf-8", newline="") as fh:
                    rows = list(csv.reader(fh))
                return NodeExecutionResult(status="ok", outputs={output: rows})
            data = self._resolve(
                ctx, node.config.get("data", ctx.get_var(node.config.get("input_variable", ""), []))
            )
            with path.open(
                "a" if self._bool(node.config.get("append", True)) else "w",
                encoding="utf-8",
                newline="",
            ) as fh:
                writer = csv.writer(fh)
                if isinstance(data, list) and data and isinstance(data[0], list):
                    writer.writerows(data)
                elif isinstance(data, list):
                    writer.writerow(data)
                elif isinstance(data, dict):
                    writer.writerow(list(data.values()))
                else:
                    writer.writerow([data])
            return NodeExecutionResult(status="ok", outputs={"sheet_path": str(path)})
        return await self._not_implemented(ctx, node, "spreadsheet_xlsx_requires_adapter")

    async def _h_open_ai(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        api_key = str(self._resolve(ctx, node.config.get("api_key", settings.openai_api_key)))
        if not api_key:
            raise ValueError("OpenAI API key missing for Open AI node")
        output_type = str(node.config.get("output_type", "text")).lower()
        model = str(node.config.get("model", settings.openai_model))
        output = str(node.config.get("output_variable", "openai_output"))
        prompt = str(self._resolve(ctx, node.config.get("content", node.config.get("prompt", ""))))
        if not prompt:
            raise ValueError("Open AI node requires content/prompt")
        base_url = str(node.config.get("base_url", settings.openai_base_url)).rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=float(node.config.get("request_timeout", 60))) as client:
            if output_type == "image":
                resp = await client.post(
                    f"{base_url}/images/generations",
                    headers=headers,
                    json={
                        "model": model,
                        "prompt": prompt,
                        "size": node.config.get("size", "1024x1024"),
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                image_url = payload["data"][0].get("url") or payload["data"][0].get("b64_json")
                return NodeExecutionResult(
                    status="ok",
                    outputs={output: image_url, f"{output}_raw": payload},
                )
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": float(node.config.get("temperature", 0.2)),
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            text = payload["choices"][0]["message"]["content"]
            return NodeExecutionResult(status="ok", outputs={output: text, f"{output}_raw": payload})

    async def _h_case_path(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        expr = str(node.config.get("expression", "")).strip()
        value = self._resolve(ctx, node.config.get("value", ""))
        if expr:
            value = self._eval_expr(ctx, expr)
        cases = node.config.get("cases", {})
        default_label = str(node.config.get("default_label", "next"))
        if isinstance(cases, dict):
            for label, expected in cases.items():
                exp_resolved = self._resolve(ctx, expected)
                if str(value) == str(exp_resolved):
                    return NodeExecutionResult(
                        status="ok",
                        outputs={"case_value": value},
                        next_label=label,
                    )
        return NodeExecutionResult(status="ok", outputs={"case_value": value}, next_label=default_label)

    async def _h_insert_data(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        row = self._resolve(ctx, node.config.get("row", {}))
        await ctx.emit_log("info", "Insert Data row captured", node.id, {"row": row})
        output = str(node.config.get("output_variable", "insert_data"))
        return NodeExecutionResult(status="ok", outputs={output: row})

    async def _h_regexp_extraction(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        input_value = str(self._resolve(ctx, node.config.get("input_value", "")))
        expr = str(self._resolve(ctx, node.config.get("expression", "")))
        flags = 0
        if self._bool(node.config.get("case_insensitive", False)):
            flags |= re.IGNORECASE
        if self._bool(node.config.get("multiline", False)):
            flags |= re.MULTILINE
        pattern = re.compile(expr, flags)
        if self._bool(node.config.get("global", True)):
            matches: Any = pattern.findall(input_value)
        else:
            m = pattern.search(input_value)
            matches = m.group(0) if m else ""
        output = str(node.config.get("output_variable", "regex_output"))
        return NodeExecutionResult(status="ok", outputs={output: matches})

    async def _h_imap_read_mail(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        config = self._resolve(ctx, node.config)
        service = str(config.get("email_service", "gmail")).lower()
        providers = {
            "gmail": ("imap.gmail.com", 993),
            "yahoo": ("imap.mail.yahoo.com", 993),
            "hotmail": ("outlook.office365.com", 993),
            "outlook": ("outlook.office365.com", 993),
        }
        host, port = providers.get(service, (config.get("host"), int(config.get("port", 993))))
        user = str(config.get("email") or config.get("user") or "")
        password = str(config.get("password") or config.get("pass") or "")
        if not host or not user or not password:
            raise ValueError("IMAP requires host/user/password")
        unseen_only = self._bool(config.get("unseen_only", False))
        mark_read = self._bool(config.get("mark_mail_as_read", False))
        latest_only = self._bool(config.get("get_latest_mail", True))
        mailbox = str(config.get("mailbox", "INBOX"))
        regex_expr = str(config.get("content_mail_contains", config.get("regex", ""))).strip()
        output = str(config.get("output_variable", "imap_result"))

        def _read_mail() -> dict[str, Any]:
            mail = imaplib.IMAP4_SSL(host, int(port))
            try:
                mail.login(user, password)
                mail.select(mailbox)
                criteria = "(UNSEEN)" if unseen_only else "ALL"
                _, data = mail.search(None, criteria)
                ids = data[0].split()
                if not ids:
                    return {"messages": [], "count": 0}
                if latest_only:
                    ids = [ids[-1]]
                messages: list[dict[str, Any]] = []
                for msg_id in ids:
                    _, payload = mail.fetch(msg_id, "(RFC822)")
                    msg = message_from_bytes(payload[0][1])
                    subject = msg.get("Subject", "")
                    sender = msg.get("From", "")
                    receiver = msg.get("To", "")
                    date = msg.get("Date", "")
                    body_text = ""
                    body_html = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            disp = str(part.get("Content-Disposition", ""))
                            if "attachment" in disp:
                                continue
                            payload_bytes = part.get_payload(decode=True) or b""
                            charset = part.get_content_charset() or "utf-8"
                            decoded = payload_bytes.decode(charset, errors="ignore")
                            if ctype == "text/plain":
                                body_text += decoded
                            elif ctype == "text/html":
                                body_html += decoded
                    else:
                        payload_bytes = msg.get_payload(decode=True) or b""
                        charset = msg.get_content_charset() or "utf-8"
                        decoded = payload_bytes.decode(charset, errors="ignore")
                        if msg.get_content_type() == "text/html":
                            body_html = decoded
                        else:
                            body_text = decoded
                    blob = "\n".join([subject, body_text, body_html])
                    regex_matches: list[str] = []
                    otp_guess = ""
                    if regex_expr:
                        regex_matches = re.findall(regex_expr, blob, flags=re.MULTILINE)
                        if regex_matches:
                            otp_guess = str(regex_matches[0])
                    else:
                        otp = re.search(r"\b(\d{4,8})\b", blob)
                        otp_guess = otp.group(1) if otp else ""
                    messages.append(
                        {
                            "subject": subject,
                            "from": sender,
                            "to": receiver,
                            "date": date,
                            "body_text": body_text,
                            "body_html": body_html,
                            "regex_matches": regex_matches,
                            "otp_guess": otp_guess,
                            "message_id": msg_id.decode(),
                        }
                    )
                    if mark_read:
                        mail.store(msg_id, "+FLAGS", "\\Seen")
                return {"messages": messages, "count": len(messages)}
            finally:
                try:
                    mail.logout()
                except Exception:
                    pass

        result = await asyncio.to_thread(_read_mail)
        return NodeExecutionResult(status="ok", outputs={output: result})

    async def _h_update_field(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        field = str(self._resolve(ctx, node.config.get("field", ""))).strip()
        if not field:
            raise ValueError("update_field requires field")
        value = str(self._resolve(ctx, node.config.get("value", "")))
        if ctx.profile_field_set is None:
            return await self._not_implemented(ctx, node, "profile_field_set_not_available")
        await ctx.profile_field_set(ctx.profile_id, field, value)
        return NodeExecutionResult(status="ok", outputs={field: value})

    async def _h_two_fa(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        secret = str(self._resolve(ctx, node.config.get("secret", ""))).replace(" ", "")
        if not secret:
            raise ValueError("Two FA requires secret")
        try:
            import pyotp  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("pyotp dependency missing") from exc
        code = pyotp.TOTP(secret).now()
        output = str(node.config.get("output_variable", "two_fa_code"))
        return NodeExecutionResult(status="ok", outputs={output: code})

    async def _h_bypass(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        timeout = float(node.config.get("timeout", 10))
        deadline = time.time() + timeout
        bypassed = False
        while time.time() < deadline:
            title = (await ctx.active_page.title()).lower()
            html = (await ctx.active_page.content()).lower()
            if "cloudflare" in title or "captcha" in html or "challenge" in html:
                await asyncio.sleep(1.0)
            else:
                bypassed = True
                break
        return NodeExecutionResult(status="ok", outputs={"bypassed": bypassed})

    async def _h_cmd(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        command = str(self._resolve(ctx, node.config.get("command", "")))
        if not command:
            raise ValueError("Cmd node requires command")
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timeout = float(node.config.get("timeout", 60))
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"Command timeout after {timeout}s")
        out = stdout.decode(errors="ignore")
        err = stderr.decode(errors="ignore")
        output = str(node.config.get("output_variable", "cmd_output"))
        return NodeExecutionResult(
            status="ok",
            outputs={
                output: out,
                f"{output}_stderr": err,
                f"{output}_code": proc.returncode,
            },
        )

    async def _h_artemis(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        """Provision ARTEMIS Accessibility Helper and attach it to one ADB phone."""
        serial = await self._resolve_phone_serial(ctx, node, default_variable="remote_phone_verified")
        # Starting the persistent worker already connects ARTEMIS and returns
        # screen dimensions plus hierarchy count. Avoid sending a full PNG
        # screenshot through the JSON-lines pipe just to establish a session.
        result = await ctx.phone_workers.connect(serial)
        output = str(node.config.get("output_variable", "artemis_phone"))
        connection = {
            "status": "connected", "serial": serial,
            "backend": result.get("backend", "ARTEMIS Accessibility Helper"),
            "width": result.get("width"), "height": result.get("height"),
            "hierarchy_nodes": result.get("element_count", len(result.get("elements", []))),
        }
        await self._remember_phone_connection(ctx, serial, connection)
        return NodeExecutionResult(status="ok", outputs={output: connection})

    @staticmethod
    def _serial_from_phone_value(value: Any) -> str:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value.strip()
        if isinstance(value, dict):
            return str(value.get("adbSerial") or value.get("serial") or value.get("device_id") or "").strip()
        return ""

    async def _remember_phone_connection(
        self, ctx: NodeExecutionContext, serial: str, details: dict[str, Any] | None = None
    ) -> None:
        connection = {
            "status": "connected", "serial": serial, "adbSerial": serial,
            "profile_id": ctx.profile_id, "saved_at": time.time(),
        }
        for key in ("backend", "width", "height"):
            if details and details.get(key) is not None:
                connection[key] = details[key]
        ctx.set_var("phone_connection", connection)
        ctx.set_var("phone_serial", serial)
        if not ctx.get_var("artemis_phone"):
            ctx.set_var("artemis_phone", connection)
        if ctx.profile_field_set is not None:
            await ctx.profile_field_set(
                ctx.profile_id, "__artemis_phone_connection", json.dumps(connection),
            )

    async def _resolve_phone_serial(
        self, ctx: NodeExecutionContext, node: Node, *, default_variable: str = "artemis_phone"
    ) -> str:
        """Resolve a phone for this profile without trusting stale run variables."""
        if ctx.phone_workers is None:
            raise RuntimeError("ARTEMIS phone worker service is unavailable.")
        online_devices = [
            device for device in await ctx.phone_workers.list_devices()
            if device.get("state") == "device"
        ]
        online = {device["serial"] for device in online_devices}
        explicit = self._serial_from_phone_value(self._resolve(ctx, node.config.get("serial", "")))
        if explicit:
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", explicit) or explicit not in online:
                raise ValueError(f"Configured ADB serial {explicit} is not online; reconnect that phone.")
            return explicit

        variable_name = str(node.config.get("serial_variable") or default_variable).strip()
        candidates = []
        if variable_name == "artemis_phone" and ctx.get_var("remote_phone_verified"):
            # A Cmd/Javascript verification in this run supersedes a phone
            # restored from the previous run of this profile.
            candidates.append(("remote_phone_verified", ctx.get_var("remote_phone_verified")))
        candidates.extend([
            (variable_name, ctx.get_var(variable_name)),
            ("artemis_phone", ctx.get_var("artemis_phone")),
            ("remote_phone_verified", ctx.get_var("remote_phone_verified")),
            ("phone_connection", ctx.get_var("phone_connection")),
            ("phone_serial", ctx.get_var("phone_serial")),
        ])
        cached = None
        if ctx.profile_field_get is not None:
            raw = await ctx.profile_field_get(ctx.profile_id, "__artemis_phone_connection")
            if raw:
                try:
                    cached = json.loads(raw)
                except json.JSONDecodeError:
                    pass
        if isinstance(cached, dict) and cached.get("profile_id") == ctx.profile_id:
            try:
                saved_at = float(cached.get("saved_at") or 0)
            except (TypeError, ValueError):
                saved_at = 0
            if 0 <= time.time() - saved_at <= 2 * 60 * 60:
                candidates.append(("saved phone connection", cached))
        for source, value in candidates:
            serial = self._serial_from_phone_value(value)
            if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", serial) and serial in online:
                if source == "saved phone connection":
                    await ctx.emit_log("info", f"Reusing online phone {serial} saved for profile {ctx.profile_id}.", node.id)
                await self._remember_phone_connection(ctx, serial, cached if source == "saved phone connection" else None)
                return serial

        rtl_pages = [page for page in ctx.browser_context.pages if (
            not page.is_closed() and "developer.samsung.com/remotetestlab/webclient" in page.url
        )]
        if len(rtl_pages) == 1 and len(online) == 1:
            body = await rtl_pages[0].locator("body").inner_text(timeout=5000)
            if "All ongoing tests have ended" in body:
                raise ValueError("RTL phone session has ended; reconnect the phone before testing this node.")
            model_match = re.search(r"\bmodel:(\S+)", online_devices[0].get("details", ""))
            if model_match:
                model = re.sub(r"[^a-z0-9]", "", model_match.group(1).lower())
                visible = re.sub(r"[^a-z0-9]", "", body.lower())
                if model not in visible:
                    raise ValueError("The only ADB phone model does not match the RTL tab in this profile.")
            serial = next(iter(online))
            await ctx.emit_log("info", f"Found the only online ADB phone {serial} in this RTL profile.", node.id)
            await self._remember_phone_connection(ctx, serial)
            return serial
        raise ValueError(
            "No verified ADB phone for this profile. Run ARTEMIS Connect first, "
            "or set serial explicitly; auto-detection requires exactly one online phone and an RTL tab."
        )

    async def _h_artemis_install_apks(
        self, ctx: NodeExecutionContext, node: Node
    ) -> NodeExecutionResult:
        """Install the ordered APK list on the current phone and verify each package."""
        config = self._resolve(ctx, dict(node.config))
        serial = await self._resolve_phone_serial(ctx, node)
        files = config.get("apk_files")
        if not isinstance(files, list) or not 1 <= len(files) <= 50:
            raise ValueError("Choose between 1 and 50 APK files in install order.")
        install_timeout = max(10, min(float(config.get("install_timeout_seconds", 180)), 900))
        method = str(config.get("install_method") or "rtl_applications")
        if method not in {"rtl_applications", "adb"}:
            raise ValueError("Install method must be rtl_applications or adb.")
        results: list[dict[str, Any]] = []
        for index, item in enumerate(files, 1):
            if await self._stop_requested(ctx):
                raise RunStopRequested
            if not isinstance(item, dict):
                raise ValueError(f"APK entry {index} is invalid.")
            asset_id = str(item.get("asset_id", "")).strip()
            path = apk_asset_path(asset_id)
            name = str(item.get("name") or path.name)
            try:
                installed = (
                    await self._install_apk_via_rtl(ctx, serial, path, install_timeout)
                    if method == "rtl_applications"
                    else await install_apk(serial, path, install_timeout)
                )
                result = {"index": index, "name": name, **installed}
                await ctx.emit_log("info", f"APK {index}/{len(files)} verified: {name} ({installed['package']}, version {installed['version_code']}, {installed['status']})", node.id)
            except RunStopRequested:
                raise
            except Exception as exc:  # Continue so every selected APK gets a result.
                result = {"index": index, "name": name, "status": "failed", "error": str(exc)}
                await ctx.emit_log("error", f"APK {index}/{len(files)} failed: {name}: {exc}", node.id)
            results.append(result)
        output = str(config.get("output_variable") or "phone_apk_install_results")
        success_count = sum(item["status"] in {"installed", "already_present"} for item in results)
        outputs = {
            output: results,
            f"{output}_success_count": success_count,
            f"{output}_failure_count": len(results) - success_count,
        }
        if success_count != len(results):
            return NodeExecutionResult(
                status="failed", outputs=outputs, next_label="error",
                error=f"Installed {success_count}/{len(results)} APKs; see {output} for each result.",
            )
        return NodeExecutionResult(status="ok", outputs=outputs)

    async def _install_apk_via_rtl(
        self, ctx: NodeExecutionContext, serial: str, path: Path, timeout: float
    ) -> dict[str, str]:
        """Use the RTL Applications file chooser, then confirm on the ADB device."""
        validate_apk(path)
        package, expected_version = await apk_identity(path)
        pages = [
            page for page in ctx.browser_context.pages
            if not page.is_closed() and "developer.samsung.com/remotetestlab/webclient" in page.url
        ]
        if len(pages) != 1:
            raise RuntimeError("Open exactly one RTL Web Client tab in the selected browser profile.")
        page = pages[0]
        if await page.get_by_text("All ongoing tests have ended.").count():
            raise RuntimeError("RTL Web Client reports that the phone session has ended.")
        model = await device_model(serial)
        if model.casefold() not in (await page.locator("body").inner_text(timeout=15000)).casefold():
            raise RuntimeError(f"RTL Web Client does not show ADB device model {model}; refusing to install on an unverified phone.")
        previous_version = await device_version(serial, package)
        await page.get_by_text("Applications", exact=True).first.click(timeout=15000)
        button = page.get_by_text("Install App", exact=True).first
        async with page.expect_file_chooser(timeout=15000) as chooser_info:
            await button.click(timeout=15000)
        chooser = await chooser_info.value
        await chooser.set_files(str(path))
        deadline = time.monotonic() + timeout
        installed_version = None
        while time.monotonic() < deadline:
            if await self._stop_requested(ctx):
                raise RunStopRequested
            installed_version = await device_version(serial, package)
            if installed_version == expected_version:
                break
            await asyncio.sleep(2)
        if installed_version != expected_version:
            raise RuntimeError(
                f"RTL upload finished, but {package} version is "
                f"{installed_version or 'not found'} (expected {expected_version})"
            )
        return {
            "package": package,
            "version_code": installed_version,
            "previous_version_code": previous_version or "",
            "status": "already_present" if previous_version == expected_version else "installed",
            "method": "rtl_applications",
        }

    async def _h_artemis_phone_action(
        self, ctx: NodeExecutionContext, node: Node
    ) -> NodeExecutionResult:
        """Run a deterministic phone action through ARTEMIS's helper/ADB bridge."""
        operations = {
            "artemis_open_app": "open_app",
            "artemis_stop_app": "stop_app",
            "artemis_get_ui": "get_ui",
            "artemis_find_element": "find_element",
            "artemis_wait_element": "wait_element",
            "artemis_read_text": "read_text",
            "artemis_tap": "tap",
            "artemis_long_press": "long_press",
            "artemis_double_tap": "double_tap",
            "artemis_swipe": "swipe",
            "artemis_type_text": "send_text",
            "artemis_clear_text": "clear_text",
            "artemis_set_clipboard": "set_clipboard",
            "artemis_key_event": "press_key",
            "artemis_screenshot": "screenshot",
            "artemis_find_image": "wait_image",
            "artemis_tap_image": "tap_image",
        }
        node_key = self._normalise_type(node.type)
        operation = operations.get(node_key)
        if not operation:
            raise ValueError(f"Unsupported ARTEMIS phone node: {node.type}")

        config = self._resolve(ctx, dict(node.config))
        serial = await self._resolve_phone_serial(ctx, node)
        for field_name in ("text_variable",):
            variable_name = str(node.config.get(field_name, "")).strip()
            config[field_name] = variable_name
            if variable_name:
                value = ctx.get_var(variable_name)
                if value is None:
                    raise ValueError(f"ARTEMIS phone node could not find variable '{variable_name}'.")
                config["value"] = value
        if operation == "send_text":
            config["value"] = config.get("value", config.get("text", ""))
        elif operation == "set_clipboard":
            config["value"] = config.get("value", config.get("text", ""))
        elif operation == "press_key":
            config["key"] = config.get("key", "BACK")
        asset_id = str(config.get("image_asset_id", "")).strip()
        if asset_id:
            if not asset_id or ctx.image_asset_get is None:
                raise ValueError("Choose a saved phone image asset for this node.")
            asset = await ctx.image_asset_get(asset_id)
            if not asset:
                raise ValueError(f"Phone image asset not found: {asset_id}")
            config["template_base64"] = base64.b64encode(bytes(asset["data"])).decode("ascii")
            config["template_sha256"] = asset["sha256"]
        try:
            result = await ctx.phone_workers.request(serial, operation, config)
        except RuntimeError:
            if operation not in {"tap", "long_press", "double_tap"} or not config.get("template_base64") or str(config.get("target_mode")) != "element":
                raise
            located = await ctx.phone_workers.request(serial, "find_image", config)
            if not located.get("found") or located.get("ambiguous"):
                raise
            point = located.get("center", {})
            fallback_config = {**config, "target_mode": "coordinates", "x": point.get("x"), "y": point.get("y")}
            result = await ctx.phone_workers.request(serial, operation, fallback_config)
            result["selector_fallback"] = "image"
            result["image_score"] = located.get("score")
        if operation == "screenshot":
            output_path = Path(str(config.get("output_path", "./artifacts/phone_screenshot.png"))).expanduser()
            if not output_path.is_absolute():
                output_path = Path(__file__).resolve().parents[1] / output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(base64.b64decode(result["image_base64"]))
            result = {"path": str(output_path.resolve()), "width": result.get("width"), "height": result.get("height")}
        output = str(config.get("output_variable", "phone_action"))
        next_label = "next"
        if operation == "wait_image":
            next_label = "true" if result.get("found") and not result.get("ambiguous") else "false"
        elif operation == "wait_element" and not result.get("found"):
            next_label = "fallback"
        return NodeExecutionResult(status="ok", outputs={output: result}, next_label=next_label)

    async def _h_artemis_analyze_error(
        self, ctx: NodeExecutionContext, node: Node
    ) -> NodeExecutionResult:
        """Explain the latest failed node and optionally offer a bounded safe retry branch."""
        failure = ctx.last_node_error
        output_name = str(node.config.get("output_variable") or "node_error_analysis").strip()
        output_name = output_name or "node_error_analysis"
        if not failure:
            analysis: dict[str, Any] = {
                "status": "no_failure_context",
                "category": "no_failure_context",
                "summary": "Chưa có node lỗi trước đó trong lượt chạy này để phân tích.",
                "recommended_fix": "Nối cổng error của node cần theo dõi vào ARTEMIS Analyze Error.",
                "safe_to_retry": False,
                "retry_recommended": False,
                "retry_reason": "Node phân tích cần nhận lỗi qua nhánh error.",
            }
            await ctx.emit_log("warning", analysis["summary"], node.id, {"analysis": analysis})
            return NodeExecutionResult(status="ok", outputs={output_name: analysis}, next_label="false")

        diagnosis = diagnose_node_error(
            node_type=str(failure.get("node_type") or ""),
            error_type=str(failure.get("error_type") or ""),
            error=str(failure.get("error") or ""),
        )
        analysis = {
            "status": "analyzed",
            "failed_node_id": failure.get("node_id"),
            "failed_node_type": failure.get("node_type"),
            "failed_step": failure.get("step"),
            "duration_ms": failure.get("duration_ms"),
            "app_path": failure.get("app_path", []),
            "error_type": failure.get("error_type"),
            "error": failure.get("error"),
            "traceback_tail": str(failure.get("traceback") or "")[-280:],
            "page_url": failure.get("page_url"),
            "config_summary": failure.get("config_summary", {}),
            **diagnosis,
            "retry_recommended": False,
            "retry_count": 0,
            "retry_limit": 0,
        }

        if self._bool(self._resolve(ctx, node.config.get("include_phone_context", False))):
            try:
                serial = await self._resolve_phone_serial(ctx, node)
                if not ctx.phone_workers.has_live_worker(serial):
                    analysis["phone_context"] = {
                        "status": "skipped",
                        "reason": "Không có ARTEMIS worker đang hoạt động; node phân tích không tự kết nối lại phone.",
                    }
                else:
                    ui = await ctx.phone_workers.request(serial, "get_ui", {"max_nodes": 300})
                    elements = ui.get("elements") if isinstance(ui.get("elements"), list) else []
                    failed_type = self._normalise_type(str(failure.get("node_type") or ""))
                    selector_count = (
                        selector_match_count(elements, failure.get("config_summary", {}))
                        if failed_type.startswith("artemis") else None
                    )
                    analysis["phone_context"] = {
                        "status": "read",
                        "serial": serial,
                        "accessibility_node_count": ui.get("element_count", len(elements)),
                        "failed_selector_match_count": selector_count,
                    }
            except Exception as exc:  # Diagnostics must still return the original node failure.
                analysis["phone_context"] = {
                    "status": "unavailable",
                    "reason": str(ctx.redact_log_value(str(exc)))[:500],
                }

        try:
            retry_limit = max(0, min(3, int(float(self._resolve(ctx, node.config.get("max_auto_retries", 0)) or 0))))
        except (TypeError, ValueError):
            retry_limit = 0
        retry_key = f"{':'.join(ctx.app_stack)}:{failure.get('node_id', '')}"
        retries = ctx.loop_state.setdefault("_analyze_error_retry_counts", {})
        retry_count = int(retries.get(retry_key, 0))
        analysis["retry_count"] = retry_count
        analysis["retry_limit"] = retry_limit
        retry_recommended = bool(diagnosis["safe_to_retry"] and retry_count < retry_limit)
        if retry_recommended:
            retries[retry_key] = retry_count + 1
            analysis["retry_recommended"] = True
            analysis["retry_count"] = retry_count + 1
            analysis["retry_reason"] = (
                f"Đề xuất thử lại lần {retry_count + 1}/{retry_limit}; chỉ nối cổng true về node lỗi "
                "sau khi xác nhận thao tác đó là bước chỉ đọc."
            )
        elif diagnosis["safe_to_retry"] and retry_limit == 0:
            analysis["retry_reason"] = "Lỗi có vẻ tạm thời, nhưng tự thử lại đang tắt (max_auto_retries = 0)."
        elif diagnosis["safe_to_retry"]:
            analysis["retry_reason"] = f"Đã đạt giới hạn {retry_limit} lần thử lại an toàn trong lượt chạy này."

        level = "warning" if diagnosis["category"] != "unknown" else "error"
        await ctx.emit_log(
            level,
            f"Phân tích node lỗi {failure.get('node_type')} ({diagnosis['category']}): {diagnosis['summary']}",
            node.id,
            {"analysis": analysis},
        )
        return NodeExecutionResult(
            status="ok",
            outputs={output_name: ctx.redact_log_value(analysis)},
            next_label="true" if retry_recommended else "false",
        )

    async def _h_log(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        message = str(self._resolve(ctx, node.config.get("message", node.config.get("log", ""))))
        await ctx.emit_log("info", message, node.id, {"variables": dict(ctx.variables)})
        return NodeExecutionResult(status="ok")

    async def _h_disconnect(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        if ctx.reconnect is None:
            return await self._not_implemented(ctx, node, "reconnect_not_available")
        delay = float(node.config.get("timeout_before_reconnect", 2))
        try:
            await ctx.browser.close()
        except Exception:
            pass
        await asyncio.sleep(delay)
        browser, browser_context, page = await ctx.reconnect()
        ctx.browser = browser
        ctx.browser_context = browser_context
        ctx.active_page = page
        ctx.active_frame = None
        return NodeExecutionResult(status="ok")

    async def _h_update_tag(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        if ctx.profile_tag_set is None:
            return await self._not_implemented(ctx, node, "profile_tag_set_not_available")
        tags = self._resolve(ctx, node.config.get("tags", []))
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        await ctx.profile_tag_set(ctx.profile_id, list(tags))
        return NodeExecutionResult(status="ok", outputs={"tags": list(tags)})

    async def _h_get_tag(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        if ctx.profile_tag_get is None:
            return await self._not_implemented(ctx, node, "profile_tag_get_not_available")
        tags = await ctx.profile_tag_get(ctx.profile_id)
        output = str(node.config.get("output_variable", "tags"))
        return NodeExecutionResult(status="ok", outputs={output: tags})

    async def _h_profile_note(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        if ctx.profile_field_get is None or ctx.profile_field_set is None:
            return await self._not_implemented(ctx, node, "profile_note_adapter_not_available")
        mode = str(node.config.get("mode", "get")).lower()
        output = str(node.config.get("output_variable", "profile_note"))
        if mode == "update":
            value = str(self._resolve(ctx, node.config.get("value", "")))
            await ctx.profile_field_set(ctx.profile_id, "note", value)
            return NodeExecutionResult(status="ok", outputs={output: value})
        value = await ctx.profile_field_get(ctx.profile_id, "note")
        return NodeExecutionResult(status="ok", outputs={output: value or ""})

    async def _h_image_search(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return await self._not_implemented(ctx, node, "image_search_requires_cv2_numpy")
        screenshot = await ctx.active_page.screenshot(full_page=True)
        screenshot_mat = cv2.imdecode(np.frombuffer(screenshot, np.uint8), cv2.IMREAD_COLOR)
        src = str(self._resolve(ctx, node.config.get("input_base64_image", "")))
        if not src:
            raise ValueError("Image search requires input_base64_image")
        if src.startswith("http://") or src.startswith("https://"):
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(src)
                resp.raise_for_status()
                template_bytes = resp.content
        elif Path(src).exists():
            template_bytes = Path(src).read_bytes()
        else:
            if "," in src:
                src = src.split(",", 1)[1]
            template_bytes = base64.b64decode(src)
        template = cv2.imdecode(np.frombuffer(template_bytes, np.uint8), cv2.IMREAD_COLOR)
        if template is None:
            raise ValueError("Invalid template image")
        result = cv2.matchTemplate(screenshot_mat, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        threshold = float(node.config.get("threshold", 0.8))
        found = max_val >= threshold
        outputs: dict[str, Any] = {"image_found": found, "image_score": float(max_val)}
        if found:
            h, w = template.shape[:2]
            center = {"x": int(max_loc[0] + (w / 2)), "y": int(max_loc[1] + (h / 2))}
            outputs["image_bbox"] = {"x": max_loc[0], "y": max_loc[1], "w": w, "h": h}
            outputs["image_center"] = center
            if self._bool(node.config.get("click", False)):
                await ctx.active_page.mouse.click(center["x"], center["y"])
        output_var = str(node.config.get("output_variable", "image_search"))
        return NodeExecutionResult(status="ok", outputs={output_var: outputs})

    async def _h_screenshot(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        folder = Path(
            str(self._resolve(ctx, node.config.get("folder_output", "artifacts/screenshots")))
        )
        folder.mkdir(parents=True, exist_ok=True)
        name = str(self._resolve(ctx, node.config.get("file_name", f"{int(time.time())}.png")))
        path = folder / name
        await ctx.active_page.screenshot(
            path=str(path),
            full_page=self._bool(node.config.get("full_page", True)),
        )
        output = str(node.config.get("output_variable", "screenshot_path"))
        return NodeExecutionResult(status="ok", outputs={output: str(path)})

    async def _h_clipboard(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        try:
            import pyperclip  # type: ignore
        except Exception:
            return await self._not_implemented(ctx, node, "clipboard_requires_pyperclip")
        action = str(node.config.get("action", "copy")).lower()
        output = str(node.config.get("output_variable", "clipboard"))
        if action == "copy":
            value = str(
                self._resolve(
                    ctx,
                    node.config.get("value", ctx.get_var(node.config.get("input_variable", ""), "")),
                )
            )
            pyperclip.copy(value)
            return NodeExecutionResult(status="ok", outputs={output: value})
        if action == "paste":
            value = pyperclip.paste()
            await ctx.active_page.keyboard.insert_text(value)
            return NodeExecutionResult(status="ok", outputs={output: value})
        value = pyperclip.paste()
        return NodeExecutionResult(status="ok", outputs={output: value})

    async def _h_switch_frame(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        frame_mode = str(node.config.get("frame", "main")).lower()
        if frame_mode in {"main", "main frame", "main_page", "mainframe"}:
            ctx.active_frame = None
            return NodeExecutionResult(status="ok")
        url_pattern = str(self._resolve(ctx, node.config.get("url_contains", ""))).strip()
        name_pattern = str(self._resolve(ctx, node.config.get("name_contains", ""))).strip()
        selector = str(node.config.get("selector", "")).strip()
        if selector:
            handle = await ctx.active_page.query_selector(selector)
            if handle:
                frame = await handle.content_frame()
                if frame:
                    ctx.active_frame = frame
                    return NodeExecutionResult(status="ok")
        for frame in ctx.active_page.frames:
            if url_pattern and url_pattern in frame.url:
                ctx.active_frame = frame
                return NodeExecutionResult(status="ok")
            if name_pattern and name_pattern in (frame.name or ""):
                ctx.active_frame = frame
                return NodeExecutionResult(status="ok")
        raise ValueError("No matching frame found")

    async def _h_switch_page(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        target = str(
            self._resolve(
                ctx, node.config.get("match_pattern_includes", node.config.get("url_contains", ""))
            )
        )
        index = int(node.config.get("matched_index", 0))
        pages = [p for p in ctx.browser_context.pages if not target or target in p.url]
        if not pages:
            raise ValueError("No matching page")
        idx = max(0, min(index, len(pages) - 1))
        ctx.active_page = pages[idx]
        ctx.active_frame = None
        return NodeExecutionResult(status="ok", outputs={"active_page_url": ctx.active_page.url})

    async def _h_switch_extension_popup_v2(
        self, ctx: NodeExecutionContext, node: Node
    ) -> NodeExecutionResult:
        target = str(self._resolve(ctx, node.config.get("match_pattern_includes", "")))
        index = int(node.config.get("matched_index", 0))
        pages = [
            p
            for p in ctx.browser_context.pages
            if p.url.startswith("chrome-extension://") and (not target or target in p.url)
        ]
        if not pages:
            return await self._not_implemented(ctx, node, "extension_popup_not_found")
        idx = max(0, min(index, len(pages) - 1))
        ctx.active_page = pages[idx]
        ctx.active_frame = None
        return NodeExecutionResult(status="ok", outputs={"active_popup_url": ctx.active_page.url})

    async def _h_trigger_extension(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        extension_url = str(self._resolve(ctx, node.config.get("extension_url", ""))).strip()
        shortcut = str(node.config.get("shortcut", "")).strip()
        if extension_url:
            page = await ctx.browser_context.new_page()
            await page.goto(extension_url, wait_until="domcontentloaded")
            ctx.active_page = page
            return NodeExecutionResult(status="ok", outputs={"active_page_url": page.url})
        if shortcut:
            await ctx.active_page.keyboard.press(shortcut)
            return NodeExecutionResult(status="ok")
        return await self._not_implemented(ctx, node, "trigger_extension_requires_url_or_shortcut")

    async def _h_dialog_alert(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        action_yes = str(node.config.get("action_for_dialog", "yes")).lower() in {
            "yes",
            "accept",
            "ok",
            "true",
        }
        if not ctx.dialog_handler_registered:
            def _on_dialog(dialog) -> None:
                if action_yes:
                    asyncio.create_task(dialog.accept())
                else:
                    asyncio.create_task(dialog.dismiss())
            ctx.active_page.on("dialog", _on_dialog)
            ctx.dialog_handler_registered = True
        return NodeExecutionResult(status="ok")

    async def _h_sleep(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        mode = str(node.config.get("options", node.config.get("mode", "fixed"))).lower()
        if mode == "random":
            min_s = float(node.config.get("min_seconds", node.config.get("seconds_min", 1)))
            max_s = float(node.config.get("max_seconds", node.config.get("seconds_max", 3)))
            delay = random.uniform(min_s, max_s)
        else:
            delay = float(node.config.get("seconds", 1))
        await asyncio.sleep(delay)
        return NodeExecutionResult(status="ok")

    async def _h_if(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        expr = str(node.config.get("expression", "")).strip()
        if not expr:
            value = self._bool(self._resolve(ctx, node.config.get("value", False)))
        else:
            value = self._bool(self._eval_expr(ctx, expr))
        return NodeExecutionResult(
            status="ok",
            outputs={"if_result": value},
            next_label="true" if value else "false",
        )

    async def _h_eval(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        expr = str(node.config.get("expression", "")).strip()
        if not expr:
            raise ValueError("Eval requires expression")
        value = self._eval_expr(ctx, expr)
        output = str(node.config.get("output_variable", "eval_result"))
        return NodeExecutionResult(status="ok", outputs={output: value})

    async def _h_javascript(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        script = str(node.config.get("script", "")).strip()
        if not script:
            raise ValueError("Javascript node requires script")
        args = self._resolve(ctx, node.config.get("args", {}))
        value = await ctx.active_page.evaluate(script, args)
        output = str(node.config.get("output_variable", "js_result"))
        return NodeExecutionResult(status="ok", outputs={output: value})

    async def _h_loop(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        mode = str(node.config.get("mode", "count")).lower()
        key = f"loop:{node.id}"
        state = ctx.loop_state.setdefault(key, {"i": 0})
        if mode == "count":
            count = int(self._resolve(ctx, node.config.get("count", 1)))
            i = int(state.get("i", 0))
            if i < count:
                state["i"] = i + 1
                output = str(node.config.get("output_variable", "loop_index"))
                return NodeExecutionResult(status="ok", outputs={output: i}, next_label="loop")
            state["i"] = 0
            return NodeExecutionResult(status="ok", next_label="next")
        if mode == "list":
            values = self._resolve(ctx, node.config.get("list", []))
            if isinstance(values, str):
                values = [v for v in values.split(str(node.config.get("delimiter", ","))) if v]
            if not isinstance(values, list):
                raise ValueError("Loop list mode requires list")
            i = int(state.get("i", 0))
            if i < len(values):
                state["i"] = i + 1
                output = str(node.config.get("output_variable", "loop_item"))
                index_var = str(node.config.get("index_variable", "loop_index"))
                return NodeExecutionResult(
                    status="ok",
                    outputs={output: values[i], index_var: i},
                    next_label="loop",
                )
            state["i"] = 0
            return NodeExecutionResult(status="ok", next_label="next")
        if mode == "while":
            limit = int(node.config.get("max_iterations", 200))
            i = int(state.get("i", 0))
            if i >= limit:
                state["i"] = 0
                return NodeExecutionResult(
                    status="ok",
                    next_label="next",
                    capability_flags=["loop_while_max_iteration_hit"],
                )
            expr = str(node.config.get("expression", "False"))
            ok = self._bool(self._eval_expr(ctx, expr))
            if ok:
                state["i"] = i + 1
                return NodeExecutionResult(
                    status="ok",
                    outputs={"loop_index": i},
                    next_label="loop",
                )
            state["i"] = 0
            return NodeExecutionResult(status="ok", next_label="next")
        raise ValueError(f"Unsupported loop mode: {mode}")

    async def _h_loop_break(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        return NodeExecutionResult(status="ok", next_label="break")

    async def _h_emulate(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        width = int(node.config.get("width", 1366))
        height = int(node.config.get("height", 768))
        await ctx.active_page.set_viewport_size({"width": width, "height": height})
        user_agent = str(self._resolve(ctx, node.config.get("user_agent", ""))).strip()
        if user_agent:
            return await self._not_implemented(ctx, node, "user_agent_change_requires_new_context")
        return NodeExecutionResult(status="ok")

    async def _h_comment(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        text = str(self._resolve(ctx, node.config.get("text", node.config.get("options", ""))))
        await ctx.emit_log("info", f"Comment: {text}", node.id)
        return NodeExecutionResult(status="ok")

    async def _h_unknown(self, ctx: NodeExecutionContext, node: Node) -> NodeExecutionResult:
        return await self._not_implemented(ctx, node, f"unknown_node_type:{node.type}")
