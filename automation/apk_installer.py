"""Install local APK files on one explicitly selected ADB device."""

from __future__ import annotations

import asyncio
import re
import zipfile
from pathlib import Path

from config.settings import BASE_DIR, settings


APK_DIR = BASE_DIR / "data" / "phone_apks"
MAX_APK_BYTES = 500 * 1024 * 1024
_PACKAGE = re.compile(r"^package: name='([^']+)' versionCode='([^']+)'", re.MULTILINE)
_VERSION = re.compile(r"\bversionCode=(\d+)")


def validate_apk(path: Path) -> None:
    if path.suffix.lower() != ".apk" or not path.is_file():
        raise ValueError("File must be an existing .apk")
    if path.stat().st_size > MAX_APK_BYTES:
        raise ValueError("APK exceeds the 500 MB limit")
    if not zipfile.is_zipfile(path):
        raise ValueError("APK is not a valid ZIP archive")
    with zipfile.ZipFile(path) as archive:
        if "AndroidManifest.xml" not in archive.namelist():
            raise ValueError("APK has no AndroidManifest.xml")


def apk_asset_path(digest: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid APK asset ID")
    return APK_DIR / f"{digest}.apk"


def aapt_path() -> Path:
    sdk = Path(settings.adb_path).parent.parent
    candidates = sorted((sdk / "build-tools").glob("*/aapt.exe"), reverse=True)
    if not candidates:
        raise RuntimeError("Android aapt.exe is required to identify and verify APK packages")
    return candidates[0]


async def _command(*args: str, timeout: float = 30) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except BaseException:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    return proc.returncode or 0, stdout.decode(errors="replace").strip()


async def apk_identity(path: Path) -> tuple[str, str]:
    code, output = await _command(str(aapt_path()), "dump", "badging", str(path))
    match = _PACKAGE.search(output)
    if code != 0 or not match:
        raise ValueError(f"Cannot read APK package metadata: {output[:300]}")
    return match.group(1), match.group(2)


async def device_version(serial: str, package: str) -> str | None:
    code, output = await _command(
        settings.adb_path, "-s", serial, "shell", "dumpsys", "package", package, timeout=25,
    )
    if code != 0:
        return None
    match = _VERSION.search(output)
    return match.group(1) if match else None


async def device_model(serial: str) -> str:
    code, output = await _command(
        settings.adb_path, "-s", serial, "shell", "getprop", "ro.product.model", timeout=15,
    )
    if code != 0 or not output.strip():
        raise RuntimeError(f"Cannot identify ADB device {serial}")
    return output.strip()


async def install_apk(serial: str, path: Path, timeout: float) -> dict[str, str]:
    validate_apk(path)
    package, expected_version = await apk_identity(path)
    code, output = await _command(settings.adb_path, "-s", serial, "get-state", timeout=15)
    if code != 0 or output.strip() != "device":
        raise RuntimeError(f"ADB device {serial} is not online: {output[:200]}")
    previous_version = await device_version(serial, package)
    code, output = await _command(
        settings.adb_path, "-s", serial, "install", "-r", str(path), timeout=timeout,
    )
    if code != 0 or not re.search(r"(?m)^Success\s*$", output):
        raise RuntimeError(f"ADB install failed: {output[:500]}")
    installed_version = await device_version(serial, package)
    if installed_version != expected_version:
        raise RuntimeError(
            f"Install reported success, but {package} version is "
            f"{installed_version or 'not found'} (expected {expected_version})"
        )
    return {
        "package": package,
        "version_code": installed_version,
        "previous_version_code": previous_version or "",
        "status": "installed",
    }
