from __future__ import annotations

import asyncio
import base64
import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any

PHONE_WORKER_RESPONSE_LIMIT = 32 * 1024 * 1024


class PhoneBridgeWorker:
    def __init__(self, *, python: str, script: Path, artemis_root: Path, serial: str, adb_path: str) -> None:
        self.python = python
        self.script = script
        self.artemis_root = artemis_root
        self.serial = serial
        self.adb_path = adb_path
        self.process: asyncio.subprocess.Process | None = None
        self.lock = asyncio.Lock()
        self.last_used = time.monotonic()
        self.ready_info: dict[str, Any] = {"status": "connected", "serial": serial}
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_tail = bytearray()

    async def _capture_stderr(self, stream: asyncio.StreamReader) -> None:
        while chunk := await stream.read(4096):
            self._stderr_tail.extend(chunk)
            if len(self._stderr_tail) > 16 * 1024:
                del self._stderr_tail[:-16 * 1024]

    def _stderr_detail(self) -> str:
        lines = [line.strip() for line in self._stderr_tail.decode("utf-8", errors="replace").splitlines() if line.strip()]
        exception_lines = [
            line for line in lines
            if line.split(":", 1)[0].rsplit(".", 1)[-1].endswith(("Error", "Exception")) and ":" in line
        ]
        return (exception_lines[-1] if exception_lines else (lines[-1] if lines else ""))[:1000]

    async def start(self) -> dict[str, Any]:
        if self.process and self.process.returncode is None:
            return dict(self.ready_info)
        env = dict(__import__("os").environ)
        env["PYTHONUNBUFFERED"] = "1"
        # Samsung RTL monitors host ADB shell commands and can drop the RDB
        # bridge when a command is blocked. ARTEMIS' default awake policy sends
        # `svc power stayon`, key events and `wm dismiss-keyguard` on connect;
        # connecting the recorder/phone worker must remain observational and
        # must not issue those implicit device mutations.
        env["ARTEMIS_KEEP_DEVICE_AWAKE"] = "0"
        self.process = await asyncio.create_subprocess_exec(
            self.python, str(self.script), "--artemis-root", str(self.artemis_root),
            "--serial", self.serial, "--adb-path", self.adb_path,
            cwd=str(self.artemis_root), env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Phone screenshots and accessibility hierarchies travel as one
            # JSON line. asyncio's default 64 KiB limit truncates those replies
            # and makes a healthy ARTEMIS worker look like it crashed.
            limit=PHONE_WORKER_RESPONSE_LIMIT,
        )
        assert self.process.stderr is not None
        self._stderr_tail.clear()
        self._stderr_task = asyncio.create_task(self._capture_stderr(self.process.stderr))
        assert self.process.stdout is not None
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=180)
            if not line:
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass
                detail = self._stderr_detail()
                message = f"ARTEMIS phone worker exited before sending its ready response (exit code={self.process.returncode})."
                if detail:
                    message += f" Worker error: {detail}"
                raise RuntimeError(message)
            ready = json.loads(line.decode("utf-8"))
        except asyncio.TimeoutError as exc:
            await self.close()
            detail = self._stderr_detail()
            message = "ARTEMIS phone worker did not become ready within 180 seconds."
            if detail:
                message += f" Worker error: {detail}"
            raise RuntimeError(message) from exc
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception as exc:
            await self.close()
            detail = self._stderr_detail()
            message = str(exc)
            if detail and detail not in message:
                message += f" Worker error: {detail}"
            if not isinstance(exc, RuntimeError):
                message = f"ARTEMIS phone worker returned an invalid ready response: {message}"
            raise RuntimeError(message) from exc
        if not ready.get("ready"):
            detail = str(ready.get("error") or "ARTEMIS connection failed.")
            await self.close()
            raise RuntimeError(detail)
        result = ready.get("result", {})
        self.ready_info = result if isinstance(result, dict) else {"status": "connected", "serial": self.serial}
        self.last_used = time.monotonic()
        return dict(self.ready_info)

    async def connect(self) -> dict[str, Any]:
        """Start or reuse the phone session and return only its small ready summary."""
        async with self.lock:
            return await self.start()

    async def request(self, operation: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self.lock:
            if not self.process or self.process.returncode is not None:
                await self.start()
            assert self.process and self.process.stdin and self.process.stdout
            request_id = uuid.uuid4().hex
            payload = json.dumps({"id": request_id, "operation": operation, "config": config or {}}, ensure_ascii=False)
            self.process.stdin.write((payload + "\n").encode("utf-8"))
            await self.process.stdin.drain()
            read_task = asyncio.create_task(self.process.stdout.readline())
            try:
                line = await asyncio.wait_for(asyncio.shield(read_task), timeout=180)
                if not line:
                    exit_code = self.process.returncode
                    await self.close()
                    raise RuntimeError(
                        f"ARTEMIS phone worker closed its output before replying (exit code={exit_code})."
                    )
                response = json.loads(line.decode("utf-8"))
            except asyncio.CancelledError:
                # Closing a browser preview cancels its HTTP stream. Finish
                # consuming the outstanding worker reply under this lock so
                # the next command stays in sync; keep the phone connection.
                try:
                    await asyncio.wait_for(asyncio.shield(read_task), timeout=15)
                except Exception:
                    await self.close()
                raise
            except asyncio.LimitOverrunError as exc:
                await self.close()
                raise RuntimeError(
                    "ARTEMIS phone worker response exceeded the 32 MiB message limit."
                ) from exc
            except Exception as exc:
                if isinstance(exc, RuntimeError) and str(exc).startswith("ARTEMIS phone worker closed its output"):
                    raise
                await self.close()
                raise RuntimeError("ARTEMIS phone worker stopped while processing a command.") from exc
            if response.get("id") != request_id:
                await self.close()
                raise RuntimeError("ARTEMIS phone worker returned an out-of-order response.")
            self.last_used = time.monotonic()
            if not response.get("ok"):
                raise RuntimeError(str(response.get("error") or "ARTEMIS phone operation failed."))
            result = response.get("result")
            return result if isinstance(result, dict) else {"result": result}

    async def close(self) -> None:
        process, self.process = self.process, None
        if not process:
            return
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        if self._stderr_task:
            try:
                await asyncio.wait_for(self._stderr_task, timeout=1)
            except asyncio.TimeoutError:
                self._stderr_task.cancel()
                await asyncio.gather(self._stderr_task, return_exceptions=True)
            self._stderr_task = None


class PhoneWorkerPool:
    """Keeps one serialized ARTEMIS worker per exact ADB serial."""

    def __init__(self, artemis_root: str, python: str, adb_path: str) -> None:
        project_root = Path(__file__).resolve().parents[1]
        configured_root = str(artemis_root or "").strip()
        root = Path(configured_root).expanduser() if configured_root else project_root.parent / "artemis"
        if not root.is_absolute():
            root = (project_root / root).resolve()
        self.artemis_root = root

        configured_python = str(python or "").strip()
        python_path = Path(configured_python).expanduser() if configured_python else None
        if python_path and not python_path.is_absolute():
            python_path = (project_root / python_path).resolve()
        if python_path:
            self.python = str(python_path)
        else:
            candidates = [
                root / ".venv" / "Scripts" / "python.exe",
                root / "venv" / "Scripts" / "python.exe",
                root / ".venv" / "bin" / "python",
                root / "venv" / "bin" / "python",
            ]
            self.python = next((str(candidate) for candidate in candidates if candidate.is_file()), sys.executable)
        self.adb_path = str(adb_path or "").strip() or shutil.which("adb") or "adb"
        self.script = Path(__file__).resolve().parents[1] / "integrations" / "artemis" / "phone_worker.py"
        self._workers: dict[str, PhoneBridgeWorker] = {}
        self._lock = asyncio.Lock()

    async def get(self, serial: str) -> PhoneBridgeWorker:
        serial = str(serial or "").strip()
        if not serial or len(serial) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for c in serial):
            raise ValueError("A valid exact ADB serial is required.")
        async with self._lock:
            now = time.monotonic()
            expired = [key for key, worker in self._workers.items() if now - worker.last_used > 900 and not worker.lock.locked()]
            for key in expired:
                worker = self._workers.pop(key)
                asyncio.create_task(worker.close())
            worker = self._workers.get(serial)
            if worker is None:
                if len(self._workers) >= 4:
                    idle = sorted((w.last_used, key) for key, w in self._workers.items() if not w.lock.locked())
                    if not idle:
                        raise RuntimeError("All ARTEMIS phone connections are busy.")
                    _, key = idle[0]
                    old = self._workers.pop(key)
                    await old.close()
                worker = PhoneBridgeWorker(
                    python=self.python, script=self.script, artemis_root=self.artemis_root,
                    serial=serial, adb_path=self.adb_path,
                )
                self._workers[serial] = worker
            return worker

    async def request(self, serial: str, operation: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        worker = await self.get(serial)
        return await worker.request(operation, config)

    async def connect(self, serial: str) -> dict[str, Any]:
        worker = await self.get(serial)
        return await worker.connect()

    def has_live_worker(self, serial: str) -> bool:
        """Check the current in-process ARTEMIS session without starting or reconnecting it."""
        worker = self._workers.get(str(serial or "").strip())
        return bool(worker and worker.process and worker.process.returncode is None)

    async def list_devices(self) -> list[dict[str, str]]:
        import asyncio.subprocess

        adb = self.adb_path or shutil.which("adb") or "adb"
        proc = await asyncio.create_subprocess_exec(
            adb, "devices", "-l", stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode:
            raise RuntimeError("Could not query ADB devices. Verify the configured ADB path.")
        devices: list[dict[str, str]] = []
        for line in stdout.decode(errors="replace").splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2:
                devices.append({"serial": fields[0], "state": fields[1], "details": " ".join(fields[2:])})
        return devices

    async def close_all(self) -> None:
        workers = list(self._workers.values())
        self._workers.clear()
        await asyncio.gather(*(worker.close() for worker in workers), return_exceptions=True)


class PhoneRecorder:
    def __init__(self, store: Any, workers: PhoneWorkerPool) -> None:
        self.store = store
        self.workers = workers
        self._locks: dict[str, asyncio.Lock] = {}
        self._frames: dict[str, dict[str, dict[str, Any]]] = {}

    @staticmethod
    def _frame_for_ui(frame: dict[str, Any]) -> dict[str, Any]:
        image = frame.get("preview_image_base64") or frame.get("image_base64")
        mime_type = frame.get("preview_mime_type") or frame.get("image_mime_type") or "image/png"
        result = {key: value for key, value in frame.items()
                  if key not in {"elements", "image_base64", "preview_image_base64", "preview_mime_type"}}
        if image:
            result["image_base64"] = image
            result["image_mime_type"] = mime_type
        return result

    async def start(self, serial: str) -> dict[str, Any]:
        devices = await self.workers.list_devices()
        if not any(d["serial"] == serial and d["state"] == "device" for d in devices):
            raise ValueError(f"ADB serial {serial} is not connected and authorized.")
        connected = await self.workers.request(serial, "observe")
        session_id = uuid.uuid4().hex[:16]
        await asyncio.to_thread(self.store.create_phone_recording, session_id, serial)
        return {"id": session_id, "serial": serial, "status": "recording", "backend": connected.get("backend"),
                "width": connected.get("width"), "height": connected.get("height")}

    async def rebind(self, session_id: str, serial: str) -> dict[str, Any]:
        """Move a saved draft to a currently authorized device, preserving its events."""
        session = await self.get(session_id)
        if not session:
            raise ValueError("Phone recording session not found.")
        serial = str(serial or "").strip()
        if not serial:
            raise ValueError("Select an online ADB device first.")
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            session = await self.get(session_id)
            if not session:
                raise ValueError("Phone recording session not found.")
            if session["status"] == "recording":
                raise ValueError("Pause the phone recorder before changing its device.")
            if session["serial"] == serial:
                return session
            devices = await self.workers.list_devices()
            if not any(d["serial"] == serial and d["state"] == "device" for d in devices):
                raise ValueError(f"ADB serial {serial} is not connected and authorized.")
            # Verify ARTEMIS can read the selected device before changing the
            # saved binding. A failed probe leaves the draft and old serial intact.
            await self.workers.request(serial, "observe")
            await asyncio.to_thread(self.store.set_phone_recording_serial, session_id, serial)
            self._frames.pop(session_id, None)
            rebound = await self.get(session_id)
            if not rebound:
                raise ValueError("Phone recording session not found after changing its device.")
            return rebound

    async def get(self, session_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self.store.get_phone_recording, session_id)

    async def list(self, limit: int = 50) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.store.list_phone_recordings, limit)

    async def frame(self, session_id: str) -> dict[str, Any]:
        session = await self.get(session_id)
        if not session:
            raise ValueError("Phone recording session not found.")
        result = await self.workers.request(session["serial"], "observe")
        frame_id = uuid.uuid4().hex
        frames = self._frames.setdefault(session_id, {})
        frames[frame_id] = {"id": frame_id, "captured_at": time.monotonic(), **result}
        while len(frames) > 8:
            frames.pop(next(iter(frames)))
        return {"frame_id": frame_id, **self._frame_for_ui(result)}

    async def action(self, session_id: str, action: dict[str, Any]) -> dict[str, Any]:
        session = await self.get(session_id)
        if not session:
            raise ValueError("Phone recording session not found.")
        if session["status"] != "recording":
            raise ValueError("Resume the phone recorder before sending actions.")
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            started = time.monotonic()
            frames = self._frames.setdefault(session_id, {})
            latest = next(reversed(frames.values()), None) if frames else None
            if latest and latest.get("serial") == session["serial"] and time.monotonic() - latest.get("captured_at", 0) <= 0.75:
                before = latest
            else:
                before = await self.workers.request(session["serial"], "observe")
                before["captured_at"] = time.monotonic()
            before_ms = round((time.monotonic() - started) * 1000)
            operation = str(action.get("type", ""))
            config = dict(action)
            config.pop("type", None)
            if operation in {"tap", "long_press", "double_tap"}:
                result = await self.workers.request(session["serial"], operation, config)
            elif operation in {"swipe", "send_text", "clear_text", "set_clipboard", "press_key"}:
                result = await self.workers.request(session["serial"], operation, config)
            else:
                raise ValueError("Unsupported recorder action.")
            input_ms = round((time.monotonic() - started) * 1000) - before_ms
            event_config = {k: v for k, v in config.items() if k not in {"value", "text", "secret"}}
            event: dict[str, Any] = {"type": operation, "config": event_config,
                     "result": result, "created_at": time.time(), "width": before.get("width"), "height": before.get("height")}
            if operation in {"tap", "long_press", "double_tap"}:
                point = (int(config.get("x", -1)), int(config.get("y", -1)))
                candidate = self._element_at(before.get("elements", []), point)
                if candidate:
                    event["selector"] = candidate["selector"]
                    event["selector_unique"] = candidate["unique"]
                    event["element"] = candidate["element"]
                    bounds = candidate["bounds"]
                else:
                    bounds = (point[0] - 64, point[1] - 48, point[0] + 64, point[1] + 48)
                event["target_bounds"] = list(bounds)
                crop = await self._element_crop(before, bounds)
                if crop:
                    event["image_asset_id"] = crop
            if operation == "send_text":
                variable = str(config.get("variable_name", "")).strip()
                secret = bool(config.get("secret")) or self._focused_sensitive_input(before.get("elements", []))
                if secret:
                    event["secret"] = True
                    event["text_variable"] = variable or f"phone_secret_{len(session.get('events', [])) + 1}"
                else:
                    event["text"] = str(config.get("value", ""))
            event_id = await asyncio.to_thread(self.store.append_phone_recording_event, session_id, event)
            frame_id = uuid.uuid4().hex
            frames[frame_id] = {"id": frame_id, **before}
            while len(frames) > 8:
                frames.pop(next(iter(frames)))
            return {"event_id": event_id, "event": event, "before_frame_id": frame_id,
                    "before": self._frame_for_ui(before), "after": result,
                    "timings": {"before_ms": before_ms, "input_ms": input_ms,
                                "total_ms": round((time.monotonic() - started) * 1000)}}

    @staticmethod
    def _focused_sensitive_input(elements: list[dict[str, Any]]) -> bool:
        def truthy(value: Any) -> bool:
            return value is True or str(value or "").strip().lower() in {"1", "true", "yes"}

        for element in elements:
            if not isinstance(element, dict):
                continue
            focused = any(truthy(element.get(key)) for key in ("focused", "is-focused", "isFocused", "accessibility-focused"))
            if not focused:
                continue
            details = " ".join(str(element.get(key) or "") for key in (
                "class", "input-type", "inputType", "autofill-hints", "autofillHints", "hint", "content-desc",
            )).casefold()
            password = any(truthy(element.get(key)) for key in ("password", "is-password", "isPassword"))
            if password or any(token in details for token in ("password", "one-time-code", "one time code", "otp", "verification code")):
                return True
        return False

    @staticmethod
    def _element_at(elements: list[dict[str, Any]], point: tuple[int, int]) -> dict[str, Any] | None:
        x, y = point
        matches: list[tuple[int, dict[str, Any], tuple[int, int, int, int], str, str]] = []
        for element in elements:
            raw = element.get("parsed_bounds")
            bounds = None
            if isinstance(raw, dict):
                try:
                    bounds = tuple(int(raw[k]) for k in ("left", "top", "right", "bottom"))
                except (KeyError, TypeError, ValueError):
                    pass
            if not bounds:
                text = str(element.get("bounds") or "")
                try:
                    a, b = text.strip("[]").split("][", 1)
                    bounds = (*map(int, a.split(",")), *map(int, b.split(",")))
                except (ValueError, TypeError):
                    continue
            left, top, right, bottom = bounds
            if not (left <= x <= right and top <= y <= bottom):
                continue
            by, selector = "", ""
            if element.get("resource-id"):
                by, selector = "resource_id", str(element["resource-id"])
            elif element.get("content-desc"):
                by, selector = "content_desc", str(element["content-desc"])
            elif element.get("text"):
                by, selector = "text", str(element["text"])
            matches.append(((right-left)*(bottom-top), element, bounds, by, selector))
        if not matches:
            return None
        matches.sort(key=lambda x: x[0])
        _, element, bounds, by, selector = matches[0]
        count = sum(1 for item in elements if selector and str(item.get({"resource_id":"resource-id","content_desc":"content-desc"}.get(by, by)) or "") == selector)
        return {"element": {k: element.get(k) for k in ("text", "content-desc", "resource-id", "class", "clickable", "password") if element.get(k) not in (None, "")},
                "bounds": bounds, "selector": {"by": by, "value": selector}, "unique": bool(selector and count == 1)}

    async def _element_crop(self, frame: dict[str, Any], bounds: tuple[int, int, int, int]) -> str | None:
        import cv2
        import numpy as np

        try:
            encoded = str(frame["image_base64"]).split(",", 1)[-1]
            image = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return None
        except Exception:
            return None
        left, top, right, bottom = bounds
        pad_x = max(8, int((right-left) * 0.08))
        pad_y = max(8, int((bottom-top) * 0.08))
        height, width = image.shape[:2]
        box = (max(0, left-pad_x), max(0, top-pad_y), min(width, right+pad_x), min(height, bottom+pad_y))
        if box[2]-box[0] < 12 or box[3]-box[1] < 12:
            return None
        ok, encoded_crop = cv2.imencode(".png", image[box[1]:box[3], box[0]:box[2]])
        if not ok:
            return None
        return await asyncio.to_thread(self.store.put_phone_image_asset, encoded_crop.tobytes(), "Recorded phone target")

    async def mark_segment(self, session_id: str, name: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.store.append_phone_recording_segment, session_id, name)

    async def crop(self, session_id: str, frame_id: str, box: dict[str, Any], name: str = "Phone image") -> dict[str, Any]:
        frame = self._frames.get(session_id, {}).get(frame_id)
        if not frame:
            raise ValueError("The phone preview changed; capture a fresh frame before cropping.")
        import cv2
        import numpy as np
        raw = base64.b64decode(str(frame["image_base64"]).split(",", 1)[-1])
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode the selected phone frame.")
        h, w = image.shape[:2]
        x = max(0, min(w - 1, int(float(box.get("x", 0)) * w)))
        y = max(0, min(h - 1, int(float(box.get("y", 0)) * h)))
        right = max(x + 8, min(w, int(float(box.get("right", 1)) * w)))
        bottom = max(y + 8, min(h, int(float(box.get("bottom", 1)) * h)))
        if right - x < 12 or bottom - y < 12:
            raise ValueError("Crop a larger, distinctive phone screen area.")
        ok, encoded_crop = cv2.imencode(".png", image[y:bottom, x:right])
        if not ok:
            raise ValueError("Could not encode the selected phone image crop.")
        data = encoded_crop.tobytes()
        asset_id = await asyncio.to_thread(self.store.put_phone_image_asset, data, name)
        return {"asset_id": asset_id, "width": right - x, "height": bottom - y}

    async def match_asset(
        self, serial: str, asset_id: str, options: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if session_id:
            session = await self.get(session_id)
            if not session or session["serial"] != serial:
                raise ValueError("Recording session does not match the selected ADB serial.")
        asset = await asyncio.to_thread(self.store.get_phone_image_asset, asset_id)
        if not asset:
            raise ValueError("Phone image asset not found.")
        payload = dict(options or {})
        payload.update({
            "template_base64": base64.b64encode(bytes(asset["data"])).decode("ascii"),
            "template_sha256": asset["sha256"],
            "include_preview": True,
        })
        result = await self.workers.request(serial, "find_image", payload)
        if session_id and result.get("preview_image_base64"):
            frame_id = uuid.uuid4().hex
            frame = {
                "id": frame_id, "frame_id": frame_id, "serial": serial,
                "backend": "ARTEMIS Accessibility Helper / UIAutomator2",
                "image_base64": result["preview_image_base64"],
                "width": result["width"], "height": result["height"],
            }
            frames = self._frames.setdefault(session_id, {})
            frames[frame_id] = frame
            while len(frames) > 8:
                frames.pop(next(iter(frames)))
            result["frame_id"] = frame_id
        return result

    async def delete(self, session_id: str) -> bool:
        self._frames.pop(session_id, None)
        self._locks.pop(session_id, None)
        return await asyncio.to_thread(self.store.delete_phone_recording, session_id)

    async def set_status(self, session_id: str, status: str) -> dict[str, Any]:
        if status not in {"paused", "recording", "stopped"}:
            raise ValueError("Invalid recorder status.")
        await asyncio.to_thread(self.store.set_phone_recording_status, session_id, status)
        session = await self.get(session_id)
        if not session:
            raise ValueError("Phone recording session not found.")
        if status == "stopped":
            self._frames.pop(session_id, None)
        return session
