"""FastAPI server for classic templates and full no-code automation runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from automation import (
    AutomationService,
    CreateAppRequest,
    CreateSavedTaskRequest,
    CreateScheduleRequest,
    RunRequest,
    UpdateAppRequest,
    UpdateSavedTaskRequest,
    UpdateScheduleRequest,
    node_catalog,
)
from automation.apk_installer import APK_DIR, MAX_APK_BYTES, apk_asset_path, validate_apk
from config.settings import BASE_DIR, settings
from core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

orchestrator = Orchestrator()
automation_service = AutomationService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await orchestrator.start()
    await automation_service.start()
    await automation_service.apply_extension_settings_to_profile_manager(orchestrator.profiles)
    yield
    await automation_service.stop()
    await orchestrator.stop()


app = FastAPI(title="IXBrowser Automation", version="2.0.0", lifespan=lifespan)

UI_DIR = BASE_DIR / "ui" / "automation"
if UI_DIR.exists():
    app.mount("/automation-ui", StaticFiles(directory=str(UI_DIR)), name="automation-ui")


def _ensure_token(authorization: str | None) -> None:
    expected = settings.api_bearer_token.strip()
    if not expected:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid API token")


async def require_token(authorization: str | None = Header(default=None)) -> None:
    _ensure_token(authorization)


class ExecuteRequest(BaseModel):
    platform: str = Field(..., description="x | facebook | tiktok | generic")
    task_type: str = Field(..., description="post_tweet, like_tweet, warm_up, custom")
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
    tasks: list[dict[str, Any]] = Field(default_factory=list)


class ExtensionImportUrlRequest(BaseModel):
    url: str = Field(..., min_length=1)


class IxPayload(BaseModel):
    model_config = {"extra": "allow"}


# ---- Legacy API (kept for compatibility) ----
@app.post("/tasks/execute", response_model=dict)
async def execute_task(req: ExecuteRequest, _: None = Depends(require_token)):
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
async def get_batch_status(batch_id: str, _: None = Depends(require_token)):
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
    _: None = Depends(require_token),
):
    profiles = await orchestrator.profiles.list_profiles(
        group_id=group_id,
        tag_id=tag_id,
        page=page,
        limit=limit,
    )
    return {
        "count": len(profiles),
        "profiles": [{"profile_id": p.profile_id, "name": p.name, "tags": p.tags} for p in profiles],
    }


@app.get("/profiles/groups")
async def list_groups(_: None = Depends(require_token)):
    return await orchestrator.profiles.list_groups()


@app.get("/profiles/tags")
async def list_tags(_: None = Depends(require_token)):
    return await orchestrator.profiles.list_tags()


# ---- IXBrowser Local API facade ----
@app.get("/ix/profiles")
async def ix_list_profiles(
    keyword: str | None = None,
    group_id: int = 0,
    tag_id: int = 0,
    profile_id: int = 0,
    page: int = 1,
    limit: int = 50,
    _: None = Depends(require_token),
):
    return await orchestrator.profiles.list_profiles_raw(
        keyword=keyword,
        group_id=group_id,
        tag_id=tag_id,
        profile_id=profile_id,
        page=page,
        limit=limit,
    )


@app.get("/ix/profiles/opened")
async def ix_list_opened_profiles(_: None = Depends(require_token)):
    try:
        return {"profiles": await orchestrator.profiles.get_opened_list()}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ix/profiles")
async def ix_create_profile(req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.create_profile(req.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/ix/profiles/{profile_id}")
async def ix_update_profile(profile_id: str, req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.update_profile(profile_id, req.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/ix/profiles/{profile_id}")
async def ix_delete_profile(profile_id: str, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.delete_profile(profile_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ix/profiles/{profile_id}/open")
async def ix_open_profile(profile_id: str, _: None = Depends(require_token)):
    try:
        opened = await orchestrator.profiles.open_profile(profile_id)
        return {"profile_id": opened.profile_id, "webdriver": opened.webdriver, "debugging_address": opened.debugging_address, "raw": opened.raw}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ix/profiles/{profile_id}/close")
async def ix_close_profile(profile_id: str, _: None = Depends(require_token)):
    try:
        await orchestrator.profiles.close_profile(profile_id)
        return {"closed": True, "profile_id": profile_id}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ix/profiles/{profile_id}/copy")
async def ix_copy_profile(
    profile_id: str,
    req: IxPayload | None = None,
    _: None = Depends(require_token),
):
    try:
        return await orchestrator.profiles.copy_profile(
            profile_id,
            req.model_dump(mode="json") if req else {},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ix/profiles/{profile_id}/random-fingerprint")
async def ix_random_profile_fingerprint(profile_id: str, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.random_profile_fingerprint(profile_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/ix/profiles/{profile_id}/proxy/custom")
async def ix_update_profile_custom_proxy(profile_id: str, req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.update_profile_custom_proxy(
            profile_id,
            req.model_dump(mode="json"),
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/ix/profiles/{profile_id}/proxy/purchased")
async def ix_update_profile_purchased_proxy(profile_id: str, req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.update_profile_purchased_proxy(
            profile_id,
            req.model_dump(mode="json"),
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/ix/proxies")
async def ix_list_proxies(
    mode: int = 0,
    tag_id: int | None = None,
    page: int = 1,
    limit: int = 50,
    _: None = Depends(require_token),
):
    return await orchestrator.profiles.list_proxies_raw(
        mode=mode,
        tag_id=tag_id,
        page=page,
        limit=limit,
    )


@app.post("/ix/proxies")
async def ix_create_proxy(req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.create_proxy(req.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/ix/proxies/{proxy_id}")
async def ix_update_proxy(proxy_id: str, req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.update_proxy(proxy_id, req.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/ix/proxies/{proxy_id}")
async def ix_delete_proxy(
    proxy_id: str,
    detach_profiles: bool = False,
    _: None = Depends(require_token),
):
    try:
        return await orchestrator.profiles.delete_proxy(
            proxy_id,
            detach_profiles=detach_profiles,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/ix/proxies/{proxy_id}/profiles")
async def ix_profiles_using_proxy(proxy_id: str, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.profiles_using_proxy(proxy_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/ix/proxy-tags")
async def ix_list_proxy_tags(
    name: str | None = None,
    page: int = 1,
    limit: int = 100,
    _: None = Depends(require_token),
):
    return await orchestrator.profiles.list_proxy_tags(name=name, page=page, limit=limit)


@app.post("/ix/proxy-tags")
async def ix_create_proxy_tag(req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.create_proxy_tag(req.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/ix/proxy-tags/{tag_id}")
async def ix_update_proxy_tag(tag_id: str, req: IxPayload, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.update_proxy_tag(tag_id, req.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/ix/proxy-tags/{tag_id}")
async def ix_delete_proxy_tag(tag_id: str, _: None = Depends(require_token)):
    try:
        return await orchestrator.profiles.delete_proxy_tag(tag_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/templates")
async def list_templates(_: None = Depends(require_token)):
    return {
        platform: orchestrator.registry.task_types(platform)
        for platform in orchestrator.registry.platforms
    }


@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket):
    try:
        _ensure_token(websocket.headers.get("authorization"))
    except HTTPException:
        await websocket.close(code=4401, reason="Unauthorized")
        return
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


@app.get("/automation/ui")
async def automation_ui():
    index_path = UI_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Automation UI not found")
    return FileResponse(index_path)


@app.get("/automation/catalog")
async def automation_catalog(_: None = Depends(require_token)):
    return {"categories": node_catalog()}


@app.get("/automation/extensions/config")
async def get_extension_config(_: None = Depends(require_token)):
    return await automation_service.get_extension_settings()


@app.put("/automation/extensions/config")
async def update_extension_config(payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        cfg = await automation_service.update_extension_settings(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    orchestrator.profiles.set_open_profile_options(
        automation_service.extension_open_profile_options(cfg)
    )
    return cfg


@app.post("/automation/extensions/upload")
async def upload_extension_file(
    file: UploadFile = File(...),
    _: None = Depends(require_token),
):
    filename = str(file.filename or "extension.zip").strip() or "extension.zip"
    blob = await file.read()
    if len(blob) > 80 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Extension package is too large (max 80MB)")
    try:
        cfg = await automation_service.upload_extension_and_add(filename, blob)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    orchestrator.profiles.set_open_profile_options(
        automation_service.extension_open_profile_options(cfg)
    )
    return cfg


@app.post("/automation/extensions/import-url")
async def import_extension_url(req: ExtensionImportUrlRequest, _: None = Depends(require_token)):
    try:
        cfg = await automation_service.import_extension_url_and_add(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    orchestrator.profiles.set_open_profile_options(
        automation_service.extension_open_profile_options(cfg)
    )
    return cfg


# ---- Automation API ----
@app.post("/automation/apps")
async def create_app(req: CreateAppRequest, _: None = Depends(require_token)):
    try:
        return await automation_service.create_app(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/automation/apps")
async def list_apps(_: None = Depends(require_token)):
    return await automation_service.list_apps()


@app.get("/automation/apps/{app_id}")
async def get_app(app_id: str, _: None = Depends(require_token)):
    app_obj = await automation_service.get_app(app_id)
    if app_obj is None:
        raise HTTPException(status_code=404, detail="App not found")
    return app_obj


@app.put("/automation/apps/{app_id}")
async def update_app(app_id: str, req: UpdateAppRequest, _: None = Depends(require_token)):
    try:
        updated = await automation_service.update_app(app_id, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="App not found")
    return updated


@app.delete("/automation/apps/{app_id}")
async def delete_app(app_id: str, _: None = Depends(require_token)):
    try:
        deleted = await automation_service.delete_app(app_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="App not found")
    return {"deleted": True}


@app.get("/automation/apps/{app_id}/bundle")
async def export_app_bundle(app_id: str, _: None = Depends(require_token)):
    try:
        data = await automation_service.export_app_bundle(app_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="autoixb-{app_id}.zip"'},
    )


@app.post("/automation/apps/import-bundle")
async def import_app_bundle(file: UploadFile = File(...), _: None = Depends(require_token)):
    data = await file.read(100 * 1024 * 1024 + 1)
    try:
        result = await automation_service.import_app_bundle(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"root": result["root"], "apps": result["apps"], "asset_count": result["asset_count"]}


@app.post("/automation/phone/apks")
async def upload_phone_apk(file: UploadFile = File(...), _: None = Depends(require_token)):
    """Copy a browser-selected APK to durable server storage for a phone node."""
    from pathlib import Path

    name = Path(str(file.filename or "").replace("\\", "/")).name
    if not name.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Choose an .apk file")
    APK_DIR.mkdir(parents=True, exist_ok=True)
    temporary = APK_DIR / f".{uuid.uuid4().hex}.apk"
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_APK_BYTES:
                    raise HTTPException(status_code=413, detail="APK exceeds the 500 MB limit")
                digest.update(chunk)
                target.write(chunk)
        try:
            validate_apk(temporary)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        asset_id = digest.hexdigest()
        saved = apk_asset_path(asset_id)
        if saved.exists():
            temporary.unlink()
        else:
            temporary.replace(saved)
        return {"asset_id": asset_id, "name": name, "path": str(saved), "size": size}
    finally:
        temporary.unlink(missing_ok=True)
        await file.close()


@app.get("/automation/phone/devices")
async def list_phone_devices(_: None = Depends(require_token)):
    try:
        return {"devices": await automation_service.phone_workers.list_devices()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/automation/phone/recordings")
async def list_phone_recordings(_: None = Depends(require_token)):
    return await automation_service.phone_recorder.list()


@app.delete("/automation/phone/recordings/{session_id}")
async def delete_phone_recording(session_id: str, _: None = Depends(require_token)):
    if not await automation_service.phone_recorder.delete(session_id):
        raise HTTPException(status_code=404, detail="Phone recording session not found")
    return {"deleted": True}


@app.get("/automation/phone/assets")
async def list_phone_assets(_: None = Depends(require_token)):
    return await automation_service.list_phone_image_assets()


@app.post("/automation/phone/recordings")
async def start_phone_recording(payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.start(str(payload.get("serial", "")))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/automation/phone/recordings/{session_id}")
async def get_phone_recording(session_id: str, _: None = Depends(require_token)):
    recording = await automation_service.phone_recorder.get(session_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Phone recording session not found")
    return recording


@app.put("/automation/phone/recordings/{session_id}/device")
async def rebind_phone_recording_device(session_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.rebind(session_id, str(payload.get("serial", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/automation/phone/recordings/{session_id}/frame")
async def get_phone_recording_frame(session_id: str, _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.frame(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/automation/phone/recordings/{session_id}/stream")
async def stream_phone_recording_frames(
    session_id: str, request: Request, _: None = Depends(require_token),
):
    if await automation_service.phone_recorder.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Phone recording session not found")

    async def frames():
        sequence = 0
        while not await request.is_disconnected():
            started = time.monotonic()
            try:
                frame = await automation_service.phone_recorder.frame(session_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
                break
            sequence += 1
            yield json.dumps({
                "type": "frame", "sequence": sequence, "frame": frame,
                "capture_ms": round((time.monotonic() - started) * 1000),
            }, separators=(",", ":")) + "\n"
            # ARTEMIS captures on the device. Bound the rate and give input
            # commands a chance to acquire the shared phone worker.
            await asyncio.sleep(max(0.15, 0.5 - (time.monotonic() - started)))

    return StreamingResponse(
        frames(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/automation/phone/recordings/{session_id}/actions")
async def record_phone_action(session_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.action(session_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/automation/phone/recordings/{session_id}/crop")
async def crop_phone_image(session_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        result = await automation_service.phone_recorder.crop(
            session_id, str(payload.get("frame_id", "")), payload.get("box", {}),
            str(payload.get("name", "Phone image")),
        )
        event_index = payload.get("event_index")
        if event_index is not None:
            event = await automation_service._db(
                automation_service.store.update_phone_recording_event,
                session_id, int(event_index), {"image_asset_id": result["asset_id"]},
            )
            result["event"] = event
        else:
            await automation_service._db(
                automation_service.store.attach_phone_recording_asset,
                session_id, result["asset_id"],
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/automation/phone/recordings/{session_id}/segments")
async def mark_phone_recording_segment(session_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.mark_segment(session_id, str(payload.get("name", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/automation/phone/recordings/{session_id}/status")
async def update_phone_recording_status(session_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.set_status(session_id, str(payload.get("status", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/automation/phone/recordings/{session_id}/generate")
async def generate_phone_recording_apps(session_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.generate_phone_recording(
            session_id, parent_name=str(payload.get("name", "Recorded phone workflow")),
            repeat_count=int(payload.get("repeat_count", 1)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/automation/phone/assets/{asset_id}")
async def get_phone_image_asset(asset_id: str, _: None = Depends(require_token)):
    asset = await automation_service.get_phone_image_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Phone image asset not found")
    return Response(content=bytes(asset["data"]), media_type=asset["mime_type"], headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.post("/automation/phone/assets/{asset_id}/match")
async def match_phone_image_asset(asset_id: str, payload: dict[str, Any], _: None = Depends(require_token)):
    try:
        return await automation_service.phone_recorder.match_asset(
            str(payload.get("serial", "")), asset_id, payload.get("options") or {},
            str(payload.get("recording_id") or "") or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/automation/tasks")
async def create_saved_task(req: CreateSavedTaskRequest, _: None = Depends(require_token)):
    try:
        return await automation_service.create_task(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/automation/tasks")
async def list_saved_tasks(_: None = Depends(require_token)):
    return await automation_service.list_tasks()


@app.get("/automation/tasks/{task_id}")
async def get_saved_task(task_id: str, _: None = Depends(require_token)):
    task = await automation_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/automation/tasks/{task_id}")
async def update_saved_task(
    task_id: str,
    req: UpdateSavedTaskRequest,
    _: None = Depends(require_token),
):
    existing = await automation_service.get_task(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")
    cfg = dict(existing["config"])
    payload = req.model_dump(exclude_none=True, mode="json")
    task_name = payload.pop("name", None)
    cfg.update(payload)
    updated = await automation_service.update_task(task_id, name=task_name, config=cfg)
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated


@app.delete("/automation/tasks/{task_id}")
async def delete_saved_task(task_id: str, _: None = Depends(require_token)):
    deleted = await automation_service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}


@app.post("/automation/tasks/{task_id}/run")
async def run_saved_task(
    task_id: str,
    body: dict[str, Any] | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: None = Depends(require_token),
):
    body = body or {}
    try:
        req = RunRequest(task_id=task_id, **body)
        return await automation_service.run(req, idempotency_key=idempotency_key)
    except ValueError as exc:
        status_code = 409 if "Idempotency-Key" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc))


@app.post("/automation/runs")
async def run_app(
    req: RunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: None = Depends(require_token),
):
    try:
        return await automation_service.run(req, idempotency_key=idempotency_key)
    except ValueError as exc:
        status_code = 409 if "Idempotency-Key" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc))


@app.get("/automation/runs")
async def list_runs(limit: int = 100, _: None = Depends(require_token)):
    return await automation_service.list_runs(limit=limit)


@app.get("/automation/runs/{run_id}")
async def get_run(run_id: str, _: None = Depends(require_token)):
    run_obj = await automation_service.get_run(run_id)
    if run_obj is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_obj


@app.get("/automation/runs/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    after_id: int = 0,
    limit: int = 200,
    _: None = Depends(require_token),
):
    run_obj = await automation_service.get_run(run_id)
    if run_obj is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return await automation_service.get_run_logs(run_id, after_id=after_id, limit=limit)


@app.post("/automation/runs/{run_id}/stop")
async def stop_run(run_id: str, _: None = Depends(require_token)):
    try:
        return await automation_service.stop_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/automation/schedules")
async def create_schedule(req: CreateScheduleRequest, _: None = Depends(require_token)):
    try:
        return await automation_service.create_schedule(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/automation/schedules")
async def list_schedules(_: None = Depends(require_token)):
    return await automation_service.list_schedules()


@app.put("/automation/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    req: UpdateScheduleRequest,
    _: None = Depends(require_token),
):
    updated = await automation_service.update_schedule(schedule_id, req)
    if updated is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated


@app.delete("/automation/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, _: None = Depends(require_token)):
    deleted = await automation_service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"deleted": True}


@app.websocket("/ws/automation/runs/{run_id}")
async def ws_automation_run(websocket: WebSocket, run_id: str):
    try:
        _ensure_token(websocket.headers.get("authorization"))
    except HTTPException:
        await websocket.close(code=4401, reason="Unauthorized")
        return
    run_obj = await automation_service.get_run(run_id)
    if run_obj is None:
        await websocket.close(code=4404, reason="Run not found")
        return
    await websocket.accept()
    last_log_id = 0
    try:
        while True:
            run_obj = await automation_service.get_run(run_id)
            if run_obj is None:
                await websocket.send_json({"event": "run_deleted"})
                return
            logs = await automation_service.get_run_logs(run_id, after_id=last_log_id, limit=200)
            if logs:
                last_log_id = logs[-1]["id"]
            await websocket.send_json({"event": "state", "run": run_obj, "logs": logs})
            if run_obj["status"] in {"done", "failed", "cancelled"}:
                await asyncio.sleep(1)
                await websocket.send_json({"event": "completed", "status": run_obj["status"]})
                return
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
