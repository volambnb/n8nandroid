from __future__ import annotations

import asyncio
import io
import json
import logging
import ssl
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from automation.compiler import CompiledGraph, GraphCompiler
from automation.models import (
    AppGraph,
    AppInput,
    CreateAppRequest,
    Edge,
    Node,
    CreateSavedTaskRequest,
    CreateScheduleRequest,
    RunRequest,
    UpdateAppRequest,
    UpdateScheduleRequest,
)
from automation.node_executor import NodeExecutionContext, NodeExecutor
from automation.phone_runtime import PhoneRecorder, PhoneWorkerPool
from automation.store import AutomationStore
from config.settings import settings
from core.profile_manager import OpenResult, ProfileInfo, ProfileManager
from core.task_queue import TaskItem, TaskQueue

logger = logging.getLogger(__name__)


class AutomationService:
    """No-code automation runtime with SQLite persistence and IXBrowser execution."""

    def __init__(self) -> None:
        self.store = AutomationStore(settings.automation_db_path)
        self.compiler = GraphCompiler()
        self.executor = NodeExecutor()
        self.profiles = ProfileManager()
        self.phone_workers = PhoneWorkerPool(settings.artemis_root, settings.artemis_python, settings.adb_path)
        self.phone_recorder = PhoneRecorder(self.store, self.phone_workers)
        self.queue = TaskQueue(
            worker_fn=self._worker,
            max_concurrent=settings.ixbrowser_max_concurrent,
        )

        self._pw_ctx = None
        self._pw: Playwright | None = None
        self._pw_lock = asyncio.Lock()
        self._compiled_by_run: dict[str, CompiledGraph] = {}
        self._called_by_run: dict[str, dict[str, CompiledGraph]] = {}
        self._run_task_ids: dict[str, list[str]] = {}
        self._run_stop_flags: dict[str, bool] = {}
        self._run_stop_events: dict[str, asyncio.Event] = {}
        self._run_configs: dict[str, dict[str, Any]] = {}
        self._run_semaphores: dict[str, asyncio.Semaphore] = {}
        self._scheduler_task: asyncio.Task | None = None
        self._running = False
        self._lock = asyncio.Lock()
        self._extensions_root = (
            Path(settings.automation_db_path).resolve().parent / "extensions"
        )
        self._extensions_root.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self.apply_extension_settings_to_profile_manager(self.profiles)
        await self.queue.start()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="automation_scheduler")
        logger.info("Automation service started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
        await self.queue.stop()
        await self.phone_workers.close_all()
        await self._reset_playwright()
        logger.info("Automation service stopped")

    async def _ensure_playwright(self) -> Playwright:
        async with self._pw_lock:
            if self._pw is not None:
                return self._pw

            context = async_playwright()
            try:
                playwright = await context.start()
            except Exception:
                try:
                    await asyncio.wait_for(context.__aexit__(None, None, None), timeout=3)
                except Exception:
                    logger.debug("Could not clean up failed Playwright startup", exc_info=True)
                raise

            self._pw_ctx = context
            self._pw = playwright
            return playwright

    async def _reset_playwright(self) -> None:
        async with self._pw_lock:
            context = self._pw_ctx
            self._pw_ctx = None
            self._pw = None
            if context is None:
                return
            try:
                await asyncio.wait_for(context.__aexit__(None, None, None), timeout=3)
            except Exception:
                logger.debug("Could not stop Playwright driver cleanly", exc_info=True)

    async def _wait_for_cdp_endpoint(self, debugging_address: str, timeout: float = 30) -> None:
        address = str(debugging_address or "").strip()
        if not address:
            raise RuntimeError("IXBrowser did not return a CDP debugging address")

        endpoint = f"http://{address}/json/version"
        deadline = asyncio.get_running_loop().time() + max(1.0, timeout)
        last_error = "endpoint not ready"
        # Build the context explicitly instead of ssl.create_default_context().
        # On some Windows machines SSLKEYLOGFILE points at a protected browser
        # filter device (for example \\.\nllMonFltProxy\...). Python 3.14
        # reads that environment variable while httpx creates its default TLS
        # context, even for this plain-HTTP localhost probe, and can fail before
        # sending the request. This context keeps normal certificate checks
        # available without inheriting that process-wide key-log destination.
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.load_default_certs()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(1.5),
            trust_env=False,
            follow_redirects=False,
            verify=ssl_context,
        ) as client:
            while True:
                try:
                    response = await client.get(endpoint)
                    if response.is_success:
                        details = response.json()
                        if isinstance(details, dict) and details.get("webSocketDebuggerUrl"):
                            return
                        last_error = "CDP version response is incomplete"
                    else:
                        last_error = f"CDP endpoint returned HTTP {response.status_code}"
                except (httpx.RequestError, ValueError) as exc:
                    last_error = type(exc).__name__

                if asyncio.get_running_loop().time() >= deadline:
                    raise RuntimeError(
                        "IXBrowser opened the profile, but its CDP endpoint did not become ready "
                        f"within {timeout:g}s ({last_error})"
                    )
                await asyncio.sleep(0.35)

    async def _db(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    # ---- App APIs ----
    async def create_app(self, req: CreateAppRequest) -> dict[str, Any]:
        self.compiler.compile(req.graph)
        await self._validate_call_graph(req.graph, root_app_id=None)
        return await self._db(
            self.store.create_app,
            req.name,
            req.description,
            req.graph.model_dump(mode="json", by_alias=True),
        )

    async def list_apps(self) -> list[dict[str, Any]]:
        return await self._db(self.store.list_apps)

    async def get_app(self, app_id: str) -> dict[str, Any] | None:
        return await self._db(self.store.get_app, app_id)

    async def update_app(self, app_id: str, req: UpdateAppRequest) -> dict[str, Any] | None:
        graph_payload = None
        if req.graph is not None:
            self.compiler.compile(req.graph)
            await self._validate_call_graph(req.graph, root_app_id=app_id)
            graph_payload = req.graph.model_dump(mode="json", by_alias=True)
        return await self._db(
            self.store.update_app,
            app_id,
            name=req.name,
            description=req.description,
            graph=graph_payload,
        )

    @staticmethod
    def _call_app_ids(graph: AppGraph) -> list[str]:
        return [str(n.config.get("app_id", "")).strip() for n in graph.nodes
                if str(n.type).strip().lower().replace(" ", "_") == "call_app"]

    async def _validate_call_graph(self, root_graph: AppGraph, root_app_id: str | None) -> None:
        visiting: list[str] = [root_app_id] if root_app_id else []
        done: set[str] = set()

        async def visit(graph: AppGraph, owner: str | None) -> None:
            for child_id in self._call_app_ids(graph):
                if not child_id:
                    raise ValueError("Call App nodes require an app_id")
                if owner and child_id == owner or child_id in visiting:
                    chain = " -> ".join([*visiting, child_id])
                    raise ValueError(f"Recursive Call App reference is not allowed: {chain}")
                if child_id in done:
                    continue
                child = await self.get_app(child_id)
                if child is None:
                    raise ValueError(f"Call App references missing app: {child_id}")
                visiting.append(child_id)
                await visit(AppGraph.model_validate(child["graph"]), child_id)
                visiting.pop()
                done.add(child_id)

        await visit(root_graph, root_app_id)

    async def _snapshot_call_graph(self, root_app_id: str, root_graph: AppGraph) -> dict[str, CompiledGraph]:
        snapshots: dict[str, CompiledGraph] = {}
        visiting = {root_app_id}

        async def visit(app_id: str, graph: AppGraph) -> None:
            for child_id in self._call_app_ids(graph):
                if child_id in visiting:
                    raise ValueError(f"Recursive Call App reference is not allowed: {' -> '.join([*visiting, child_id])}")
                if child_id in snapshots:
                    continue
                child = await self.get_app(child_id)
                if child is None:
                    raise ValueError(f"Call App references missing app: {child_id}")
                child_graph = AppGraph.model_validate(child["graph"])
                snapshots[child_id] = self.compiler.compile(child_graph)
                visiting.add(child_id)
                await visit(child_id, child_graph)
                visiting.remove(child_id)

        await visit(root_app_id, root_graph)
        return snapshots

    async def get_phone_image_asset(self, asset_id: str) -> dict[str, Any] | None:
        return await self._db(self.store.get_phone_image_asset, asset_id)

    async def list_phone_image_assets(self) -> list[dict[str, Any]]:
        return await self._db(self.store.list_phone_image_assets)

    async def export_app_bundle(self, root_app_id: str) -> bytes:
        root = await self.get_app(root_app_id)
        if not root:
            raise ValueError("App not found")
        apps: dict[str, dict[str, Any]] = {}

        async def visit(app: dict[str, Any]) -> None:
            app_id = str(app["id"])
            if app_id in apps:
                return
            apps[app_id] = app
            graph = app.get("graph") or {}
            for node in graph.get("nodes", []):
                if str(node.get("type", "")).strip().lower().replace(" ", "_") == "call_app":
                    child_id = str((node.get("config") or {}).get("app_id", ""))
                    child = await self.get_app(child_id)
                    if not child:
                        raise ValueError(f"App bundle references missing app: {child_id}")
                    await visit(child)

        await visit(root)
        asset_ids: set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "image_asset_id" and item:
                        asset_ids.add(str(item))
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        for app in apps.values():
            collect(app.get("graph", {}))
        manifest = {
            "format": "autoixb-app-bundle", "version": 1, "root_app_id": root_app_id,
            "apps": [{"id": app["id"], "name": app["name"], "description": app.get("description", ""),
                      "graph": app["graph"]} for app in apps.values()],
            "assets": {},
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, asset_id in enumerate(sorted(asset_ids), start=1):
                asset = await self.get_phone_image_asset(asset_id)
                if not asset:
                    raise ValueError(f"App bundle references missing phone image: {asset_id}")
                path = f"assets/{index:04d}.png"
                archive.writestr(path, bytes(asset["data"]))
                manifest["assets"][asset_id] = {"path": path, "name": asset.get("name") or "Phone image"}
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return output.getvalue()

    async def import_app_bundle(self, bundle_data: bytes) -> dict[str, Any]:
        if len(bundle_data) > 100 * 1024 * 1024:
            raise ValueError("App bundle exceeds 100 MB.")
        try:
            with zipfile.ZipFile(io.BytesIO(bundle_data)) as archive:
                names = archive.namelist()
                if names.count("manifest.json") != 1:
                    raise ValueError("App bundle is missing manifest.json.")
                if sum(info.file_size for info in archive.infolist()) > 200 * 1024 * 1024:
                    raise ValueError("App bundle expands beyond the 200 MB limit.")
                manifest = json.loads(archive.read("manifest.json"))
                if not isinstance(manifest, dict):
                    raise ValueError("App bundle manifest must be an object.")
                if manifest.get("format") != "autoixb-app-bundle" or manifest.get("version") != 1:
                    raise ValueError("Unsupported app bundle format.")
                source_apps = manifest.get("apps")
                if not isinstance(source_apps, list) or not source_apps:
                    raise ValueError("App bundle contains no apps.")
                if not all(isinstance(item, dict) for item in source_apps):
                    raise ValueError("App bundle contains an invalid app entry.")
                source_id_values = [str(item.get("id") or "").strip() for item in source_apps]
                source_ids = set(source_id_values)
                if "" in source_ids or len(source_ids) != len(source_apps):
                    raise ValueError("App bundle has invalid or duplicate app IDs.")
                root_source_id = str(manifest.get("root_app_id") or "").strip()
                if root_source_id not in source_ids:
                    raise ValueError("App bundle root app is missing.")
                asset_manifest = manifest.get("assets") or {}
                if not isinstance(asset_manifest, dict):
                    raise ValueError("App bundle image manifest is invalid.")
                asset_data: dict[str, tuple[bytes, str]] = {}
                for old_asset_id, metadata in asset_manifest.items():
                    if not isinstance(metadata, dict):
                        raise ValueError(f"App bundle image metadata is invalid: {old_asset_id}")
                    path = str(metadata.get("path", ""))
                    if (not path.startswith("assets/") or ".." in path.split("/")
                            or path.startswith("/") or names.count(path) != 1):
                        raise ValueError(f"App bundle image file is missing: {old_asset_id}")
                    image_data = archive.read(path)
                    if not image_data.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError(f"App bundle image is not a PNG: {old_asset_id}")
                    asset_data[str(old_asset_id)] = (image_data, str(metadata.get("name") or "Imported phone image"))
        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, AttributeError, UnicodeDecodeError) as exc:
            raise ValueError("Could not read the app bundle.") from exc

        app_ids = {old_id: uuid.uuid4().hex[:12] for old_id in source_ids}
        adjacency: dict[str, list[str]] = {}
        prepared: list[dict[str, Any]] = []
        referenced_assets: set[str] = set()
        for item in source_apps:
            old_id = str(item["id"]).strip()
            source_graph = item.get("graph")
            if not isinstance(source_graph, dict):
                raise ValueError(f"App bundle has an invalid graph for app {old_id}.")
            graph = json.loads(json.dumps(source_graph))
            children: list[str] = []
            def remap(value: Any) -> None:
                if isinstance(value, dict):
                    if "app_id" in value and str(value["app_id"]) in app_ids:
                        value["app_id"] = app_ids[str(value["app_id"])]
                    if "app_id" in value and str(value["app_id"]) not in app_ids and value.get("type") == "Call App":
                        raise ValueError(f"App bundle has an external app reference in {old_id}.")
                    if "image_asset_id" in value and value["image_asset_id"]:
                        referenced_assets.add(str(value["image_asset_id"]))
                    for child in value.values():
                        remap(child)
                elif isinstance(value, list):
                    for child in value:
                        remap(child)
            remap(graph)
            graph = AppGraph.model_validate(graph).model_dump(mode="json", by_alias=True)
            for node in graph.get("nodes", []):
                if str(node.get("type", "")).strip().lower().replace(" ", "_") == "call_app":
                    target = str((node.get("config") or {}).get("app_id", ""))
                    if target not in app_ids.values():
                        raise ValueError(f"App bundle has an external child app reference in {old_id}.")
                    children.append(target)
            self.compiler.compile(AppGraph.model_validate(graph))
            adjacency[app_ids[old_id]] = children
            prepared.append({"id": app_ids[old_id], "name": str(item.get("name") or "Imported app"),
                             "description": str(item.get("description") or ""), "graph": graph})

        visiting: set[str] = set()
        visited: set[str] = set()
        def ensure_acyclic(app_id: str) -> None:
            if app_id in visiting:
                raise ValueError("App bundle contains recursive Call App references.")
            if app_id in visited:
                return
            visiting.add(app_id)
            for child in adjacency.get(app_id, []):
                ensure_acyclic(child)
            visiting.remove(app_id)
            visited.add(app_id)
        for app_id in adjacency:
            ensure_acyclic(app_id)

        missing_assets = referenced_assets - set(asset_data)
        if missing_assets:
            raise ValueError(f"App bundle is missing image asset {sorted(missing_assets)[0]}.")

        asset_ids: dict[str, str] = {}
        try:
            for old_asset_id in sorted(referenced_assets):
                image_data, name = asset_data[old_asset_id]
                asset_ids[old_asset_id] = await self._db(self.store.put_phone_image_asset, image_data, name)
            for app in prepared:
                def remap_assets(value: Any) -> None:
                    if isinstance(value, dict):
                        if value.get("image_asset_id"):
                            value["image_asset_id"] = asset_ids[str(value["image_asset_id"])]
                        for child in value.values():
                            remap_assets(child)
                    elif isinstance(value, list):
                        for child in value:
                            remap_assets(child)
                remap_assets(app["graph"])
            saved = await self._db(self.store.create_app_bundle, prepared)
        except Exception:
            if asset_ids:
                await self._db(self.store.cleanup_orphan_phone_assets, set(asset_ids.values()))
            raise
        root_id = app_ids.get(root_source_id)
        root = next((app for app in saved if app["id"] == root_id), None)
        if root is None:  # Defensive: root is validated before any app is written.
            raise RuntimeError("Imported bundle did not produce its declared root app.")
        return {"root": root, "apps": saved, "id_map": app_ids, "asset_count": len(asset_ids)}

    async def generate_phone_recording(self, session_id: str, *, parent_name: str, repeat_count: int = 1) -> dict[str, Any]:
        recording = await self.phone_recorder.get(session_id)
        if not recording:
            raise ValueError("Phone recording session not found.")
        events = list(recording.get("events", []))
        if not events:
            raise ValueError("Record at least one phone action before creating an app.")
        # Segment marks remain in the draft, but the recorder now generates
        # one linear app. Looping can be added later in the editor if needed.
        segments = [{"start_event": 1, "end_event": len(events)}]
        app_inputs: list[AppInput] = [AppInput(
            name="phone_serial", type="string", required=True, default=str(recording.get("serial") or ""),
        )]
        variables_config: dict[str, Any] = {"custom_variables": [], "timeout": 30}
        parent_nodes = [
            Node(id="start", type="Start", x=60, y=100),
            Node(id="variables", type="Variables", config=variables_config, x=60, y=260),
            # The palette label is "ARTEMIS Connect"; the executable type is ARTEMIS.
            Node(id="phone_connect", type="ARTEMIS", config={
                "serial_variable": "phone_serial", "output_variable": "artemis_phone", "timeout": 120,
            }, x=250, y=100),
        ]
        variable_items = parent_nodes[1].config["custom_variables"]
        parent_edges = [
            Edge(**{"from": "start", "to": "phone_connect", "label": "next"}),
        ]

        def preferred_image_region(event: dict[str, Any]) -> dict[str, float] | None:
            width = max(1, int(event.get("width") or 1))
            height = max(1, int(event.get("height") or 1))
            raw_bounds = event.get("target_bounds")
            try:
                left, top, right, bottom = (int(value) for value in raw_bounds)
                pad_x = max(24, (right - left) // 2)
                pad_y = max(24, (bottom - top) // 2)
            except (TypeError, ValueError):
                cfg = event.get("config") or {}
                x, y = int(cfg.get("x", width // 2)), int(cfg.get("y", height // 2))
                left, top, right, bottom = x - width * 0.12, y - height * 0.08, x + width * 0.12, y + height * 0.08
                pad_x, pad_y = width * 0.04, height * 0.04
            x0 = max(0, left - pad_x) / width
            y0 = max(0, top - pad_y) / height
            x1 = min(width, right + pad_x) / width
            y1 = min(height, bottom + pad_y) / height
            if x1 <= x0 or y1 <= y0:
                return None
            return {"x": float(x0), "y": float(y0), "w": float(x1 - x0), "h": float(y1 - y0)}

        for segment_index, segment in enumerate(segments):
            app_inputs_child = app_inputs
            child_nodes = parent_nodes
            child_edges = parent_edges
            selected = events[int(segment["start_event"]) - 1:int(segment["end_event"])]
            branch_tails = ["phone_connect"]
            for step_index, event in enumerate(selected, start=1):
                event_type = str(event.get("type", ""))
                cfg = dict(event.get("config", {}))
                node_id = f"step_{step_index}"
                node_type = "Comment"
                node_cfg: dict[str, Any] = {"text": "Unmapped recorder step"}
                step_nodes: list[Node] = []
                step_edges: list[Edge] = []
                next_tails: list[str] = []
                selector = event.get("selector")
                element = event.get("element") if isinstance(event.get("element"), dict) else {}
                # Resource IDs on launcher icons are commonly shared by every
                # icon. Prefer a recorded accessibility label in that case so
                # replay can identify the intended icon without relying on a
                # visually ambiguous crop.
                playback_selector = selector if isinstance(selector, dict) and selector.get("value") and event.get("selector_unique") else None
                if playback_selector is None:
                    content_desc = str(element.get("content-desc") or element.get("accessibilityText") or "").strip()
                    text_value = str(element.get("text") or "").strip()
                    if content_desc:
                        playback_selector = {"by": "content_desc", "value": content_desc}
                    elif text_value:
                        playback_selector = {"by": "text", "value": text_value}
                image_id = str(event.get("image_asset_id", ""))
                if event_type in {"tap", "double_tap", "long_press"}:
                    if (event_type == "tap" and not playback_selector
                            and str(element.get("clickable", "")).strip().lower() == "false"):
                        # A plain tap on an accessibility node explicitly marked
                        # non-clickable has no semantic action to replay. Image
                        # matching such web-view text is brittle when the page
                        # layout or font rendering changes, so retain an audit
                        # log step and continue safely.
                        node_type = "Log"
                        node_cfg = {"message": f"Skipped recorded tap at event {event.get('index', step_index)}: target was non-clickable and had no selector."}
                        step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                        next_tails = [node_id]
                    elif isinstance(playback_selector, dict) and playback_selector.get("value"):
                        action_type = {"tap": "ARTEMIS Tap", "double_tap": "ARTEMIS Double Tap", "long_press": "ARTEMIS Long Press"}[event_type]
                        selector_config = {"serial_variable": "artemis_phone", "target_mode": "element",
                                           "selector_by": playback_selector.get("by", "text"), "selector": playback_selector["value"],
                                           "match_mode": "exact", "match_index": 0, "require_unique": True, "timeout": 30,
                                           "duration_ms": int(cfg.get("duration_ms", 800))}
                        if image_id:
                            wait_id, selector_id, image_tap_id = f"wait_{step_index}", f"tap_{step_index}", f"image_{step_index}"
                            step_nodes = [
                                Node(id=wait_id, type="ARTEMIS Wait Element", config={
                                    "serial_variable": "artemis_phone", "selector_by": playback_selector.get("by", "text"),
                                    "selector": playback_selector["value"], "match_mode": "exact", "match_index": 0,
                                    "require_unique": True, "fallback_on_miss": True,
                                    "wait_timeout_seconds": 8, "poll_interval_seconds": 0.35, "timeout": 12,
                                }, x=250 + step_index * 150, y=100 + step_index * 105),
                                Node(id=selector_id, type=action_type, config=selector_config, x=430 + step_index * 150, y=50 + step_index * 105),
                                Node(id=image_tap_id, type="ARTEMIS Tap Image", config={
                                    "serial_variable": "artemis_phone", "image_asset_id": image_id,
                                    "threshold": 0.86, "scale_min": 0.8, "scale_max": 1.2,
                                    "scale_steps": 9, "wait_timeout_seconds": 8, "region": preferred_image_region(event), "timeout": 30,
                                }, x=430 + step_index * 150, y=150 + step_index * 105),
                            ]
                            step_edges.extend([
                                Edge(**{"from": wait_id, "to": selector_id, "label": "next"}),
                                Edge(**{"from": wait_id, "to": image_tap_id, "label": "fallback"}),
                                Edge(**{"from": selector_id, "to": image_tap_id, "label": "error"}),
                            ])
                            next_tails = [selector_id, image_tap_id]
                        else:
                            wait_id = f"wait_{step_index}"
                            selector_id = f"tap_{step_index}"
                            step_nodes = [
                                Node(id=wait_id, type="ARTEMIS Wait Element", config={
                                    "serial_variable": "artemis_phone", "selector_by": playback_selector.get("by", "text"),
                                    "selector": playback_selector["value"], "match_mode": "exact", "match_index": 0,
                                    "require_unique": True, "wait_timeout_seconds": 8,
                                    "poll_interval_seconds": 0.35, "timeout": 12,
                                }, x=250 + step_index * 150, y=100 + step_index * 105),
                                Node(id=selector_id, type=action_type, config=selector_config, x=430 + step_index * 150, y=100 + step_index * 105),
                            ]
                            step_edges.append(Edge(**{"from": wait_id, "to": selector_id, "label": "next"}))
                            next_tails = [selector_id]
                    elif image_id:
                        node_type = "ARTEMIS Tap Image"
                        node_cfg = {"serial_variable": "artemis_phone", "image_asset_id": image_id,
                                    "threshold": 0.86, "scale_min": 0.8, "scale_max": 1.2,
                                    "scale_steps": 9, "wait_timeout_seconds": 8, "region": preferred_image_region(event), "timeout": 30}
                        step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                        next_tails = [node_id]
                    else:
                        node_type = {"tap": "ARTEMIS Tap", "double_tap": "ARTEMIS Double Tap", "long_press": "ARTEMIS Long Press"}[event_type]
                        node_cfg = {"serial_variable": "artemis_phone", "target_mode": "coordinates",
                                    "x": int(cfg.get("x", 0)), "y": int(cfg.get("y", 0)),
                                    "duration_ms": int(cfg.get("duration_ms", 800)), "timeout": 30,
                                    "coordinate_review_required": True}
                        step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                        next_tails = [node_id]
                elif event_type == "swipe":
                    node_type = "ARTEMIS Swipe"
                    width, height = max(1, int(event.get("width") or 1)), max(1, int(event.get("height") or 1))
                    node_cfg = {"serial_variable": "artemis_phone", "direction": "up",
                                "start_x_percent": int(cfg.get("x1", 0)) / width,
                                "start_y_percent": int(cfg.get("y1", 0)) / height,
                                "end_x_percent": int(cfg.get("x2", 0)) / width,
                                "end_y_percent": int(cfg.get("y2", 0)) / height,
                                "duration_ms": int(cfg.get("duration_ms", 400)), "timeout": 30}
                    step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                    next_tails = [node_id]
                elif event_type == "send_text":
                    node_type = "ARTEMIS Type Text"
                    node_cfg = {"serial_variable": "artemis_phone", "clear_existing": bool(cfg.get("clear_existing")), "timeout": 30}
                    if event.get("secret"):
                        variable = str(event.get("text_variable") or f"phone_secret_{step_index}")
                        node_cfg["text_variable"] = variable
                        if not any(item.name == variable for item in app_inputs_child):
                            app_inputs_child.append(AppInput(name=variable, type="string", required=True, secret=True))
                            variable_items.append({"name": variable, "source": "input", "secret": True})
                    else:
                        variable = f"phone_text_{step_index}"
                        value = str(event.get("text", ""))
                        node_cfg["text_variable"] = variable
                        app_inputs_child.append(AppInput(name=variable, type="string", default=value))
                        variable_items.append({"name": variable, "source": "value", "value": value, "allow_override": True})
                    step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                    next_tails = [node_id]
                elif event_type == "clear_text":
                    node_type, node_cfg = "ARTEMIS Clear Text", {"serial_variable": "artemis_phone", "timeout": 30}
                    step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                    next_tails = [node_id]
                elif event_type == "set_clipboard":
                    node_type, node_cfg = "ARTEMIS Set Clipboard", {"serial_variable": "artemis_phone", "text": "", "timeout": 30}
                    step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                    next_tails = [node_id]
                elif event_type == "press_key":
                    node_type, node_cfg = "ARTEMIS Key Event", {"serial_variable": "artemis_phone", "key": cfg.get("key", "BACK"), "timeout": 30}
                    step_nodes = [Node(id=node_id, type=node_type, config=node_cfg, x=300 + step_index * 150, y=100 + step_index * 105)]
                    next_tails = [node_id]
                if step_nodes:
                    first_step_id = step_nodes[0].id
                    child_edges.extend(Edge(**{"from": tail, "to": first_step_id, "label": "next"}) for tail in branch_tails)
                    child_nodes.extend(step_nodes)
                    child_edges.extend(step_edges)
                    branch_tails = next_tails

            for generated_node in child_nodes:
                generated_node.config["sleep_before_run_seconds"] = 1
            graph = AppGraph(nodes=child_nodes, edges=child_edges, inputs=app_inputs_child)
            self.compiler.compile(graph)
            app_id = uuid.uuid4().hex[:12]
            saved = await self._db(self.store.create_app_bundle, [{"id": app_id,
                "name": parent_name.strip() or "Phone workflow",
                "description": "Phone workflow generated from recorder",
                "graph": graph.model_dump(mode="json", by_alias=True)}])
            return {"app": saved[0], "parent": saved[0], "children": []}

    async def delete_app(self, app_id: str) -> bool:
        return await self._db(self.store.delete_app, app_id)

    # ---- Task APIs ----
    async def create_task(self, req: CreateSavedTaskRequest) -> dict[str, Any]:
        app = await self.get_app(req.app_id)
        if app is None:
            raise ValueError("App not found")
        config = req.model_dump(mode="json")
        config.pop("name", None)
        config.pop("app_id", None)
        return await self._db(self.store.create_task, req.name, req.app_id, config)

    async def list_tasks(self) -> list[dict[str, Any]]:
        return await self._db(self.store.list_tasks)

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        return await self._db(self.store.get_task, task_id)

    async def update_task(
        self,
        task_id: str,
        *,
        name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self._db(self.store.update_task, task_id, name=name, config=config)

    async def delete_task(self, task_id: str) -> bool:
        return await self._db(self.store.delete_task, task_id)

    # ---- Schedule APIs ----
    async def create_schedule(self, req: CreateScheduleRequest) -> dict[str, Any]:
        task = await self.get_task(req.task_id)
        if task is None:
            raise ValueError("Task not found")
        return await self._db(
            self.store.create_schedule,
            name=req.name,
            task_id=req.task_id,
            interval_seconds=req.interval_seconds,
            cron_expr=req.cron_expr,
            enabled=req.enabled,
            input_overrides=req.input_overrides,
        )

    async def list_schedules(self) -> list[dict[str, Any]]:
        return await self._db(self.store.list_schedules)

    async def update_schedule(self, schedule_id: str, req: UpdateScheduleRequest) -> dict[str, Any] | None:
        payload = req.model_dump(exclude_none=True, mode="json")
        return await self._db(self.store.update_schedule, schedule_id, **payload)

    async def delete_schedule(self, schedule_id: str) -> bool:
        return await self._db(self.store.delete_schedule, schedule_id)

    # ---- Extension Settings APIs ----
    def _default_extension_settings(self) -> dict[str, Any]:
        return {
            "load_extensions": True,
            "disable_extension_welcome_page": True,
            "disable_other_extensions": False,
            "startup_args": [],
            "items": [],
        }

    def _normalize_extension_item(self, item: dict[str, Any], idx: int) -> dict[str, Any]:
        source_type = str(item.get("source_type") or "path").strip().lower()
        if source_type not in {"path", "url"}:
            source_type = "path"
        path_raw = str(item.get("path") or "").strip()
        url_raw = str(item.get("url") or "").strip()
        ext_id = str(item.get("id") or "").strip() or f"ext_{idx}_{uuid.uuid4().hex[:8]}"
        name_raw = str(item.get("name") or "").strip()
        version_raw = str(item.get("version") or "").strip()
        manifest_version_raw = str(item.get("manifest_version") or "").strip()
        created_at_raw = item.get("created_at")
        try:
            created_at = float(created_at_raw) if created_at_raw is not None else time.time()
        except (TypeError, ValueError):
            created_at = time.time()

        runtime_status = "ready"
        status_note = ""
        if source_type == "path":
            if not path_raw:
                runtime_status = "missing_path"
                status_note = "Missing extension path"
            elif not Path(path_raw).is_dir():
                runtime_status = "missing_path"
                status_note = "Path not found or not a folder"
        elif source_type == "url":
            runtime_status = "url_metadata_only"
            status_note = "URL extension is metadata only until converted to local folder"

        return {
            "id": ext_id,
            "name": name_raw or f"Extension {idx + 1}",
            "source_type": source_type,
            "path": path_raw,
            "url": url_raw,
            "version": version_raw,
            "manifest_version": manifest_version_raw,
            "enabled": bool(item.get("enabled", True)),
            "created_at": created_at,
            "note": str(item.get("note") or "").strip(),
            "runtime_status": runtime_status,
            "status_note": status_note,
        }

    def _normalize_extension_settings(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        base = self._default_extension_settings()
        payload = payload or {}
        startup_args_raw = payload.get("startup_args", [])
        if not isinstance(startup_args_raw, list):
            startup_args_raw = []
        startup_args = []
        for arg in startup_args_raw:
            text = str(arg).strip()
            if text and text not in startup_args:
                startup_args.append(text)

        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            raw_items = []
        seen_ids: set[str] = set()
        items: list[dict[str, Any]] = []
        for idx, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                continue
            item = self._normalize_extension_item(raw, idx)
            if item["id"] in seen_ids:
                item["id"] = f"{item['id']}_{uuid.uuid4().hex[:6]}"
            seen_ids.add(item["id"])
            items.append(item)

        return {
            "load_extensions": bool(payload.get("load_extensions", base["load_extensions"])),
            "disable_extension_welcome_page": bool(
                payload.get(
                    "disable_extension_welcome_page",
                    base["disable_extension_welcome_page"],
                )
            ),
            "disable_other_extensions": bool(
                payload.get("disable_other_extensions", base["disable_other_extensions"])
            ),
            "startup_args": startup_args,
            "items": items,
        }

    def extension_open_profile_options(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        cfg = self._normalize_extension_settings(payload)
        extension_paths: list[str] = []
        seen_paths: set[str] = set()
        for item in cfg["items"]:
            if not item.get("enabled"):
                continue
            if item.get("source_type") != "path":
                continue
            if item.get("runtime_status") != "ready":
                continue
            path = str(item.get("path") or "").strip()
            if path and path not in seen_paths:
                seen_paths.add(path)
                extension_paths.append(path)
        return {
            "load_extensions": bool(cfg["load_extensions"]),
            "disable_extension_welcome_page": bool(cfg["disable_extension_welcome_page"]),
            "startup_args": list(cfg["startup_args"]),
            "extension_paths": extension_paths,
            "disable_other_extensions": bool(cfg["disable_other_extensions"]),
        }

    async def get_extension_settings(self) -> dict[str, Any]:
        raw = await self._db(self.store.get_extension_settings)
        cfg = self._normalize_extension_settings(raw)
        if raw is None:
            await self._db(self.store.set_extension_settings, cfg)
        return cfg

    async def update_extension_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg = self._normalize_extension_settings(payload)
        await self._db(self.store.set_extension_settings, cfg)
        self.profiles.set_open_profile_options(self.extension_open_profile_options(cfg))
        return cfg

    async def apply_extension_settings_to_profile_manager(
        self,
        profile_manager: ProfileManager,
    ) -> dict[str, Any]:
        cfg = await self.get_extension_settings()
        profile_manager.set_open_profile_options(self.extension_open_profile_options(cfg))
        return cfg

    def _build_extension_item_from_zip_bytes(self, filename: str, blob: bytes) -> dict[str, Any]:
        safe_name = Path(filename).name or "extension.zip"
        if not safe_name.lower().endswith(".zip"):
            raise ValueError("Only .zip extension packages are supported")
        if not blob:
            raise ValueError("Empty file")

        ext_id = f"ext_{uuid.uuid4().hex[:10]}"
        target_dir = self._extensions_root / ext_id
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                members = zf.infolist()
                if not members:
                    raise ValueError("Zip file is empty")
                for info in members:
                    candidate = Path(info.filename)
                    if candidate.is_absolute() or ".." in candidate.parts:
                        raise ValueError("Unsafe zip path detected")
                zf.extractall(target_dir)
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid zip file") from exc

        manifest_candidates = list(target_dir.rglob("manifest.json"))
        if not manifest_candidates:
            raise ValueError("manifest.json not found in extension package")
        manifest_path = sorted(
            manifest_candidates,
            key=lambda p: (len(p.parts), str(p)),
        )[0]
        extension_dir = manifest_path.parent

        name = manifest_path.parent.name
        version = ""
        manifest_version = ""
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            name = str(manifest.get("name") or name).strip() or name
            version = str(manifest.get("version") or "").strip()
            manifest_version = str(manifest.get("manifest_version") or "").strip()
        except Exception:
            pass

        return {
            "id": ext_id,
            "name": name,
            "source_type": "path",
            "path": str(extension_dir.resolve()),
            "url": "",
            "version": version,
            "manifest_version": manifest_version,
            "enabled": True,
            "created_at": time.time(),
            "note": "",
        }

    async def upload_extension_and_add(self, filename: str, blob: bytes) -> dict[str, Any]:
        item = await asyncio.to_thread(self._build_extension_item_from_zip_bytes, filename, blob)
        cfg = await self.get_extension_settings()
        cfg["items"] = [item] + list(cfg.get("items", []))
        return await self.update_extension_settings(cfg)

    def _download_extension_zip(self, url: str) -> tuple[str, bytes]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URL must start with http:// or https://")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "IXAutomationStudio/1.0"},
        )
        with urllib.request.urlopen(request, timeout=25) as resp:  # noqa: S310
            content = resp.read()
            if not content:
                raise ValueError("Downloaded file is empty")
            filename = Path(parsed.path).name or "extension.zip"
        return filename, content

    async def import_extension_url_and_add(self, url: str) -> dict[str, Any]:
        clean_url = str(url or "").strip()
        if not clean_url:
            raise ValueError("Extension URL is required")
        filename, blob = await asyncio.to_thread(self._download_extension_zip, clean_url)
        if not filename.lower().endswith(".zip"):
            raise ValueError("Only direct .zip URLs are supported for import")
        item = await asyncio.to_thread(self._build_extension_item_from_zip_bytes, filename, blob)
        item["url"] = clean_url
        cfg = await self.get_extension_settings()
        cfg["items"] = [item] + list(cfg.get("items", []))
        return await self.update_extension_settings(cfg)

    # ---- Run APIs ----
    async def run(
        self,
        req: RunRequest,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if idempotency_key and (
            len(idempotency_key) > 160
            or not all(char.isalnum() or char in "._:-" for char in idempotency_key)
        ):
            raise ValueError("Idempotency-Key may contain only letters, digits, '.', '_', ':', '-' (max 160)")
        if req.task_id:
            task = await self.get_task(req.task_id)
            if task is None:
                raise ValueError("Task not found")
            app_id = task["app_id"]
            task_cfg = task["config"]
            merged_inputs = {**task_cfg.get("default_inputs", {}), **req.inputs}
            selector = req.profile_selector.model_copy(
                update=task_cfg.get("profile_selector", {})
            )
            concurrency = int(task_cfg.get("concurrency", req.concurrency))
            retry = int(task_cfg.get("retry", req.retry))
            timeout = float(task_cfg.get("timeout", req.timeout))
            stop_on_error = bool(task_cfg.get("stop_on_error", req.stop_on_error))
            close_profile_on_finish = bool(
                task_cfg.get("close_profile_on_finish", req.close_profile_on_finish)
            )
        else:
            task = None
            app_id = req.app_id
            merged_inputs = dict(req.inputs)
            selector = req.profile_selector
            concurrency = req.concurrency
            retry = req.retry
            timeout = req.timeout
            stop_on_error = req.stop_on_error
            close_profile_on_finish = req.close_profile_on_finish

        if not app_id:
            raise ValueError("app_id is required")
        app = await self.get_app(app_id)
        if app is None:
            raise ValueError("App not found")

        graph = req.graph if req.graph is not None else AppGraph.model_validate(app["graph"])
        compiled = self.compiler.compile(graph)
        called_apps = await self._snapshot_call_graph(app_id, graph)
        secret_input_names = {field.name for field in graph.inputs if field.secret}
        for field in graph.inputs:
            if field.name not in merged_inputs and field.default is not None:
                merged_inputs[field.name] = field.default
            value = merged_inputs.get(field.name)
            if field.required and (value is None or (isinstance(value, str) and not value.strip())):
                raise ValueError(f"Required app input is missing: {field.name}")
        if req.start_node_id:
            start_node_id = str(req.start_node_id).strip()
            if start_node_id not in compiled.nodes:
                raise ValueError(f"start_node_id not found: {start_node_id}")
            if req.single_node_only:
                compiled = CompiledGraph(
                    nodes={start_node_id: compiled.nodes[start_node_id]},
                    edges={},
                    start_node_id=start_node_id,
                    secret_inputs=set(compiled.secret_inputs),
                    input_defaults=dict(compiled.input_defaults),
                )
            else:
                compiled.start_node_id = start_node_id

        profiles = await self._resolve_profiles(selector.model_dump(mode="json"))
        if not profiles:
            raise ValueError("No matching profiles")

        summary = {
            "total": len(profiles),
            "pending": len(profiles),
            "running": 0,
            "done": 0,
            "failed": 0,
            "cancelled": 0,
        }
        request_payload = req.model_dump(mode="json")
        idempotency_request = (
            json.loads(json.dumps(request_payload))
            if secret_input_names and idempotency_key else None
        )
        if secret_input_names and isinstance(request_payload.get("inputs"), dict):
            request_payload["inputs"] = {
                key: ("[REDACTED]" if key in secret_input_names else value)
                for key, value in request_payload["inputs"].items()
            }
        run_obj = await self._db(
            self.store.create_run,
            app_id=app_id,
            task_id=task["id"] if task else None,
            request=request_payload,
            summary=summary,
            idempotency_key=idempotency_key,
            idempotency_request=idempotency_request,
        )
        run_id = run_obj["id"]
        if run_obj.get("idempotency_reused"):
            return {
                "run_id": run_id,
                "app_id": app_id,
                "task_id": task["id"] if task else None,
                "count": int(run_obj.get("summary", {}).get("total", 0)),
                "idempotency_reused": True,
            }

        async with self._lock:
            self._compiled_by_run[run_id] = compiled
            self._called_by_run[run_id] = called_apps
            self._run_stop_flags[run_id] = False
            self._run_stop_events[run_id] = asyncio.Event()
            self._run_configs[run_id] = {
                "inputs": merged_inputs,
                "timeout": timeout,
                "retry": retry,
                "stop_on_error": stop_on_error,
                "close_profile_on_finish": close_profile_on_finish,
                "concurrency": concurrency,
            }
            self._run_semaphores[run_id] = asyncio.Semaphore(max(1, concurrency))
            self._run_task_ids[run_id] = []

        for prof in profiles:
            run_item_id = f"{run_id}:{prof.profile_id}"
            await self._db(
                self.store.upsert_run_item,
                run_id=run_id,
                run_item_id=run_item_id,
                profile_id=prof.profile_id,
                status="pending",
            )
            item = TaskItem(
                profile_id=prof.profile_id,
                platform="automation",
                task_type="graph_run",
                params={
                    "run_id": run_id,
                    "run_item_id": run_item_id,
                    "app_id": app_id,
                    "timeout": timeout,
                    "retry": retry,
                    "stop_on_error": stop_on_error,
                    "close_profile_on_finish": close_profile_on_finish,
                    "inputs": merged_inputs,
                    "profile_name": prof.name,
                },
                priority=0,
                # Browser graph steps may have non-idempotent effects (clicks,
                # submissions, reservations). Never replay a failed graph run
                # automatically; a fresh, explicit run is safer.
                max_retries=0,
            )
            self.queue.enqueue(item)
            self._run_task_ids[run_id].append(item.id)

        await self._db(
            self.store.update_run,
            run_id,
            status="running",
            started_at=time.time(),
            summary=summary,
        )
        await self._db(
            self.store.append_log,
            run_id=run_id,
            run_item_id=None,
            level="info",
            message="Run queued",
            data={"profiles": len(profiles)},
        )
        return {
            "run_id": run_id,
            "app_id": app_id,
            "task_id": task["id"] if task else None,
            "count": len(profiles),
        }

    async def stop_run(self, run_id: str) -> dict[str, Any]:
        run = await self.get_run(run_id)
        if run is None:
            raise ValueError("Run not found")
        if str(run.get("status", "")).lower() in {"done", "failed", "cancelled"}:
            return {
                "run_id": run_id,
                "status": run["status"],
                "already_finished": True,
                "cancelled_pending": 0,
            }
        async with self._lock:
            self._run_stop_flags[run_id] = True
            stop_event = self._run_stop_events.get(run_id)
            if stop_event is not None:
                stop_event.set()
        # Persist stop intent before draining the queue so every concurrent
        # worker summary sees it and refuses to leave queued items pending.
        await self._db(self.store.update_run, run_id, stop_requested=True)
        task_ids = self._run_task_ids.get(run_id, [])
        cancelled = 0
        for task_id in task_ids:
            task = self.queue.get_task(task_id)
            if self.queue.cancel_task(task_id):
                cancelled += 1
                if task is not None:
                    await self._db(
                        self.store.upsert_run_item,
                        run_id=run_id,
                        run_item_id=f"{run_id}:{task.profile_id}",
                        profile_id=task.profile_id,
                        status="cancelled",
                        finished_at=time.time(),
                        error="Cancelled before start",
                    )
        await self._db(
            self.store.update_run,
            run_id,
            stop_requested=True,
        )
        await self._db(
            self.store.append_log,
            run_id=run_id,
            run_item_id=None,
            level="warning",
            message="Run stop requested",
            data={"cancelled_pending": cancelled},
        )
        await self._refresh_run_summary(run_id, recover_stopped=run_id not in self._run_task_ids)
        await self._finish_run_if_needed(run_id)
        refreshed = await self.get_run(run_id)
        return {
            "run_id": run_id,
            "status": refreshed["status"] if refreshed else "cancelled",
            "already_finished": False,
            "cancelled_pending": cancelled,
        }

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = await self._db(self.store.get_run, run_id)
        if run is None:
            return None
        if run.get("stop_requested") and run.get("finished_at") is None:
            # A browser refresh can reconnect to a run whose stop summary was
            # lost in a concurrent update. Reconcile it from persisted items;
            # if this service no longer owns its workers, finish orphaned items.
            await self._refresh_run_summary(run_id, recover_stopped=run_id not in self._run_task_ids)
            await self._finish_run_if_needed(run_id)
            run = await self._db(self.store.get_run, run_id)
            if run is None:
                return None
        items = await self._db(self.store.list_run_items, run_id)
        run["items"] = items
        return run

    async def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self._db(self.store.list_runs, limit)

    async def get_run_logs(self, run_id: str, after_id: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._db(self.store.get_logs, run_id, after_id=after_id, limit=limit)

    async def _resolve_profiles(self, selector: dict[str, Any]) -> list[ProfileInfo]:
        profile_ids = selector.get("profile_ids")
        group_id = int(selector.get("group_id", 0))
        tag_id = int(selector.get("tag_id", 0))
        all_profiles = await self.profiles.list_all_profiles(group_id=group_id, tag_id=tag_id)
        if profile_ids:
            wanted = {str(pid).strip() for pid in profile_ids if str(pid).strip()}
            return [p for p in all_profiles if str(p.profile_id) in wanted]
        return all_profiles

    async def _connect_profile(self, opened: OpenResult) -> tuple[Browser, BrowserContext, Page]:
        await self._wait_for_cdp_endpoint(opened.debugging_address)
        pw = await self._ensure_playwright()
        try:
            browser = await pw.chromium.connect_over_cdp(
                f"http://{opened.debugging_address}",
                timeout=20_000,
            )
        except Exception:
            # A failed CDP attach can terminate Playwright's shared driver process.
            # Do not reuse that dead process on the queue's automatic retry.
            await self._reset_playwright()
            raise
        contexts = browser.contexts
        if not contexts:
            raise RuntimeError("No browser context available")
        context = contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        return browser, context, page

    async def _append_log(
        self,
        run_id: str,
        run_item_id: str | None,
        level: str,
        message: str,
        node_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        await self._db(
            self.store.append_log,
            run_id=run_id,
            run_item_id=run_item_id,
            level=level,
            message=message,
            node_id=node_id,
            data=data,
        )

    async def _profile_field_get(self, profile_id: str, field: str) -> str | None:
        return await self._db(self.store.get_profile_field, profile_id, field)

    async def _profile_field_set(self, profile_id: str, field: str, value: str) -> None:
        await self._db(self.store.update_profile_field, profile_id, field, value)

    async def _profile_tag_get(self, profile_id: str) -> list[str]:
        raw = await self._profile_field_get(profile_id, "__tags")
        if not raw:
            return []
        return [t for t in raw.split(",") if t]

    async def _profile_tag_set(self, profile_id: str, tags: list[str]) -> None:
        await self._profile_field_set(profile_id, "__tags", ",".join(tags))

    async def _is_run_stopped(self, run_id: str) -> bool:
        return self._run_stop_flags.get(run_id, False)

    async def _saved_phone_variables(self, profile_id: str) -> dict[str, Any]:
        """Restore only an online, recent connection for this exact profile."""
        raw = await self._profile_field_get(profile_id, "__artemis_phone_connection")
        if not raw:
            return {}
        try:
            saved = json.loads(raw)
            serial = str(saved.get("serial") or "").strip()
            age = time.time() - float(saved.get("saved_at") or 0)
        except (ValueError, TypeError, AttributeError):
            return {}
        if saved.get("profile_id") != profile_id or not (0 <= age <= 2 * 60 * 60):
            return {}
        try:
            devices = await self.phone_workers.list_devices()
        except RuntimeError:
            return {}
        if not any(device.get("serial") == serial and device.get("state") == "device" for device in devices):
            return {}
        return {"artemis_phone": saved, "phone_connection": saved, "phone_serial": serial}

    async def _worker(self, item: TaskItem) -> dict[str, Any]:
        run_id = str(item.params["run_id"])
        sem = self._run_semaphores.get(run_id)
        if sem is None:
            return await self._worker_inner(item)
        async with sem:
            return await self._worker_inner(item)

    async def _worker_inner(self, item: TaskItem) -> dict[str, Any]:
        run_id = str(item.params["run_id"])
        run_item_id = str(item.params["run_item_id"])
        stop_on_error = bool(item.params.get("stop_on_error", False))
        timeout = float(item.params.get("timeout", 300))
        close_profile_on_finish = bool(item.params.get("close_profile_on_finish", False))

        if self._run_stop_flags.get(run_id, False):
            await self._db(
                self.store.upsert_run_item,
                run_id=run_id,
                run_item_id=run_item_id,
                profile_id=item.profile_id,
                status="cancelled",
                finished_at=time.time(),
                error="Run stop requested",
            )
            return {"cancelled": True}

        await self._db(
            self.store.upsert_run_item,
            run_id=run_id,
            run_item_id=run_item_id,
            profile_id=item.profile_id,
            status="running",
            started_at=time.time(),
        )

        opened: OpenResult | None = None
        browser: Browser | None = None
        try:
            opened = await self.profiles.open_profile(item.profile_id)
            browser, context, page = await self._connect_profile(opened)
            # IXBrowser may finish creating its visible Chromium window after
            # the API reports the profile as opened. Raise it again once CDP is
            # ready so each workflow run starts with the real profile onscreen.
            window_visible = await self.profiles.ensure_profile_window_visible(item.profile_id)
            if not window_visible:
                raise RuntimeError(
                    f"Could not bring browser profile {item.profile_id} to the screen; "
                    "workflow stopped before its first node."
                )
            compiled = self._compiled_by_run.get(run_id)
            if compiled is None:
                raise RuntimeError("Compiled graph not found for run")

            saved_phone_variables = (
                await self._saved_phone_variables(item.profile_id)
                if any(node.type.strip().lower().startswith("artemis") for node in compiled.nodes.values())
                else {}
            )

            async def _reconnect() -> tuple[Browser, BrowserContext, Page]:
                if opened is None:
                    raise RuntimeError("Cannot reconnect without open profile")
                return await self._connect_profile(opened)

            ctx = NodeExecutionContext(
                run_id=run_id,
                run_item_id=run_item_id,
                profile_id=item.profile_id,
                playwright=await self._ensure_playwright(),
                browser=browser,
                browser_context=context,
                active_page=page,
                profile_debug_url=f"http://{opened.debugging_address}",
                variables={
                    **saved_phone_variables,
                    **item.params.get("inputs", {}),
                    "profile_id": item.profile_id,
                    "profile_name": item.params.get("profile_name", ""),
                },
                secret_variables=set(compiled.secret_inputs),
                run_timeout=timeout,
                log=lambda level, message, node_id, data: self._append_log(
                    run_id, run_item_id, level, message, node_id, data
                ),
                should_stop=lambda: self._is_run_stopped(run_id),
                stop_event=self._run_stop_events.get(run_id),
                reconnect=_reconnect,
                profile_field_get=self._profile_field_get,
                profile_field_set=self._profile_field_set,
                profile_tag_get=self._profile_tag_get,
                profile_tag_set=self._profile_tag_set,
                phone_workers=self.phone_workers,
                image_asset_get=self.get_phone_image_asset,
                called_apps=self._called_by_run.get(run_id, {}),
                app_stack=[str(item.params.get("app_id") or "")],
            )
            result = await self.executor.execute_graph(compiled, ctx)
            if result.get("stopped"):
                await self._db(
                    self.store.upsert_run_item,
                    run_id=run_id,
                    run_item_id=run_item_id,
                    profile_id=item.profile_id,
                    status="cancelled",
                    finished_at=time.time(),
                    error="Run stopped by user",
                    result=result,
                )
                await self._append_log(
                    run_id,
                    run_item_id,
                    "warning",
                    "Profile run cancelled by user; no following node will run",
                    data={"profile_id": item.profile_id, "stopped": True},
                )
                return {**result, "cancelled": True}
            await self._db(
                self.store.upsert_run_item,
                run_id=run_id,
                run_item_id=run_item_id,
                profile_id=item.profile_id,
                status="done",
                finished_at=time.time(),
                result=result,
            )
            await self._append_log(
                run_id,
                run_item_id,
                "info",
                "Profile run completed",
                data={"profile_id": item.profile_id},
            )
            return result
        except Exception as exc:  # noqa: BLE001
            await self._db(
                self.store.upsert_run_item,
                run_id=run_id,
                run_item_id=run_item_id,
                profile_id=item.profile_id,
                status="failed",
                finished_at=time.time(),
                error=str(exc),
            )
            await self._append_log(
                run_id,
                run_item_id,
                "error",
                f"Profile run failed: {exc}",
                data={"profile_id": item.profile_id},
            )
            if stop_on_error:
                await self.stop_run(run_id)
            raise
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            if opened is not None:
                if close_profile_on_finish:
                    try:
                        await self.profiles.close_profile(item.profile_id)
                    except Exception:
                        pass
            await self._refresh_run_summary(run_id)
            await self._finish_run_if_needed(run_id)

    async def _refresh_run_summary(self, run_id: str, *, recover_stopped: bool = False) -> None:
        await self._db(self.store.refresh_run_summary, run_id, recover_stopped=recover_stopped)

    async def _finish_run_if_needed(self, run_id: str) -> None:
        run = await self._db(self.store.get_run, run_id)
        if run is None or run.get("finished_at") is None:
            return
        async with self._lock:
            self._compiled_by_run.pop(run_id, None)
            self._run_stop_flags.pop(run_id, None)
            self._run_stop_events.pop(run_id, None)
            self._run_configs.pop(run_id, None)
            self._run_semaphores.pop(run_id, None)
            self._run_task_ids.pop(run_id, None)

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                now_ts = time.time()
                due = await self._db(self.store.due_schedules, now_ts)
                for schedule in due:
                    task_id = schedule["task_id"]
                    task = await self.get_task(task_id)
                    if task is None:
                        continue
                    try:
                        run_req = RunRequest(
                            task_id=task_id,
                            inputs=schedule.get("input_overrides", {}),
                        )
                        await self.run(run_req)
                        await self._append_log(
                            run_id="scheduler",
                            run_item_id=None,
                            level="info",
                            message=f"Schedule triggered: {schedule['id']}",
                            data={"task_id": task_id},
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Schedule run failed: %s", schedule["id"])
                        await self._append_log(
                            run_id="scheduler",
                            run_item_id=None,
                            level="error",
                            message=f"Schedule failed: {exc}",
                            data={"schedule_id": schedule["id"]},
                        )

                    interval_seconds = schedule.get("interval_seconds")
                    if interval_seconds:
                        next_run_at = now_ts + int(interval_seconds)
                    else:
                        # Cron placeholder in v1: keep fixed minute cadence.
                        next_run_at = now_ts + 60
                    await self._db(
                        self.store.mark_schedule_run,
                        schedule["id"],
                        now_ts=now_ts,
                        next_run_at=next_run_at,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduler loop error")
            await asyncio.sleep(5)
