"""Profile Manager – wraps IXBrowserClient with async helpers and batch ops."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from ixbrowser_local_api import IXBrowserClient
from ixbrowser_local_api.entities import Profile

from config.settings import settings

logger = logging.getLogger(__name__)

# Measured from the currently open Galaxy S / profile 178 browser window.
MIN_PROFILE_WINDOW_WIDTH = 1366
MIN_PROFILE_WINDOW_HEIGHT = 977


@dataclass
class ProfileInfo:
    profile_id: str
    name: str
    group_id: int = 0
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class OpenResult:
    profile_id: str
    webdriver: str
    debugging_address: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class ProfileManager:
    """Thread-safe wrapper around IXBrowserClient.

    All heavy calls are offloaded to a thread-pool so they don't block
    the asyncio event loop.  A semaphore enforces the IXBrowser API
    concurrency limit (default 3).
    """

    def __init__(self) -> None:
        self._client = IXBrowserClient(
            target=settings.ixbrowser_host,
            port=settings.ixbrowser_port,
        )
        self._sem = asyncio.Semaphore(settings.ixbrowser_max_concurrent)
        self._open_profiles: dict[str, OpenResult] = {}
        self._open_profile_window_pids: dict[str, int] = {}
        self._open_profile_options: dict[str, Any] = {
            "load_extensions": True,
            "disable_extension_welcome_page": True,
            "startup_args": [],
            "extension_paths": [],
            "disable_other_extensions": False,
        }

    # ── helpers ──────────────────────────────────────────────────────

    async def _run(self, func, *args, **kwargs):
        """Run a blocking IXBrowserClient method in the default executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def ensure_profile_window_visible(self, profile_id: str) -> bool:
        """Re-show the real Chromium window for a profile already opened by IXBrowser."""
        profile_key = str(profile_id)
        pid = self._open_profile_window_pids.get(profile_key)
        opened = self._open_profiles.get(profile_key)
        payload: dict[str, Any] = {"browser_pid": pid} if pid else {}
        if opened:
            payload["debugging_address"] = opened.debugging_address
        if not payload:
            return False
        return await asyncio.to_thread(self._ensure_profile_window_visible, payload)

    @staticmethod
    def _profile_process_id(payload: Any) -> int | None:
        """Find IXBrowser's browser PID in the local API response, if present."""
        pid_keys = {"pid", "process_id", "browser_pid", "chromium_pid"}
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key.lower() in pid_keys:
                    try:
                        pid = int(value)
                    except (TypeError, ValueError):
                        continue
                    if pid > 0:
                        return pid
            for value in payload.values():
                pid = ProfileManager._profile_process_id(value)
                if pid is not None:
                    return pid
        elif isinstance(payload, list):
            for value in payload:
                pid = ProfileManager._profile_process_id(value)
                if pid is not None:
                    return pid
        return None

    @staticmethod
    def _debugging_port(address: Any) -> int | None:
        value = str(address or "").strip()
        if not value:
            return None
        try:
            parsed = urlsplit(value if "://" in value else f"http://{value}")
            return parsed.port
        except ValueError:
            return None

    @staticmethod
    def _browser_pid_for_debugging_port(port: int) -> int | None:
        """Resolve the Chromium PID from the CDP listener when IXBrowser omits it."""
        if os.name != "nt":
            return None
        try:
            import psutil
        except ImportError:
            logger.error("Cannot focus IXBrowser window: psutil is not installed")
            return None

        # The CDP listener's owning process is the profile's real Chromium process.
        try:
            for connection in psutil.net_connections(kind="tcp"):
                address = connection.laddr
                local_port = getattr(address, "port", None)
                if local_port is None and isinstance(address, tuple) and len(address) > 1:
                    local_port = address[1]
                if (
                    local_port == port
                    and connection.status == psutil.CONN_LISTEN
                    and connection.pid
                ):
                    return int(connection.pid)
        except (psutil.AccessDenied, psutil.Error, OSError):
            logger.debug("Could not inspect CDP listener process for port %s", port, exc_info=True)

        # Some Windows builds deny socket-table inspection. Chromium also exposes
        # its CDP port in the process command line, so use that as a fallback.
        expected = str(port)
        try:
            for process in psutil.process_iter(["pid", "cmdline"]):
                try:
                    args = process.info.get("cmdline") or []
                    for index, arg in enumerate(args):
                        arg = str(arg)
                        if arg == f"--remote-debugging-port={expected}":
                            return int(process.info["pid"])
                        if (
                            arg == "--remote-debugging-port"
                            and index + 1 < len(args)
                            and str(args[index + 1]) == expected
                        ):
                            return int(process.info["pid"])
                except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                    continue
        except (psutil.Error, OSError):
            logger.debug("Could not inspect Chromium command lines for port %s", port, exc_info=True)
        return None

    @staticmethod
    def _ensure_profile_window_visible(payload: Any) -> bool:
        """Restore, size, and raise the IXBrowser Chromium main window on Windows."""
        if os.name != "nt":
            return True
        pid = ProfileManager._profile_process_id(payload)
        if pid is None:
            port = ProfileManager._debugging_port(
                ProfileManager._profile_debugging_address(payload)
            )
            if port is not None:
                pid = ProfileManager._browser_pid_for_debugging_port(port)
        if pid is None:
            return False

        try:
            import ctypes
            import time
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
            user32.EnumWindows.restype = wintypes.BOOL
            user32.GetWindowThreadProcessId.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.DWORD),
            ]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.GetWindowRect.restype = wintypes.BOOL
            user32.GetClassNameW.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(ctypes.c_wchar),
                ctypes.c_int,
            ]
            user32.GetClassNameW.restype = ctypes.c_int
            user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
            user32.GetWindowTextLengthW.restype = ctypes.c_int
            user32.GetWindowTextW.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(ctypes.c_wchar),
                ctypes.c_int,
            ]
            user32.GetWindowTextW.restype = ctypes.c_int
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow.restype = wintypes.BOOL
            user32.SystemParametersInfoW.argtypes = [
                wintypes.UINT,
                wintypes.UINT,
                ctypes.c_void_p,
                wintypes.UINT,
            ]
            user32.SystemParametersInfoW.restype = wintypes.BOOL
            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int
            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.IsWindowVisible.argtypes = [wintypes.HWND]
            user32.IsWindowVisible.restype = wintypes.BOOL
            user32.GetForegroundWindow.restype = wintypes.HWND
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD
            user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
            user32.AttachThreadInput.restype = wintypes.BOOL
            user32.BringWindowToTop.argtypes = [wintypes.HWND]
            user32.BringWindowToTop.restype = wintypes.BOOL
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.SetForegroundWindow.restype = wintypes.BOOL
            user32.RedrawWindow.argtypes = [
                wintypes.HWND,
                ctypes.POINTER(wintypes.RECT),
                ctypes.c_void_p,
                wintypes.UINT,
            ]
            user32.RedrawWindow.restype = wintypes.BOOL
            matches: list[tuple[int, int, int, int, str, str]] = []

            @enum_proc
            def visit(hwnd: int, _lparam: int) -> bool:
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value == pid:
                    rect = wintypes.RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
                        class_name = ctypes.create_unicode_buffer(128)
                        user32.GetClassNameW(hwnd, class_name, len(class_name))
                        title_length = user32.GetWindowTextLengthW(hwnd)
                        title = ctypes.create_unicode_buffer(title_length + 1)
                        user32.GetWindowTextW(hwnd, title, len(title))
                        # Do not confuse Chromium's blank helper surface with its
                        # actual top-level browser window. The main window can have
                        # an empty title briefly while the first page is loading.
                        is_main_browser = int(class_name.value == "Chrome_WidgetWin_1")
                        has_title = int(bool(title.value))
                        hwnd_value = getattr(hwnd, "value", hwnd)
                        matches.append((
                            is_main_browser,
                            has_title,
                            area,
                            int(hwnd_value or 0),
                            class_name.value,
                            title.value,
                        ))
                return True

            # The IXBrowser API can return before Chromium has created its main
            # top-level window. Wait for the actual browser class, even if its
            # title has not loaded yet.
            for _ in range(80):
                matches.clear()
                user32.EnumWindows(visit, 0)
                if any(match[0] for match in matches):
                    break
                time.sleep(0.1)
            main_windows = [match for match in matches if match[0]]
            if not main_windows:
                return False

            # Prefer a titled main window, then the largest main window. This avoids
            # raising a large, empty helper surface over the real profile page.
            _, _, _, hwnd, _, _ = max(main_windows)
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return False

            work = wintypes.RECT()
            if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):  # SPI_GETWORKAREA
                work.left = 0
                work.top = 0
                work.right = user32.GetSystemMetrics(0)
                work.bottom = user32.GetSystemMetrics(1)
            work_w = max(1, work.right - work.left)
            work_h = max(1, work.bottom - work.top)
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            width = min(max(width, MIN_PROFILE_WINDOW_WIDTH), work_w)
            height = min(max(height, MIN_PROFILE_WINDOW_HEIGHT), work_h)
            if work_w < MIN_PROFILE_WINDOW_WIDTH or work_h < MIN_PROFILE_WINDOW_HEIGHT:
                user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE if the screen is smaller than the target size
            else:
                # Always bring the whole browser into the usable desktop area, even
                # when it was only partially offscreen or had an undersized window.
                user32.SetWindowPos(
                    hwnd, 0, work.left, work.top, width, height, 0x0240
                )  # SWP_SHOWWINDOW | SWP_NOOWNERZORDER; HWND_TOP, not topmost.

            # IXBrowser/Chromium may leave a large, titleless Chrome_WidgetWin_0
            # surface above the real browser. Hide only a same-process blank surface
            # that substantially overlaps the titled main window; keep small helper,
            # DevTools, and unrelated windows untouched.
            main_rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(main_rect)):
                main_area = max(0, main_rect.right - main_rect.left) * max(
                    0, main_rect.bottom - main_rect.top
                )

                @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                def hide_duplicate(candidate: int, _lparam: int) -> bool:
                    if candidate == hwnd or not user32.IsWindowVisible(candidate):
                        return True

                    candidate_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(candidate, ctypes.byref(candidate_pid))
                    if candidate_pid.value != pid:
                        return True

                    candidate_class = ctypes.create_unicode_buffer(128)
                    user32.GetClassNameW(candidate, candidate_class, len(candidate_class))
                    if candidate_class.value != "Chrome_WidgetWin_0":
                        return True
                    if user32.GetWindowTextLengthW(candidate) > 0:
                        return True

                    candidate_rect = wintypes.RECT()
                    if not user32.GetWindowRect(candidate, ctypes.byref(candidate_rect)):
                        return True
                    candidate_width = max(0, candidate_rect.right - candidate_rect.left)
                    candidate_height = max(0, candidate_rect.bottom - candidate_rect.top)
                    candidate_area = candidate_width * candidate_height
                    overlap_width = max(
                        0, min(main_rect.right, candidate_rect.right) - max(main_rect.left, candidate_rect.left)
                    )
                    overlap_height = max(
                        0, min(main_rect.bottom, candidate_rect.bottom) - max(main_rect.top, candidate_rect.top)
                    )
                    overlap_area = overlap_width * overlap_height
                    if (
                        main_area > 0
                        and candidate_area >= main_area * 0.5
                        and overlap_area >= min(main_area, candidate_area) * 0.5
                    ):
                        user32.ShowWindow(candidate, 0)  # SW_HIDE
                    return True

                user32.EnumWindows(hide_duplicate, 0)

            # Windows may reject foreground changes from a worker thread unless it
            # is temporarily attached to the current foreground input queue.
            foreground = user32.GetForegroundWindow()
            foreground_thread = (
                user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
            )
            current_thread = kernel32.GetCurrentThreadId()
            attached_input = bool(
                foreground_thread
                and foreground_thread != current_thread
                and user32.AttachThreadInput(current_thread, foreground_thread, True)
            )
            try:
                # Briefly place the window in the topmost band so it becomes
                # visible even when Windows rejects foreground activation from
                # the API worker thread. It is returned to normal z-order below.
                user32.SetWindowPos(
                    hwnd,
                    ctypes.c_void_p(-1),  # HWND_TOPMOST
                    0,
                    0,
                    0,
                    0,
                    0x0043,  # SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
                )
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetWindowPos(
                    hwnd,
                    ctypes.c_void_p(-2),  # HWND_NOTOPMOST
                    0,
                    0,
                    0,
                    0,
                    0x0043,
                )
            finally:
                if attached_input:
                    user32.AttachThreadInput(current_thread, foreground_thread, False)
            user32.RedrawWindow(hwnd, None, None, 0x0185)  # invalidate and repaint child surfaces
            return bool(user32.IsWindowVisible(hwnd))
        except Exception:  # noqa: BLE001
            logger.warning("Could not restore IXBrowser window for pid %s", pid, exc_info=True)
            return False

    @staticmethod
    def _profile_debugging_address(payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in ("debugging_address", "debugAddress", "cdp_address"):
                value = payload.get(key)
                if value:
                    return str(value)
            for value in payload.values():
                address = ProfileManager._profile_debugging_address(value)
                if address:
                    return address
        elif isinstance(payload, list):
            for value in payload:
                address = ProfileManager._profile_debugging_address(value)
                if address:
                    return address
        return None

    def _api_profile_id(self, profile_id: str | int) -> str | int:
        raw = str(profile_id).strip()
        if raw.isdigit():
            return int(raw)
        return raw

    def _api_numeric_id(self, value: str | int, field_name: str = "id") -> int:
        raw = str(value).strip()
        if raw.isdigit():
            return int(raw)
        raise ValueError(f"{field_name} must be a numeric id")

    def _check_error(self, result: Any, action: str) -> None:
        if result is None:
            raise RuntimeError(
                f"IXBrowser {action} failed: "
                f"code={self._client.code} msg={self._client.message}"
            )

    @staticmethod
    def _clean_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        return {k: v for k, v in payload.items() if v is not None and v != ""}

    def _profile_from_payload(self, payload: dict[str, Any] | None) -> Profile:
        clean = self._clean_payload(payload)
        startup_page = str(clean.pop("startup_page", "") or "").strip().lower()
        custom_url = str(clean.pop("custom_url", "") or "").strip()
        proxy_mode = str(clean.pop("proxy_mode", "") or "").strip().lower()
        random_on_create = bool(clean.pop("random_on_create", False))
        clean.pop("profile_id_for_random", None)

        profile = Profile(clean)
        if startup_page == "custom_url" and custom_url:
            profile.set_custom_page(custom_url)
        elif startup_page == "blank":
            profile.set_blank_page()

        if proxy_mode == "direct":
            # IXBrowser represents a direct connection as custom proxy mode
            # with proxy_type="direct". Sending the form's default "http"
            # type makes IXBrowser require a proxy IP and return 101006.
            profile.set_proxy_config({"proxy_mode": 2, "proxy_type": "direct"})
        elif proxy_mode == "custom":
            proxy_ip = str(clean.get("proxy_ip") or "").strip()
            proxy_port = str(clean.get("proxy_port") or "").strip()
            proxy_type = str(clean.get("proxy_type") or "http").strip().lower()
            if not proxy_ip:
                raise ValueError("Proxy riêng cần có máy chủ hoặc địa chỉ IP.")
            if not proxy_port:
                raise ValueError("Proxy riêng cần có cổng kết nối.")
            if proxy_type == "direct":
                raise ValueError("Loại direct chỉ dùng với chế độ Kết nối trực tiếp.")
            profile.set_proxy_config(
                self._clean_payload(
                    {
                        "proxy_mode": 2,
                        "proxy_type": proxy_type,
                        "proxy_ip": proxy_ip,
                        "proxy_port": proxy_port,
                        "proxy_user": clean.get("proxy_user"),
                        "proxy_password": clean.get("proxy_password"),
                        "proxy_check_line": clean.get("proxy_check_line") or "global_line",
                    }
                )
            )
        elif proxy_mode == "purchased_proxy":
            proxy_id = str(clean.get("proxy_id") or "").strip()
            if not proxy_id:
                raise ValueError("Hãy nhập ID proxy đã mua.")
            profile.set_proxy_config(
                {
                    "proxy_mode": 3,
                    "proxy_id": proxy_id,
                }
            )

        for key in [
            "proxy_type",
            "proxy_ip",
            "proxy_port",
            "proxy_user",
            "proxy_password",
            "proxy_check_line",
            "proxy_id",
        ]:
            if hasattr(profile, key):
                setattr(profile, key, None)
        profile.random_on_create = random_on_create  # runtime-only marker for caller
        return profile

    def set_open_profile_options(self, options: dict[str, Any] | None) -> dict[str, Any]:
        options = options or {}
        startup_args = options.get("startup_args", [])
        extension_paths = options.get("extension_paths", [])
        if not isinstance(startup_args, list):
            startup_args = []
        if not isinstance(extension_paths, list):
            extension_paths = []

        clean_startup_args = [str(arg).strip() for arg in startup_args if str(arg).strip()]
        clean_extension_paths = [str(p).strip() for p in extension_paths if str(p).strip()]
        self._open_profile_options = {
            "load_extensions": bool(options.get("load_extensions", True)),
            "disable_extension_welcome_page": bool(
                options.get("disable_extension_welcome_page", True)
            ),
            "startup_args": clean_startup_args,
            "extension_paths": clean_extension_paths,
            "disable_other_extensions": bool(options.get("disable_other_extensions", False)),
        }
        return self.get_open_profile_options()

    def get_open_profile_options(self) -> dict[str, Any]:
        return {
            "load_extensions": bool(self._open_profile_options.get("load_extensions", True)),
            "disable_extension_welcome_page": bool(
                self._open_profile_options.get("disable_extension_welcome_page", True)
            ),
            "startup_args": list(self._open_profile_options.get("startup_args", [])),
            "extension_paths": list(self._open_profile_options.get("extension_paths", [])),
            "disable_other_extensions": bool(
                self._open_profile_options.get("disable_other_extensions", False)
            ),
        }

    def _compose_startup_args(self) -> list[str]:
        options = self.get_open_profile_options()
        args: list[str] = list(options["startup_args"])
        extension_paths = list(options["extension_paths"])
        if extension_paths:
            joined = ",".join(extension_paths)
            if options["disable_other_extensions"]:
                disable_arg = f"--disable-extensions-except={joined}"
                if disable_arg not in args:
                    args.append(disable_arg)
            load_arg = f"--load-extension={joined}"
            if load_arg not in args:
                args.append(load_arg)
        return args

    # ── profile listing ──────────────────────────────────────────────

    async def list_profiles(
        self,
        *,
        keyword: str | None = None,
        group_id: int = 0,
        tag_id: int = 0,
        profile_id: int = 0,
        page: int = 1,
        limit: int = 100,
    ) -> list[ProfileInfo]:
        async with self._sem:
            data = await self._run(
                self._client.get_profile_list,
                keyword=keyword,
                group_id=group_id,
                tag_id=tag_id,
                profile_id=profile_id,
                page=page,
                limit=limit,
            )
        self._check_error(data, "get_profile_list")
        return [
            ProfileInfo(
                profile_id=str(item["profile_id"]),
                name=item.get("name", ""),
                group_id=item.get("group_id", 0),
                tags=[t.get("title", "") for t in item.get("tags", [])],
                raw=item,
            )
            for item in data
        ]

    async def list_all_profiles(
        self, *, group_id: int = 0, tag_id: int = 0, batch_size: int = 100
    ) -> list[ProfileInfo]:
        """Paginate through all profiles matching the filter."""
        all_profiles: list[ProfileInfo] = []
        page = 1
        while True:
            batch = await self.list_profiles(
                group_id=group_id, tag_id=tag_id, page=page, limit=batch_size
            )
            all_profiles.extend(batch)
            if len(batch) < batch_size:
                break
            page += 1
        return all_profiles

    async def list_profiles_raw(
        self,
        *,
        keyword: str | None = None,
        group_id: int = 0,
        tag_id: int = 0,
        profile_id: int = 0,
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        async with self._sem:
            data = await self._run(
                self._client.get_profile_list,
                keyword=keyword,
                group_id=group_id,
                tag_id=tag_id,
                profile_id=profile_id,
                page=page,
                limit=limit,
            )
        self._check_error(data, "get_profile_list")
        return {"total": self._client.total, "profiles": data}

    def _profile_uses_proxy(self, profile: dict[str, Any], proxy_id: int) -> bool:
        candidates = [
            profile.get("proxy_id"),
            profile.get("proxy_config", {}).get("proxy_id")
            if isinstance(profile.get("proxy_config"), dict)
            else None,
            profile.get("proxy_info", {}).get("proxy_id")
            if isinstance(profile.get("proxy_info"), dict)
            else None,
            profile.get("proxy", {}).get("proxy_id")
            if isinstance(profile.get("proxy"), dict)
            else None,
        ]
        return any(str(value).strip() == str(proxy_id) for value in candidates if value not in (None, ""))

    async def profiles_using_proxy(self, proxy_id: str | int) -> dict[str, Any]:
        proxy_id_api = self._api_numeric_id(proxy_id, "proxy_id")
        matched: list[dict[str, Any]] = []
        page = 1
        limit = 100
        while True:
            data = await self.list_profiles_raw(page=page, limit=limit)
            profiles = data.get("profiles", [])
            for profile in profiles:
                if isinstance(profile, dict) and self._profile_uses_proxy(profile, proxy_id_api):
                    matched.append(profile)
            if len(profiles) < limit:
                break
            page += 1
            if page > 200:
                break
        return {"proxy_id": proxy_id_api, "count": len(matched), "profiles": matched}

    async def detach_proxy_from_profiles(self, proxy_id: str | int) -> dict[str, Any]:
        using = await self.profiles_using_proxy(proxy_id)
        detached: list[str] = []
        failed: list[dict[str, str]] = []
        for profile in using["profiles"]:
            profile_id = str(profile.get("profile_id") or profile.get("id") or "").strip()
            if not profile_id:
                continue
            try:
                await self.update_profile_custom_proxy(profile_id, {"proxy_type": "direct"})
                detached.append(profile_id)
            except Exception as exc:  # Keep deleting explicit and auditable.
                failed.append({"profile_id": profile_id, "error": str(exc)})
        return {
            "proxy_id": using["proxy_id"],
            "detached_count": len(detached),
            "detached_profile_ids": detached,
            "failed": failed,
        }

    async def create_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self._profile_from_payload(payload)
        random_on_create = bool(getattr(profile, "random_on_create", False))
        if hasattr(profile, "random_on_create"):
            delattr(profile, "random_on_create")
        async with self._sem:
            result = await self._run(self._client.create_profile, profile)
        self._check_error(result, "create_profile")
        created: dict[str, Any] = result if isinstance(result, dict) else {"result": result}
        data = created.get("data") if isinstance(created.get("data"), dict) else {}
        profile_id = created.get("profile_id") or created.get("id") or data.get("profile_id")
        if random_on_create and profile_id:
            created["random_fingerprint"] = await self.random_profile_fingerprint(str(profile_id))
        return created

    async def update_profile(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._clean_payload(payload)
        clean["profile_id"] = self._api_profile_id(profile_id)
        profile = self._profile_from_payload(clean)
        if hasattr(profile, "random_on_create"):
            delattr(profile, "random_on_create")
        async with self._sem:
            result = await self._run(self._client.update_profile, profile)
        self._check_error(result, "update_profile")
        return result if isinstance(result, dict) else {"result": result}

    async def delete_profile(self, profile_id: str) -> dict[str, Any]:
        async with self._sem:
            result = await self._run(self._client.delete_profile, self._api_profile_id(profile_id))
        self._check_error(result, "delete_profile")
        self._open_profiles.pop(str(profile_id), None)
        self._open_profile_window_pids.pop(str(profile_id), None)
        return result if isinstance(result, dict) else {"deleted": True, "result": result}

    async def copy_profile(self, profile_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        clean = self._clean_payload(payload)
        async with self._sem:
            result = await self._run(
                self._client.create_profile_by_copying,
                self._api_profile_id(profile_id),
                name=clean.get("name"),
                group_id=clean.get("group_id"),
                site_id=clean.get("site_id"),
                site_url=clean.get("site_url"),
            )
        self._check_error(result, "create_profile_by_copying")
        return result if isinstance(result, dict) else {"result": result}

    async def random_profile_fingerprint(self, profile_id: str) -> dict[str, Any]:
        async with self._sem:
            result = await self._run(
                self._client.random_profile_fingerprint,
                self._api_profile_id(profile_id),
            )
        self._check_error(result, "random_profile_fingerprint")
        return result if isinstance(result, dict) else {"result": result}

    async def update_profile_custom_proxy(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._clean_payload(payload)
        async with self._sem:
            result = await self._run(
                self._client.update_profile_to_custom_proxy_mode,
                self._api_profile_id(profile_id),
                proxy_type=clean.get("proxy_type", "direct"),
                proxy_ip=clean.get("proxy_ip"),
                proxy_port=clean.get("proxy_port"),
                proxy_user=clean.get("proxy_user"),
                proxy_password=clean.get("proxy_password"),
                proxy_check_line=clean.get("proxy_check_line"),
            )
        self._check_error(result, "update_profile_to_custom_proxy_mode")
        return result if isinstance(result, dict) else {"result": result}

    async def update_profile_purchased_proxy(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        proxy_id = self._clean_payload(payload).get("proxy_id")
        if proxy_id in (None, ""):
            raise ValueError("proxy_id is required")
        proxy_id = self._api_numeric_id(proxy_id, "proxy_id")
        async with self._sem:
            result = await self._run(
                self._client.update_profile_to_purchased_proxy_mode,
                self._api_profile_id(profile_id),
                proxy_id,
            )
        self._check_error(result, "update_profile_to_purchased_proxy_mode")
        return result if isinstance(result, dict) else {"result": result}

    # ── open / close ─────────────────────────────────────────────────

    async def open_profile(self, profile_id: str) -> OpenResult:
        profile_id_api = self._api_profile_id(profile_id)
        self._open_profile_window_pids.pop(str(profile_id), None)
        options = self.get_open_profile_options()
        startup_args = self._compose_startup_args()
        async with self._sem:
            result = await self._run(
                self._client.open_profile,
                profile_id_api,
                load_extensions=bool(options["load_extensions"]),
                cookies_backup=False,
                load_profile_info_page=False,
                disable_extension_welcome_page=bool(options["disable_extension_welcome_page"]),
                startup_args=startup_args,
            )
        self._check_error(result, "open_profile")
        debugging_address = str(result.get("debugging_address", "") or "").strip()
        # IXBrowser's open/native-list responses normally provide a CDP address,
        # not a Chromium PID. Resolve the process that owns that exact CDP port;
        # otherwise the window restore silently does nothing and the workflow
        # continues behind the editor.
        native_browser_pid = self._profile_process_id(result)
        debug_port = self._debugging_port(debugging_address)
        if debug_port is not None:
            for attempt in range(30):
                browser_pid = await asyncio.to_thread(
                    self._browser_pid_for_debugging_port,
                    debug_port,
                )
                if browser_pid:
                    native_browser_pid = browser_pid
                    break
                if attempt < 29:
                    await asyncio.sleep(0.1)

        opened = OpenResult(
            profile_id=profile_id,
            webdriver=result["webdriver"],
            debugging_address=debugging_address,
            raw=result,
        )
        self._open_profiles[profile_id] = opened
        window_payload: dict[str, Any] = {"debugging_address": debugging_address}
        if native_browser_pid:
            self._open_profile_window_pids[str(profile_id)] = native_browser_pid
            window_payload["browser_pid"] = native_browser_pid

        # Bring the exact profile window forward before attaching Playwright or
        # starting the first node. Retry once for IXBrowser's delayed HWND.
        visible = await asyncio.to_thread(self._ensure_profile_window_visible, window_payload)
        if not visible and os.name == "nt":
            await asyncio.sleep(0.25)
            if not native_browser_pid and debug_port is not None:
                native_browser_pid = await asyncio.to_thread(
                    self._browser_pid_for_debugging_port,
                    debug_port,
                )
                if native_browser_pid:
                    self._open_profile_window_pids[str(profile_id)] = native_browser_pid
                    window_payload["browser_pid"] = native_browser_pid
            visible = await asyncio.to_thread(self._ensure_profile_window_visible, window_payload)
        if not visible and os.name == "nt":
            logger.error(
                "Could not show profile %s Chromium window (CDP port %s, PID %s); stopping before node execution",
                profile_id,
                debug_port,
                native_browser_pid,
            )
            self._open_profiles.pop(profile_id, None)
            self._open_profile_window_pids.pop(str(profile_id), None)
            try:
                await self.close_profile(profile_id)
            except Exception:  # noqa: BLE001
                logger.warning("Could not close profile %s after window activation failed", profile_id, exc_info=True)
            raise RuntimeError(
                "IXBrowser opened the profile, but autoIXB could not locate and show its Chromium window. "
                "The workflow was stopped before its first node."
            )

        logger.info("Opened profile %s → %s", profile_id, opened.debugging_address)
        return opened

    async def close_profile(self, profile_id: str) -> None:
        profile_id_api = self._api_profile_id(profile_id)
        async with self._sem:
            result = await self._run(self._client.close_profile, profile_id_api)
        self._check_error(result, "close_profile")
        self._open_profiles.pop(profile_id, None)
        self._open_profile_window_pids.pop(str(profile_id), None)
        logger.info("Closed profile %s", profile_id)

    async def close_profiles_batch(self, profile_ids: list[str]) -> None:
        profile_ids_api = [self._api_profile_id(pid) for pid in profile_ids]
        async with self._sem:
            result = await self._run(
                self._client.close_profile_in_batches, profile_ids_api
            )
        self._check_error(result, "close_profile_in_batches")
        for pid in profile_ids:
            self._open_profiles.pop(pid, None)
            self._open_profile_window_pids.pop(str(pid), None)
        logger.info("Closed %d profiles in batch", len(profile_ids))

    # ── group / tag helpers ──────────────────────────────────────────

    async def list_groups(self) -> list[dict[str, Any]]:
        async with self._sem:
            data = await self._run(self._client.get_group_list)
        self._check_error(data, "get_group_list")
        return data

    async def list_tags(self) -> list[dict[str, Any]]:
        async with self._sem:
            data = await self._run(self._client.get_tag_list)
        self._check_error(data, "get_tag_list")
        return data

    # ── state ────────────────────────────────────────────────────────

    @property
    def open_profiles(self) -> dict[str, OpenResult]:
        return dict(self._open_profiles)

    async def get_opened_list(self) -> list[dict[str, Any]]:
        async with self._sem:
            data = await self._run(self._client.get_opened_profile_list)
        self._check_error(data, "get_opened_profile_list")
        return data

    async def list_proxies_raw(
        self,
        *,
        mode: int = 0,
        tag_id: int | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        async with self._sem:
            data = await self._run(
                self._client.get_proxy_list,
                mode=mode,
                tag_id=tag_id if tag_id and tag_id > 0 else None,
                page=page,
                limit=limit,
            )
        self._check_error(data, "get_proxy_list")
        return {"total": self._client.total, "proxies": data}

    async def create_proxy(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._clean_payload(payload)
        for key in ("proxy_type", "proxy_ip", "proxy_port"):
            if key not in clean:
                raise ValueError(f"{key} is required")
        async with self._sem:
            result = await self._run(
                self._client.create_proxy,
                clean["proxy_type"],
                clean["proxy_ip"],
                clean["proxy_port"],
                proxy_user=clean.get("proxy_user"),
                proxy_password=clean.get("proxy_password"),
                note=clean.get("note"),
                tag=clean.get("tag"),
            )
        self._check_error(result, "create_proxy")
        return result if isinstance(result, dict) else {"result": result}

    async def update_proxy(self, proxy_id: str | int, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._clean_payload(payload)
        proxy_id_api = self._api_numeric_id(proxy_id, "proxy_id")
        async with self._sem:
            result = await self._run(
                self._client.update_proxy,
                proxy_id_api,
                proxy_type=clean.get("proxy_type"),
                proxy_ip=clean.get("proxy_ip"),
                proxy_port=clean.get("proxy_port"),
                proxy_user=clean.get("proxy_user"),
                proxy_password=clean.get("proxy_password"),
                note=clean.get("note"),
                tag=clean.get("tag"),
            )
        self._check_error(result, "update_proxy")
        return result if isinstance(result, dict) else {"result": result}

    async def delete_proxy(self, proxy_id: str | int, *, detach_profiles: bool = False) -> dict[str, Any]:
        proxy_id_api = self._api_numeric_id(proxy_id, "proxy_id")
        detach_result: dict[str, Any] | None = None
        if detach_profiles:
            detach_result = await self.detach_proxy_from_profiles(proxy_id_api)
            if detach_result.get("failed"):
                return {
                    "deleted": False,
                    "proxy_id": proxy_id_api,
                    "detached": detach_result,
                    "error": "Some profiles could not be detached from this proxy",
                }
        async with self._sem:
            result = await self._run(self._client.delete_proxy, proxy_id_api)
        self._check_error(result, "delete_proxy")
        response = result if isinstance(result, dict) else {"deleted": True, "result": result}
        if detach_result is not None:
            response["detached"] = detach_result
        return response

    async def list_proxy_tags(self, *, name: str | None = None, page: int = 1, limit: int = 100) -> dict[str, Any]:
        async with self._sem:
            data = await self._run(self._client.get_proxy_tag_list, name=name, page=page, limit=limit)
        self._check_error(data, "get_proxy_tag_list")
        return {"total": self._client.total, "tags": data}

    async def create_proxy_tag(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str((payload or {}).get("name") or (payload or {}).get("title") or "").strip()
        if not name:
            raise ValueError("name is required")
        async with self._sem:
            result = await self._run(self._client.create_proxy_tag, name)
        self._check_error(result, "create_proxy_tag")
        return result if isinstance(result, dict) else {"result": result}

    async def update_proxy_tag(self, tag_id: str | int, payload: dict[str, Any]) -> dict[str, Any]:
        name = str((payload or {}).get("name") or (payload or {}).get("title") or "").strip()
        if not name:
            raise ValueError("name is required")
        tag_id_api = self._api_numeric_id(tag_id, "tag_id")
        async with self._sem:
            result = await self._run(self._client.update_proxy_tag, tag_id_api, name)
        self._check_error(result, "update_proxy_tag")
        return result if isinstance(result, dict) else {"result": result}

    async def delete_proxy_tag(self, tag_id: str | int) -> dict[str, Any]:
        tag_id_api = self._api_numeric_id(tag_id, "tag_id")
        async with self._sem:
            result = await self._run(self._client.delete_proxy_tag, tag_id_api)
        self._check_error(result, "delete_proxy_tag")
        return result if isinstance(result, dict) else {"deleted": True, "result": result}
