"""Deterministic diagnosis for failed automation nodes."""

from __future__ import annotations

import re
from typing import Any


_READ_ONLY_NODES = {
    "element_exist", "element_exists", "get_url", "get_text", "get_value",
    "get_attribute", "screenshot", "artemis_get_ui",
    "artemis_find_element", "artemis_wait_element", "artemis_read_text",
    "artemis_screenshot", "artemis_find_image",
}


def diagnose_node_error(
    *,
    node_type: str,
    error_type: str,
    error: str,
) -> dict[str, Any]:
    """Return a cause and concrete recovery steps without changing device state."""
    node = str(node_type or "").strip().lower().replace(" ", "_")
    # Classify from the exception itself. Tracebacks often mention helper names
    # such as "image" or "selector" even when the real cause is a timeout.
    details = f"{error_type} {error}".casefold()

    phone_error = any(token in details for token in (
        "no verified adb phone", "adb serial", "device offline", "device not found",
        "no devices/emulators", "more than one device", "unauthorized", "rdb",
        "remote debug bridge", "phone worker", "phone bridge", "closed its output",
        "worker stopped", "did not become ready",
    )) or (node.startswith("artemis") and any(token in details for token in (
        "connection reset", "connection refused", "connection lost", "not connected",
    )))
    if phone_error:
        category = "phone_connection"
        summary = "Kết nối ADB/ARTEMIS tới phone đang thiếu, offline hoặc worker bị ngắt."
        fix = "Mở lại phiên Samsung RTL, xác nhận Remote Debug Bridge đang Connected, rồi chạy ARTEMIS Connect và kiểm tra đúng serial."
        transient = any(token in details for token in (
            "connection reset", "worker stopped", "closed its output", "temporarily unavailable",
        ))
    elif any(token in details for token in (
        "selector", "element was not found", "element not found", "no element",
        "matches=0", "not uniquely found", "strict mode violation",
    )):
        category = "selector"
        summary = "Node không tìm được đúng phần tử hoặc selector khớp nhiều phần tử."
        fix = "Chạy ARTEMIS Get UI để xem cây giao diện, sửa selector; thêm ARTEMIS Wait Element nếu màn hình cần thời gian tải."
        transient = any(token in details for token in ("timeout", "timed out", "deadline exceeded"))
    elif any(token in details for token in (
        "image", "template", "threshold", "ambiguous", "match score",
    )) and node in {"artemis_find_image", "artemis_tap_image", "image_search"}:
        category = "image_match"
        transient = any(token in details for token in ("timeout", "timed out", "deadline exceeded"))
        summary = "Ảnh mẫu không khớp đủ tin cậy hoặc có nhiều vùng giống nhau."
        fix = "Chụp/cắt lại vùng ảnh có chi tiết riêng biệt, kiểm tra kích thước phone và vùng tìm; giảm ngưỡng chỉ sau khi xem điểm khớp."
    elif any(token in details for token in (
        "permission denied", "access is denied", "winerror 5", "operation not permitted",
    )):
        category = "permission"
        summary = "Tiến trình autoIXB không có quyền đọc/ghi/chạy tài nguyên node cần dùng."
        fix = "Kiểm tra quyền thư mục/file và tài khoản chạy service; với file APK, xác nhận asset đã tải lên autoIXB và còn tồn tại."
        transient = False
    elif any(token in details for token in (
        "timeout", "timed out", "deadline exceeded", "exceeded timeout",
    )):
        category = "timeout"
        summary = "Node vượt quá thời gian chờ trước khi hoàn tất."
        fix = "Xác định node đang chờ trang, phone hay selector; tăng timeout phù hợp hoặc thêm bước chờ trạng thái cụ thể."
        transient = True
    elif any(token in details for token in (
        "apk", "package name", "activity", "install failed", "not installed",
        "unable to resolve", "monkey",
    )) or node in {"artemis_install_apks", "artemis_open_app"}:
        category = "android_package"
        summary = "Lỗi nhiều khả năng liên quan APK, package name, activity hoặc trạng thái cài đặt."
        fix = "Xác minh APK/package đã cài và đúng phiên bản. Nếu cần tìm Activity hoặc quyền khai báo, phân tích AndroidManifest và call flow của APK bằng android-reverse-engineering-skill/jadx."
        transient = False
    elif any(token in details for token in (
        "net::err_", "name_not_resolved", "dns", "network is unreachable",
        "failed to fetch", "connection aborted",
    )):
        category = "network"
        summary = "Trang hoặc API không truy cập được do DNS, mạng hoặc kết nối bị ngắt."
        fix = "Kiểm tra proxy/profile, DNS và URL; thêm retry có giới hạn cho bước đọc sau khi mạng ổn định."
        transient = True
    elif any(token in details for token in (
        "invalid selector", "invalid regular expression", "syntaxerror", "syntax error",
    )):
        category = "configuration"
        summary = "Cấu hình hoặc biểu thức của node không hợp lệ."
        fix = "Sửa selector, regex, package/activity hoặc biểu thức theo loại node; chạy riêng node sau khi lưu."
        transient = False
    else:
        category = "unknown"
        summary = "Chưa khớp quy tắc lỗi đã biết; xem exception và traceback của node để xác định dòng gây lỗi."
        fix = "Kiểm tra cấu hình node, thông tin traceback và trạng thái browser/phone ngay sau lỗi; sửa nguyên nhân rồi chạy lại từ node đó."
        transient = False

    retry_safe = transient and node in _READ_ONLY_NODES
    retry_reason = (
        "Lỗi có dấu hiệu tạm thời và node chỉ đọc dữ liệu, không lặp thao tác ghi lên browser/phone."
        if retry_safe else
        "Không tự chạy lại: lỗi chưa chắc tạm thời hoặc node có thể đã tạo tác động (click, nhập, cài, mở/đóng app...)."
    )
    return {
        "category": category,
        "summary": summary,
        "recommended_fix": fix,
        "safe_to_retry": retry_safe,
        "retry_reason": retry_reason,
        "confidence": "medium" if category != "unknown" else "low",
    }


def selector_match_count(elements: list[dict[str, Any]], config: dict[str, Any]) -> int | None:
    """Count selector candidates without returning screen text to logs."""
    selector = str(config.get("selector") or "").strip()
    if not selector:
        return None
    by = str(config.get("selector_by") or "any").strip().lower()
    mode = str(config.get("match_mode") or "exact").strip().lower()
    keys = {
        "text": ("text",),
        "content_desc": ("content-desc", "accessibilityText"),
        "resource_id": ("resource-id",),
        "class": ("class",),
        "any": ("text", "content-desc", "accessibilityText", "resource-id", "class"),
    }.get(by, ("text",))
    try:
        pattern = re.compile(selector, re.IGNORECASE) if mode == "regex" else None
    except re.error:
        return None
    count = 0
    for element in elements:
        values = [str(element.get(key) or "") for key in keys]
        matched = False
        for value in values:
            if pattern:
                matched = bool(pattern.search(value))
            elif mode == "contains":
                matched = selector.casefold() in value.casefold()
            elif mode == "starts_with":
                matched = value.casefold().startswith(selector.casefold())
            else:
                matched = value.casefold() == selector.casefold()
            if matched:
                break
        if matched:
            count += 1
    return count
