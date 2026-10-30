"""Long lived, JSON-lines phone worker for autoIXB's ARTEMIS integration."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from typing import Any


def _png_base64(image: Any) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _screen_png_base64(encoded: str) -> tuple[str, int, int]:
    import cv2
    import numpy as np

    raw = base64.b64decode(str(encoded).split(",", 1)[-1])
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Could not decode the phone screenshot.")
    ok, png = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode the phone screenshot as PNG.")
    return base64.b64encode(png.tobytes()).decode("ascii"), int(image.shape[1]), int(image.shape[0])


def _screen_preview(encoded: str, max_edge: int = 1440, quality: int = 82) -> tuple[str, str, int, int]:
    """Keep the source frame for crops, and return a compact JPEG for live preview."""
    import cv2
    import numpy as np

    payload = str(encoded).split(",", 1)[-1]
    raw = base64.b64decode(payload)
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Could not decode the phone screenshot.")
    height, width = image.shape[:2]
    scale = min(1.0, float(max_edge) / max(width, height))
    if scale < 1.0:
        image = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    ok, preview = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("Could not encode the phone preview.")
    return payload, base64.b64encode(preview.tobytes()).decode("ascii"), int(width), int(height)


def _bounds(element: dict[str, Any]) -> tuple[int, int, int, int] | None:
    raw = element.get("parsed_bounds")
    if isinstance(raw, dict):
        try:
            return tuple(int(raw[k]) for k in ("left", "top", "right", "bottom"))
        except (KeyError, TypeError, ValueError):
            pass
    text = str(element.get("bounds") or "")
    try:
        left_top, right_bottom = text.strip("[]").split("][", 1)
        left, top = (int(x) for x in left_top.split(",", 1))
        right, bottom = (int(x) for x in right_bottom.split(",", 1))
        return left, top, right, bottom
    except (ValueError, TypeError):
        return None


class PhoneWorker:
    def __init__(self, serial: str, adb_path: str = "") -> None:
        self.serial = serial
        if adb_path:
            os.environ["ARTEMIS_ADB_PATH"] = adb_path
        os.environ["ARTEMIS_HIERARCHY_BACKEND"] = "auto"
        self.client: Any = None
        self.templates: dict[str, Any] = {}

    def connect(self) -> dict[str, Any]:
        root = os.environ.get("AUTOIXB_ARTEMIS_ROOT", "")
        if root and root not in sys.path:
            sys.path.insert(0, root)
        from artemis.clients.screen_client_factory import create_screen_client, describe_backend

        self.client = create_screen_client(self.serial, backend="auto")
        self.client.connect()
        data = self.client.get_screen_data()
        elements = list(getattr(data, "elements", []) or [])
        return {
            "serial": self.serial,
            "backend": describe_backend(self.client),
            "width": int(data.width),
            "height": int(data.height),
            "element_count": len(elements),
            "status": "connected",
        }

    def _screen_data(self) -> Any:
        if self.client is None:
            self.connect()
        return self.client.get_screen_data()

    def _input(self, action: str, **payload: Any) -> Any:
        backend = getattr(self.client, "active_backend", None) or "helper"
        if backend == "helper":
            client = getattr(self.client, "helper", self.client)
            method = getattr(client, action)
            if action == "tap":
                return method(payload["x"], payload["y"])
            if action == "swipe":
                return method(
                    payload["x1"], payload["y1"], payload["x2"], payload["y2"],
                    duration_ms=payload.get("duration_ms", 350),
                )
            if action in {"send_text", "set_clipboard"}:
                return method(payload.get("value", ""))
            if action == "clear_text":
                return method()
            return method(payload.get("key", "BACK"))

        client = getattr(self.client, "uiautomator", self.client)
        device = client._ensure_connected()
        if action == "tap":
            return device.click(payload["x"], payload["y"])
        if action == "swipe":
            return device.swipe(
                payload["x1"], payload["y1"], payload["x2"], payload["y2"],
                duration=payload.get("duration_ms", 350) / 1000,
            )
        if action == "send_text":
            return client.send_text(payload.get("value", ""))
        if action == "clear_text":
            return client.clear_text()
        if action == "press_key":
            return client.press_key(payload.get("key", "BACK"))
        if action == "set_clipboard":
            return client.set_clipboard(payload.get("value", ""))
        raise ValueError(f"Unsupported phone input action: {action}")

    def _match_image(self, cfg: dict[str, Any]) -> dict[str, Any]:
        import cv2
        import numpy as np

        started = time.perf_counter()
        data = self._screen_data()
        screenshot_bytes = base64.b64decode(str(data.base64).split(",", 1)[-1])
        screen_color = cv2.imdecode(np.frombuffer(screenshot_bytes, np.uint8), cv2.IMREAD_COLOR)
        if screen_color is None:
            raise RuntimeError("Could not decode the phone screenshot.")
        screen = cv2.cvtColor(screen_color, cv2.COLOR_BGR2GRAY)
        captured_at = time.perf_counter()
        source = str(cfg.get("template_base64", ""))
        if not source:
            raise ValueError("An image template is required.")
        cache_key = str(cfg.get("template_sha256") or source[:96])
        template = self.templates.get(cache_key)
        if template is None:
            raw = base64.b64decode(source.split(",", 1)[-1])
            template = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
            if template is None or template.size == 0:
                raise ValueError("Invalid phone image template.")
            self.templates[cache_key] = template
            if len(self.templates) > 128:
                self.templates.pop(next(iter(self.templates)))
        if float(np.std(template)) < 3.0:
            raise ValueError("Image template has too little visual detail; crop a more distinctive area.")

        height, width = screen.shape[:2]
        threshold = max(0.5, min(0.99, float(cfg.get("threshold", 0.86))))
        region = cfg.get("region")
        ox = oy = 0
        search = screen
        used_full_screen_fallback = False
        if isinstance(region, dict):
            rx = max(0, min(width - 1, int(float(region.get("x", 0)) * width)))
            ry = max(0, min(height - 1, int(float(region.get("y", 0)) * height)))
            rw = max(1, min(width - rx, int(float(region.get("w", 1)) * width)))
            rh = max(1, min(height - ry, int(float(region.get("h", 1)) * height)))
            ox, oy = rx, ry
            search = screen[ry:ry + rh, rx:rx + rw]
        search_region = {"x": ox, "y": oy, "w": int(search.shape[1]), "h": int(search.shape[0])}

        scale_min = max(0.5, min(1.5, float(cfg.get("scale_min", 0.8))))
        scale_max = max(scale_min, min(1.8, float(cfg.get("scale_max", 1.2))))
        scale_steps = max(1, min(17, int(cfg.get("scale_steps", 9))))
        scales = [scale_min] if scale_steps == 1 else [
            scale_min + (scale_max - scale_min) * i / (scale_steps - 1)
            for i in range(scale_steps)
        ]
        candidates: list[tuple[float, int, int, int, int]] = []
        for scale in scales:
            tw = max(8, int(template.shape[1] * scale))
            th = max(8, int(template.shape[0] * scale))
            if tw > search.shape[1] or th > search.shape[0]:
                continue
            resized = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
            scores = cv2.matchTemplate(search, resized, cv2.TM_CCOEFF_NORMED)
            _, peak, _, location = cv2.minMaxLoc(scores)
            candidates.append((float(peak), ox + int(location[0]), oy + int(location[1]), tw, th))
            masked = scores.copy()
            px, py = location
            masked[max(0, py-th//2):min(masked.shape[0], py+th//2+1),
                   max(0, px-tw//2):min(masked.shape[1], px+tw//2+1)] = -1
            _, second_peak, _, second_location = cv2.minMaxLoc(masked)
            if second_peak >= 0:
                candidates.append((float(second_peak), ox + int(second_location[0]), oy + int(second_location[1]), tw, th))

        # If the crop-local search misses, retry once against the complete phone screen.
        if (not candidates or max(candidate[0] for candidate in candidates) < threshold) and (ox or oy or search.shape != screen.shape):
            candidates = []
            used_full_screen_fallback = True
            search_region = {"x": 0, "y": 0, "w": width, "h": height}
            for scale in scales:
                tw = max(8, int(template.shape[1] * scale))
                th = max(8, int(template.shape[0] * scale))
                if tw > width or th > height:
                    continue
                resized = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
                scores = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
                _, peak, _, location = cv2.minMaxLoc(scores)
                candidates.append((float(peak), int(location[0]), int(location[1]), tw, th))
                masked = scores.copy()
                px, py = location
                masked[max(0, py-th//2):min(masked.shape[0], py+th//2+1),
                       max(0, px-tw//2):min(masked.shape[1], px+tw//2+1)] = -1
                _, second_peak, _, second_location = cv2.minMaxLoc(masked)
                if second_peak >= 0:
                    candidates.append((float(second_peak), int(second_location[0]), int(second_location[1]), tw, th))

        candidates.sort(reverse=True)
        best = candidates[0] if candidates else None
        found = bool(best and best[0] >= threshold)
        ambiguous = False
        if found and len(candidates) > 1:
            def overlaps(a: tuple[float, int, int, int, int], b: tuple[float, int, int, int, int]) -> bool:
                iw = max(0, min(a[1]+a[3], b[1]+b[3]) - max(a[1], b[1]))
                ih = max(0, min(a[2]+a[4], b[2]+b[4]) - max(a[2], b[2]))
                return iw * ih > min(a[3]*a[4], b[3]*b[4]) * 0.5
            second = next((c for c in candidates[1:] if not overlaps(c, best)), None)
            ambiguous = bool(second and best[0] - second[0] < float(cfg.get("ambiguity_margin", 0.045)))
        result: dict[str, Any] = {
            "found": found,
            "ambiguous": ambiguous,
            "score": best[0] if best else 0.0,
            "width": width,
            "height": height,
            "search_region": search_region,
            "used_full_screen_fallback": used_full_screen_fallback,
            "capture_ms": round((captured_at - started) * 1000, 1),
        }
        if cfg.get("include_preview"):
            ok, png = cv2.imencode(".png", screen_color)
            if not ok:
                raise RuntimeError("Could not encode the phone preview as PNG.")
            result["preview_image_base64"] = base64.b64encode(png.tobytes()).decode("ascii")
            result["preview_width"] = width
            result["preview_height"] = height
        if best:
            score, x, y, w, h = best
            result["bbox"] = {"x": x, "y": y, "w": w, "h": h}
            result["center"] = {"x": x + w // 2, "y": y + h // 2}
        result["match_ms"] = round((time.perf_counter() - captured_at) * 1000, 1)
        return result

    def perform(self, operation: str, cfg: dict[str, Any]) -> dict[str, Any]:
        if operation in {"frame", "observe"}:
            data = self._screen_data()
            image_base64, preview_image_base64, width, height = _screen_preview(data.base64)
            result = {
                "serial": self.serial,
                "backend": getattr(self.client, "active_backend", None) or "helper",
                "image_base64": image_base64,
                "preview_image_base64": preview_image_base64,
                "preview_mime_type": "image/jpeg",
                "width": width,
                "height": height,
                "elements": list(getattr(data, "elements", []) or []),
            }
            return result
        if operation in {"open_app", "stop_app"}:
            package = str(cfg.get("package_name", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
                raise ValueError("Enter a valid Android package name.")
            args = ["shell", "am", "force-stop", package] if operation == "stop_app" else ["shell", "monkey", "-p", package, "1"]
            from artemis.runtime.adb_endpoint import adb_command
            proc = subprocess.run(adb_command(["-s", self.serial, *args]), capture_output=True, text=True, timeout=30, check=False)
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "Android app command failed.")
            return {"action": operation, "package_name": package}
        if operation in {"get_ui", "find_element", "wait_element", "read_text", "tap", "long_press", "double_tap"}:
            # Coordinate actions already carry their target. Capturing another
            # hierarchy and screenshot here adds a full phone round trip before
            # every recorder tap without affecting the coordinates.
            needs_elements = operation not in {"tap", "long_press", "double_tap"} or str(cfg.get("target_mode", "coordinates")).lower() == "element"
            data = self._screen_data() if needs_elements else None
            elements = list(getattr(data, "elements", []) or []) if data is not None else []
            selector = str(cfg.get("selector", "")).strip()
            by = str(cfg.get("selector_by", "text")).strip().lower()
            mode = str(cfg.get("match_mode", "exact")).strip().lower()
            def matches(element: dict[str, Any]) -> bool:
                keys = {"text": ["text"], "content_desc": ["content-desc", "accessibilityText"],
                        "resource_id": ["resource-id"], "class": ["class"],
                        "any": ["text", "content-desc", "accessibilityText", "resource-id", "class"]}.get(by, ["text"])
                for key in keys:
                    value = str(element.get(key) or "")
                    if mode == "regex":
                        try:
                            if re.search(selector, value, flags=re.I): return True
                        except re.error as exc:
                            raise ValueError(f"Invalid selector regex: {exc}") from exc
                    elif mode == "contains" and selector.casefold() in value.casefold(): return True
                    elif mode == "starts_with" and value.casefold().startswith(selector.casefold()): return True
                    elif value.casefold() == selector.casefold(): return True
                return False
            found = [e for e in elements if selector and matches(e)]
            if operation == "wait_element":
                deadline = time.monotonic() + max(0.0, min(300.0, float(cfg.get("wait_timeout_seconds", 15))))
                while not found and time.monotonic() < deadline:
                    time.sleep(max(0.1, min(5.0, float(cfg.get("poll_interval_seconds", 0.5)))))
                    data = self._screen_data()
                    elements = list(getattr(data, "elements", []) or [])
                    found = [e for e in elements if selector and matches(e)]
                if cfg.get("require_unique") and len(found) != 1:
                    found = []
                if not found and not cfg.get("fallback_on_miss"):
                    raise RuntimeError(f"Phone UI element was not uniquely found; matches={len(found)}.")
            if operation == "get_ui":
                return {"element_count": len(elements), "elements": elements,
                        "texts": list(dict.fromkeys(str(e.get("text") or e.get("content-desc") or "") for e in elements if e.get("text") or e.get("content-desc")))}
            if operation == "read_text":
                source = found if selector else elements
                texts = list(dict.fromkeys(str(e.get("text") or e.get("content-desc") or "").strip() for e in source if e.get("text") or e.get("content-desc")))
                return {"count": len(texts), "texts": texts[:max(1, min(2000, int(cfg.get("max_items", 300))))]}
            if operation in {"find_element", "wait_element"}:
                index = int(cfg.get("match_index", 0))
                if operation == "find_element" and cfg.get("require_unique") and len(found) != 1:
                    raise RuntimeError(f"Phone UI selector must match exactly one element; matches={len(found)}.")
                return {"found": bool(found), "match_count": len(found),
                        "element": found[index] if 0 <= index < len(found) else None}
            if str(cfg.get("target_mode", "coordinates")).lower() == "element":
                index = int(cfg.get("match_index", 0))
                if cfg.get("require_unique") and len(found) != 1:
                    raise RuntimeError(f"Selector must match one phone element; matches={len(found)}.")
                if index < 0 or index >= len(found):
                    raise RuntimeError(f"Phone UI element was not found; matches={len(found)}.")
                bounds = _bounds(found[index])
                if not bounds:
                    raise RuntimeError("Matched phone element has no screen bounds.")
                x, y = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
            else:
                x, y = int(cfg["x"]), int(cfg["y"])
            if operation == "long_press":
                duration = max(300, min(10000, int(cfg.get("duration_ms", 800))))
                accepted = self._input("swipe", x1=x, y1=y, x2=x, y2=y, duration_ms=duration)
            else:
                accepted = self._input("tap", x=x, y=y)
                if operation == "double_tap":
                    time.sleep(max(40, min(500, int(cfg.get("interval_ms", 100)))) / 1000)
                    accepted = self._input("tap", x=x, y=y) if accepted is not False else False
            if accepted is False:
                raise RuntimeError(f"Phone rejected {operation} input.")
            return {"action": operation, "x": x, "y": y}
        if operation == "swipe":
            if "x1" not in cfg:
                data = self._screen_data()
                width, height = int(data.width), int(data.height)
                direction = str(cfg.get("direction", "up")).lower()
                defaults = {"up": (.5, .8, .5, .25), "down": (.5, .25, .5, .8),
                            "left": (.8, .5, .25, .5), "right": (.25, .5, .8, .5)}
                p = defaults.get(direction, defaults["up"])
                coords = [float(cfg.get(key, p[idx])) for idx, key in enumerate(("start_x_percent", "start_y_percent", "end_x_percent", "end_y_percent"))]
                cfg.update(x1=int(coords[0] * width), y1=int(coords[1] * height), x2=int(coords[2] * width), y2=int(coords[3] * height))
            accepted = self._input(
                "swipe", x1=int(cfg["x1"]), y1=int(cfg["y1"]),
                x2=int(cfg["x2"]), y2=int(cfg["y2"]),
                duration_ms=max(80, min(10000, int(cfg.get("duration_ms", 400)))),
            )
            if accepted is False:
                raise RuntimeError("Phone rejected swipe input.")
            return {"action": operation}
        if operation in {"send_text", "type_text", "clear_text", "set_clipboard", "press_key", "key_event"}:
            operation = {"type_text": "send_text", "key_event": "press_key"}.get(operation, operation)
            value = cfg.get("value", "")
            if operation == "send_text" and cfg.get("clear_existing"):
                self._input("clear_text")
            self._input(operation, value=value, key=cfg.get("key", "BACK"))
            return {"action": operation, "characters": len(str(value)) if operation == "send_text" else None}
        if operation in {"find_image", "tap_image"}:
            deadline = time.monotonic() + max(0.0, min(300.0, float(cfg.get("wait_timeout_seconds", 0)))) if operation == "tap_image" else time.monotonic()
            interval = max(0.1, min(5.0, float(cfg.get("poll_interval_seconds", 0.35))))
            result = self._match_image(cfg)
            while operation == "tap_image" and not result["found"] and time.monotonic() < deadline:
                time.sleep(interval)
                result = self._match_image(cfg)
            if operation == "tap_image":
                if not result["found"]:
                    raise RuntimeError(
                        "Phone image not found; "
                        f"score={result['score']:.3f}, threshold={cfg.get('threshold', 0.86)}, "
                        f"search_region={result['search_region']}, "
                        f"full_screen_fallback={result['used_full_screen_fallback']}, "
                        f"capture_ms={result['capture_ms']}, match_ms={result['match_ms']}."
                    )
                if result["ambiguous"]:
                    raise RuntimeError(
                        "Phone image match is ambiguous; no tap was sent; "
                        f"score={result['score']:.3f}, bbox={result.get('bbox')}, "
                        f"search_region={result['search_region']}, "
                        f"capture_ms={result['capture_ms']}, match_ms={result['match_ms']}."
                    )
                point = result["center"]
                tap_started = time.perf_counter()
                self._input("tap", x=point["x"], y=point["y"])
                result["tap_ms"] = round((time.perf_counter() - tap_started) * 1000, 1)
                result["action"] = "tap_image"
            return result
        if operation == "wait_image":
            wait_started = time.perf_counter()
            timeout = max(0.0, min(300.0, float(cfg.get("wait_timeout_seconds", 15))))
            interval = max(0.1, min(5.0, float(cfg.get("poll_interval_seconds", 0.35))))
            deadline = time.monotonic() + timeout
            while True:
                result = self._match_image(cfg)
                if result["found"]:
                    result["wait_ms"] = round((time.perf_counter() - wait_started) * 1000, 1)
                    return result
                if time.monotonic() >= deadline:
                    result["timed_out"] = True
                    result["wait_ms"] = round((time.perf_counter() - wait_started) * 1000, 1)
                    return result
                time.sleep(interval)
        if operation == "hierarchy":
            data = self._screen_data()
            return {"elements": list(getattr(data, "elements", []) or [])}
        if operation == "screenshot":
            data = self._screen_data()
            image_base64, width, height = _screen_png_base64(data.base64)
            return {"image_base64": image_base64, "width": width, "height": height}
        raise ValueError(f"Unsupported phone operation: {operation}")

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artemis-root", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--adb-path", default="")
    args = parser.parse_args()
    os.environ["AUTOIXB_ARTEMIS_ROOT"] = args.artemis_root
    sys.path.insert(0, args.artemis_root)
    worker = PhoneWorker(args.serial, args.adb_path)
    try:
        connected = worker.connect()
        print(json.dumps({"ready": True, "result": connected}), flush=True)
        for line in sys.stdin:
            request: dict[str, Any] = {}
            try:
                request = json.loads(line)
                request_id = request.get("id")
                operation = str(request.get("operation", ""))
                config = request.get("config", {})
                if not isinstance(config, dict):
                    raise ValueError("Phone operation config must be an object.")
                result = worker.perform(operation, config)
                response = {"id": request_id, "ok": True, "result": result}
            except Exception as exc:  # noqa: BLE001
                response = {"id": request.get("id") if isinstance(request, dict) else None, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            print(json.dumps(response, ensure_ascii=False, default=str), flush=True)
    finally:
        worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
