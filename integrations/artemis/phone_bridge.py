"""Small ARTEMIS Accessibility Helper bridge used by autoIXB phone nodes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _elements(client: Any) -> list[dict[str, Any]]:
    from artemis.clients.accessibility_client import normalize_helper_elements
    from third_party.mobile_use.clients.ui_automator_client import parse_hierarchy_xml_to_elements

    snapshot = client.get_hierarchy_json()
    result = normalize_helper_elements(snapshot.get("elements"))
    if result:
        return result
    xml = snapshot.get("xml")
    return parse_hierarchy_xml_to_elements(xml) if isinstance(xml, str) and xml.strip() else []


def _bounds(element: dict[str, Any]) -> dict[str, int] | None:
    parsed = element.get("parsed_bounds")
    if isinstance(parsed, dict):
        try:
            bounds = {key: int(parsed[key]) for key in ("left", "top", "right", "bottom")}
            if bounds["right"] > bounds["left"] and bounds["bottom"] > bounds["top"]:
                return bounds
        except (KeyError, TypeError, ValueError):
            pass
    raw = str(element.get("bounds") or "")
    match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", raw)
    if not match:
        return None
    left, top, right, bottom = map(int, match.groups())
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _summary(element: dict[str, Any]) -> dict[str, Any]:
    keys = ("text", "content-desc", "resource-id", "class", "clickable", "enabled", "selected", "focused", "visible-to-user")
    result = {key: element.get(key, "") for key in keys if element.get(key) not in (None, "")}
    bounds = _bounds(element)
    if bounds:
        result["bounds"] = bounds
    return result


def _matches(element: dict[str, Any], config: dict[str, Any]) -> bool:
    selector = str(config.get("selector", "")).strip()
    if not selector:
        return False
    by = str(config.get("selector_by", "text")).strip().lower()
    mode = str(config.get("match_mode", "exact")).strip().lower()
    values: list[str]
    if by in {"content_desc", "content-desc", "description"}:
        values = [str(element.get("content-desc") or element.get("accessibilityText") or "")]
    elif by in {"resource_id", "resource-id", "id"}:
        values = [str(element.get("resource-id") or "")]
    elif by in {"class", "class_name"}:
        values = [str(element.get("class") or "")]
    elif by == "any":
        values = [
            str(element.get("text") or ""),
            str(element.get("content-desc") or element.get("accessibilityText") or ""),
            str(element.get("resource-id") or ""),
            str(element.get("class") or ""),
        ]
    else:
        values = [str(element.get("text") or "")]
    needle = selector.casefold()
    for value in values:
        candidate = value.casefold()
        if mode == "contains" and needle in candidate:
            return True
        if mode == "starts_with" and candidate.startswith(needle):
            return True
        if mode == "regex":
            try:
                if re.search(selector, value, flags=re.IGNORECASE):
                    return True
            except re.error as exc:
                raise ValueError(f"Invalid selector regular expression: {exc}") from exc
        if mode not in {"contains", "starts_with", "regex"} and candidate == needle:
            return True
    return False


def _find(elements: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    return [element for element in elements if _matches(element, config)]


def _center(element: dict[str, Any]) -> tuple[int, int]:
    bounds = _bounds(element)
    if not bounds:
        raise RuntimeError("The matched phone UI element has no usable screen bounds.")
    return (
        (bounds["left"] + bounds["right"]) // 2,
        (bounds["top"] + bounds["bottom"]) // 2,
    )


def _get_target(client: Any, config: dict[str, Any]) -> tuple[int, int, dict[str, Any] | None]:
    if str(config.get("target_mode", "element")).lower() == "coordinates":
        return int(config.get("x", 0)), int(config.get("y", 0)), None
    matches = _find(_elements(client), config)
    if not matches:
        raise RuntimeError(f"Phone UI element was not found: {config.get('selector', '')}")
    index = int(config.get("match_index", 0))
    if index < 0 or index >= len(matches):
        raise RuntimeError(f"match_index {index} is outside {len(matches)} matching phone elements.")
    target = matches[index]
    x, y = _center(target)
    if str(target.get("enabled", "true")).lower() == "false":
        raise RuntimeError("The matched phone UI element is disabled.")
    return x, y, target


def _run_adb(serial: str, args: list[str], timeout: float = 30.0) -> dict[str, Any]:
    from artemis.runtime.adb_endpoint import adb_command

    proc = subprocess.run(
        adb_command(["-s", serial, *args]),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    result = {"return_code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    if proc.returncode != 0:
        raise RuntimeError(result["stderr"] or result["stdout"] or f"ADB command failed ({proc.returncode}).")
    return result


def _perform(client: Any, serial: str, operation: str, config: dict[str, Any]) -> dict[str, Any]:
    if operation == "connect":
        elements = _elements(client)
        from artemis.runtime.helper_manager import helper_manager

        session = client.session
        status = helper_manager.status(serial)
        result = {
            "status": "connected",
            "serial": serial,
            "helper_installed": bool(status.get("installed")),
            "helper_enabled": bool(status.get("enabled")),
            "reachable": bool(status.get("reachable")),
            "protocol_supported": bool(status.get("protocol_supported")),
            "protocol_version": session.protocol_version if session else None,
            "helper_version": session.version_code if session else None,
            "hierarchy_nodes": len(elements),
            "backend": "ARTEMIS Accessibility Helper",
        }
        if not all((result["helper_installed"], result["helper_enabled"], result["reachable"], result["protocol_supported"], result["hierarchy_nodes"] > 0)):
            raise RuntimeError("ARTEMIS helper connected but did not return a usable phone UI tree.")
        return result

    if operation == "open_app":
        package = str(config.get("package_name", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
            raise ValueError("Enter a valid Android package name, such as com.example.app.")
        activity = str(config.get("activity", "")).strip()
        if activity:
            if not re.fullmatch(r"[A-Za-z0-9_.$]+(?:/[A-Za-z0-9_.$]+)?", activity):
                raise ValueError("The Android activity name contains unsupported characters.")
            component = activity if "/" in activity else f"{package}/{activity}"
            result = _run_adb(serial, ["shell", "am", "start", "-n", component])
        else:
            result = _run_adb(serial, ["shell", "monkey", "-p", package, "1"])
        return {"action": "open_app", "package_name": package, **result}

    if operation == "stop_app":
        package = str(config.get("package_name", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
            raise ValueError("Enter a valid Android package name, such as com.example.app.")
        result = _run_adb(serial, ["shell", "am", "force-stop", package])
        return {"action": "stop_app", "package_name": package, **result}

    if operation in {"get_ui", "read_text", "find_element", "wait_element"}:
        timeout = max(0.0, min(float(config.get("wait_timeout_seconds", 15)), 300.0))
        interval = max(0.1, min(float(config.get("poll_interval_seconds", 0.5)), 10.0))
        deadline = time.monotonic() + (timeout if operation == "wait_element" else 0)
        while True:
            elements = _elements(client)
            matches = _find(elements, config) if str(config.get("selector", "")).strip() else []
            if operation == "wait_element" and not matches and time.monotonic() < deadline:
                time.sleep(min(interval, max(0, deadline - time.monotonic())))
                continue
            if operation == "get_ui":
                limit = max(1, min(int(config.get("max_nodes", 300)), 2000))
                compact = [_summary(element) for element in elements[:limit]]
                texts = [str(item.get("text") or item.get("content-desc") or "") for item in compact]
                texts = [text for text in texts if text.strip()]
                return {"element_count": len(elements), "elements": compact, "texts": texts}
            if operation == "read_text":
                source = _find(elements, config) if str(config.get("selector", "")).strip() else elements
                limit = max(1, min(int(config.get("max_items", 300)), 2000))
                texts: list[str] = []
                for element in source:
                    text = str(element.get("text") or element.get("content-desc") or element.get("accessibilityText") or "").strip()
                    if text and text not in texts:
                        texts.append(text)
                    if len(texts) >= limit:
                        break
                return {"count": len(texts), "texts": texts}
            found = bool(matches)
            selected: dict[str, Any] | None = None
            if found:
                index = int(config.get("match_index", 0))
                if index < 0 or index >= len(matches):
                    raise RuntimeError(f"match_index {index} is outside {len(matches)} matching phone elements.")
                selected = _summary(matches[index])
            if operation == "find_element":
                return {"found": found, "match_count": len(matches), "element": selected}
            if operation == "wait_element":
                return {"found": found, "match_count": len(matches), "element": selected}

    if operation in {"tap", "long_press", "double_tap"}:
        x, y, target = _get_target(client, config)
        if operation == "tap":
            success = client.tap(x, y)
            if not success:
                raise RuntimeError("ARTEMIS tap action was not accepted by the phone.")
        elif operation == "double_tap":
            success = client.tap(x, y)
            if success:
                time.sleep(max(0, min(int(config.get("interval_ms", 100)), 1000)) / 1000)
                success = client.tap(x, y)
            if not success:
                raise RuntimeError("ARTEMIS double-tap action was not accepted by the phone.")
        else:
            duration = max(300, min(int(config.get("duration_ms", 1000)), 10000))
            _run_adb(serial, ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration)])
        return {"action": operation, "x": x, "y": y, "element": _summary(target) if target else None}

    if operation == "swipe":
        image = client.get_screenshot()
        if image is None:
            raise RuntimeError("ARTEMIS could not capture the phone screen to size the swipe.")
        width, height = image.size
        direction = str(config.get("direction", "up")).lower()
        defaults = {
            "up": (0.5, 0.8, 0.5, 0.25),
            "down": (0.5, 0.25, 0.5, 0.8),
            "left": (0.8, 0.5, 0.25, 0.5),
            "right": (0.25, 0.5, 0.8, 0.5),
        }
        if direction not in defaults:
            raise ValueError("Swipe direction must be up, down, left, or right.")
        default_points = defaults[direction]
        percentages = [
            float(config.get("start_x_percent", default_points[0])),
            float(config.get("start_y_percent", default_points[1])),
            float(config.get("end_x_percent", default_points[2])),
            float(config.get("end_y_percent", default_points[3])),
        ]
        if any(value < 0 or value > 1 for value in percentages):
            raise ValueError("Swipe percentages must be between 0 and 1.")
        x1, y1, x2, y2 = int(percentages[0] * width), int(percentages[1] * height), int(percentages[2] * width), int(percentages[3] * height)
        duration = max(80, min(int(config.get("duration_ms", 450)), 10000))
        if not client.swipe(x1, y1, x2, y2, duration_ms=duration):
            raise RuntimeError("ARTEMIS swipe action was not accepted by the phone.")
        return {"action": "swipe", "direction": direction, "from": [x1, y1], "to": [x2, y2], "duration_ms": duration}

    if operation == "type_text":
        text = str(config.get("text", ""))
        if config.get("text_variable"):
            text = str(config.get("resolved_text_variable_value", text))
        if config.get("clear_existing") and not client.clear_text():
            raise RuntimeError("ARTEMIS could not clear the focused phone field.")
        if not client.send_text(text):
            raise RuntimeError("ARTEMIS could not enter text in the focused phone field.")
        return {"action": "type_text", "characters": len(text)}

    if operation == "clear_text":
        if not client.clear_text():
            raise RuntimeError("ARTEMIS could not clear the focused phone field.")
        return {"action": "clear_text"}

    if operation == "set_clipboard":
        text = str(config.get("text", ""))
        if config.get("text_variable"):
            text = str(config.get("resolved_text_variable_value", text))
        if not client.set_clipboard(text):
            raise RuntimeError("ARTEMIS could not set the phone clipboard.")
        return {"action": "set_clipboard", "characters": len(text)}

    if operation == "key_event":
        key = str(config.get("key", "BACK")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", key):
            raise ValueError("Key event must be an Android key name such as BACK, HOME, ENTER, or DPAD_DOWN.")
        if not client.press_key(key):
            raise RuntimeError(f"ARTEMIS could not send key event {key}.")
        return {"action": "key_event", "key": key.upper()}

    if operation == "screenshot":
        image = client.get_screenshot()
        if image is None:
            raise RuntimeError("ARTEMIS could not capture the phone screen.")
        output_path = Path(str(config.get("output_path", "phone_screenshot.png"))).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
        return {"path": str(output_path.resolve()), "width": image.width, "height": image.height}

    raise ValueError(f"Unsupported ARTEMIS phone operation: {operation}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artemis-root", required=True, type=Path)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--operation", default="connect")
    args = parser.parse_args()
    try:
        config = json.load(sys.stdin) if args.operation != "connect" else {}
        if not isinstance(config, dict):
            raise ValueError("ARTEMIS bridge config must be a JSON object.")
        root = args.artemis_root.resolve()
        if not (root / "pyproject.toml").is_file():
            raise RuntimeError("ARTEMIS project root is invalid.")
        sys.path.insert(0, str(root))
        from artemis.clients.accessibility_client import AccessibilityClient

        client = AccessibilityClient(args.serial, provision_on_connect=args.operation == "connect")
        client.connect()
        result = _perform(client, args.serial, args.operation, config)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
