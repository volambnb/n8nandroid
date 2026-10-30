from __future__ import annotations

from typing import Any


def node_catalog() -> list[dict[str, Any]]:
    """GenLogin-like node palette grouped by bars/categories."""
    return [
        {
            "id": "start_stop",
            "label": "Start - Stop",
            "nodes": [
                {"label": "Start", "type": "Start", "default_config": {}},
                {
                    "label": "Variables",
                    "type": "Variables",
                    "default_config": {
                        "custom_variables": [],
                        "timeout": 30,
                    },
                },
                {"label": "Stop", "type": "Stop", "default_config": {"stop_browser": True}},
            ],
        },
        {
            "id": "navigation",
            "label": "Navigation Bar",
            "nodes": [
                {"label": "New Tab", "type": "New Tab", "default_config": {}},
                {
                    "label": "Open URL",
                    "type": "Open URL",
                    "default_config": {
                        "url": "https://example.com",
                        "wait_time_ms": 0,
                        "wait_for_navigation": "domcontentloaded",
                        "navigation_timeout_seconds": 90,
                    },
                },
                {"label": "Activate Tab", "type": "Activate Tab", "default_config": {"index": 0}},
                {"label": "Close Tab", "type": "Close Tab", "default_config": {}},
                {"label": "Reload Tab", "type": "Reload Tab", "default_config": {}},
            ],
        },
        {
            "id": "mouse",
            "label": "Mouse Bar",
            "nodes": [
                {"label": "Click", "type": "Click", "default_config": {"selector_type": "css", "selector": "button"}},
                {"label": "Mouse Movement", "type": "Mouse Movement", "default_config": {"x": 200, "y": 300, "steps": 20}},
                {"label": "Scroll", "type": "Scroll", "default_config": {"delta_y": 800}},
            ],
        },
        {
            "id": "keyboard",
            "label": "Keyboard Bar",
            "nodes": [
                {"label": "Press Key", "type": "Press Key", "default_config": {"key": "Enter"}},
                {"label": "Type Text", "type": "Type Text", "default_config": {"text": "Hello", "text_file_path": "", "text_file_line_index": 0, "selector_type": "css", "selector": "input"}},
            ],
        },
        {
            "id": "data",
            "label": "Data Bar",
            "nodes": [
                {
                    "label": "Element Exist",
                    "type": "Element Exist",
                    "default_config": {
                        "selector_type": "css",
                        "selector": "body",
                        "wait_state": "visible",
                        "timeout": 5,
                        "output_variable": "exists",
                    },
                },
                {"label": "Get URL", "type": "Get URL", "default_config": {"output_variable": "url"}},
                {
                    "label": "Get Text",
                    "type": "Get Text",
                    "default_config": {
                        "selector_type": "css",
                        "selector": "body",
                        "timeout": 10,
                        "trim_output": True,
                        "output_variable": "text",
                    },
                },
                {
                    "label": "Get Value",
                    "type": "Get Value",
                    "default_config": {
                        "selector_type": "css",
                        "selector": "input",
                        "timeout": 10,
                        "trim_output": True,
                        "output_variable": "value",
                    },
                },
                {"label": "Get Attribute", "type": "Get Attribute", "default_config": {"selector_type": "css", "selector": "img", "attribute_name": "src", "output_variable": "attr"}},
                {
                    "label": "Select Dropdown",
                    "type": "Select Dropdown",
                    "default_config": {
                        "selector_type": "css",
                        "selector": "select",
                        "select_option_by": "value",
                        "option_value": "1",
                        "timeout": 10,
                    },
                },
                {"label": "Random", "type": "Random", "default_config": {"type": "email", "output_variable": "random_value"}},
                {
                    "label": "File Upload",
                    "type": "File Upload",
                    "default_config": {
                        "selector_type": "css",
                        "selector": "input[type=file]",
                        "file_type": "file",
                        "file_path": "",
                        "filename": "upload.bin",
                        "timeout": 30,
                        "wait_state": "attached",
                        "output_variable": "uploaded_file",
                    },
                },
                {"label": "HTTP", "type": "HTTP", "default_config": {"method": "GET", "url": "https://example.com/api", "response_type": "json", "output_variable": "http_response"}},
                {"label": "Read file/variable", "type": "Read file/variable", "default_config": {"input_type": "file", "file_path": "", "mode": "line_by_line", "output_variable": "lines"}},
                {"label": "Write file", "type": "Write file", "default_config": {"file_path": "./artifacts/output.txt", "format": "txt", "mode": "append", "input_variable": "text"}},
                {"label": "Cookies", "type": "Cookies", "default_config": {"action": "export", "file_path": "./artifacts/cookies.json"}},
                {"label": "Save asset", "type": "Save asset", "default_config": {"save_asset_by": "url", "url": "", "output_path": "./artifacts", "filename": ""}},
                {"label": "Spreadsheet", "type": "Spreadsheet", "default_config": {"operation": "read", "file_path": "./artifacts/data.csv", "output_variable": "sheet"}},
                {"label": "Open AI", "type": "Open AI", "default_config": {"output_type": "text", "model": "gpt-4o", "content": "Say hello", "output_variable": "ai"}},
                {"label": "Case Path", "type": "Case Path", "default_config": {"value": "{status}", "cases": {"success": "ok"}, "default_label": "fallback"}},
                {"label": "Insert Data", "type": "Insert Data", "default_config": {"row": {"field": "{value}"}, "output_variable": "inserted_row"}},
                {"label": "RegExp (Data extraction)", "type": "RegExp (Data extraction)", "default_config": {"input_value": "{text}", "expression": "\\d+", "global": True, "output_variable": "matches"}},
                {"label": "IMAP (Read mail)", "type": "IMAP (Read mail)", "default_config": {"email_service": "gmail", "email": "", "password": "", "unseen_only": True, "get_latest_mail": True, "output_variable": "mail"}},
                {"label": "Update field", "type": "Update field", "default_config": {"field": "status", "value": "done"}},
                {"label": "Two FA", "type": "Two FA", "default_config": {"secret": "", "output_variable": "otp"}},
            ],
        },
        {
            "id": "other",
            "label": "Other",
            "nodes": [
                {"label": "Bypass", "type": "Bypass", "default_config": {"timeout": 10}},
                {"label": "Cmd", "type": "Cmd", "default_config": {"command": "echo hello", "output_variable": "cmd_out"}},
                {"label": "Log", "type": "Log", "default_config": {"message": "Checkpoint reached"}},
                {"label": "Analyze Error", "type": "Analyze Error", "default_config": {
                    "output_variable": "node_error_analysis", "include_phone_context": False,
                    "serial_variable": "artemis_phone", "max_auto_retries": 0, "timeout": 30,
                }},
                {"label": "Disconnect", "type": "Disconnect", "default_config": {"timeout_before_reconnect": 2}},
                {"label": "Update tag", "type": "Update tag", "default_config": {"tags": ["processed"]}},
                {"label": "Get tag", "type": "Get tag", "default_config": {"output_variable": "tags"}},
                {"label": "Profile note", "type": "Profile note", "default_config": {"mode": "get", "output_variable": "profile_note"}},
                {"label": "Image search", "type": "Image search", "default_config": {"input_base64_image": "", "threshold": 0.8, "output_variable": "image"}},
                {"label": "Screenshot", "type": "Screenshot", "default_config": {"folder_output": "./artifacts/screenshots", "file_name": "screen.png", "output_variable": "shot"}},
                {"label": "Clipboard", "type": "Clipboard", "default_config": {"action": "copy", "value": "{text}", "output_variable": "clipboard"}},
                {"label": "Switch Frame", "type": "Switch Frame", "default_config": {"frame": "main"}},
                {"label": "Switch Page", "type": "Switch Page", "default_config": {"match_pattern_includes": "", "matched_index": 0}},
                {"label": "Switch Extension Popup V2", "type": "Switch Extension Popup V2", "default_config": {"match_pattern_includes": "", "matched_index": 0}},
                {"label": "Trigger Extension", "type": "Trigger Extension", "default_config": {"extension_url": ""}},
                {"label": "Dialog/Alert", "type": "Dialog/Alert", "default_config": {"action_for_dialog": "yes"}},
                {"label": "Sleep", "type": "Sleep", "default_config": {"mode": "fixed", "seconds": 1}},
                {"label": "If", "type": "If", "default_config": {"expression": "True"}},
                {"label": "Eval", "type": "Eval", "default_config": {"expression": "1 + 1", "output_variable": "eval_result"}},
                {"label": "Javascript", "type": "Javascript", "default_config": {"script": "() => document.title", "output_variable": "js_result"}},
                {"label": "Loop", "type": "Loop", "default_config": {"mode": "count", "count": 3, "output_variable": "loop_index"}},
                {"label": "Loop V2 - Break loop", "type": "Loop V2 - Break loop", "default_config": {}},
                {"label": "Emulate", "type": "Emulate", "default_config": {"width": 1366, "height": 768}},
                {"label": "Comment", "type": "Comment", "default_config": {"text": "Note"}},
            ],
        },
        {
            "id": "artemis_phone",
            "label": "ARTEMIS Phone",
            "nodes": [
                {"label": "ARTEMIS Connect", "type": "ARTEMIS", "default_config": {
                    "serial": "", "serial_variable": "remote_phone_verified",
                    "artemis_root": "", "python_executable": "",
                    "adb_path": "",
                    "output_variable": "artemis_phone", "timeout": 120,
                }},
                {"label": "ARTEMIS Open App", "type": "ARTEMIS Open App", "default_config": {
                    "serial_variable": "artemis_phone", "package_name": "com.example.app",
                    "activity": "", "output_variable": "phone_app", "timeout": 60,
                }},
                {"label": "ARTEMIS Install APKs", "type": "ARTEMIS Install APKs", "default_config": {
                    "serial_variable": "artemis_phone", "apk_files": [],
                    "install_method": "rtl_applications",
                    "install_timeout_seconds": 180, "output_variable": "phone_apk_install_results",
                    "timeout": 0,
                }},
                {"label": "ARTEMIS Stop App", "type": "ARTEMIS Stop App", "default_config": {
                    "serial_variable": "artemis_phone", "package_name": "com.example.app",
                    "output_variable": "phone_app", "timeout": 30,
                }},
                {"label": "ARTEMIS Get UI", "type": "ARTEMIS Get UI", "default_config": {
                    "serial_variable": "artemis_phone", "max_nodes": 300,
                    "output_variable": "phone_ui", "timeout": 30,
                }},
                {"label": "ARTEMIS Find Element", "type": "ARTEMIS Find Element", "default_config": {
                    "serial_variable": "artemis_phone", "selector_by": "text",
                    "selector": "", "match_mode": "exact", "match_index": 0,
                    "output_variable": "phone_element", "timeout": 30,
                }},
                {"label": "ARTEMIS Wait Element", "type": "ARTEMIS Wait Element", "default_config": {
                    "serial_variable": "artemis_phone", "selector_by": "text",
                    "selector": "", "match_mode": "exact", "match_index": 0,
                    "wait_timeout_seconds": 15, "poll_interval_seconds": 0.5,
                    "output_variable": "phone_element", "timeout": 30,
                }},
                {"label": "ARTEMIS Read Text", "type": "ARTEMIS Read Text", "default_config": {
                    "serial_variable": "artemis_phone", "selector_by": "any",
                    "selector": "", "match_mode": "contains", "max_items": 300,
                    "output_variable": "phone_texts", "timeout": 30,
                }},
                {"label": "ARTEMIS Tap", "type": "ARTEMIS Tap", "default_config": {
                    "serial_variable": "artemis_phone", "target_mode": "element",
                    "selector_by": "text", "selector": "", "match_mode": "exact",
                    "match_index": 0, "x": 540, "y": 960,
                    "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Long Press", "type": "ARTEMIS Long Press", "default_config": {
                    "serial_variable": "artemis_phone", "target_mode": "element",
                    "selector_by": "text", "selector": "", "match_mode": "exact",
                    "match_index": 0, "x": 540, "y": 960, "duration_ms": 1000,
                    "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Double Tap", "type": "ARTEMIS Double Tap", "default_config": {
                    "serial_variable": "artemis_phone", "target_mode": "element",
                    "selector_by": "text", "selector": "", "match_mode": "exact",
                    "match_index": 0, "x": 540, "y": 960,
                    "interval_ms": 100, "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Swipe", "type": "ARTEMIS Swipe", "default_config": {
                    "serial_variable": "artemis_phone", "direction": "up",
                    "start_x_percent": 0.5, "start_y_percent": 0.8,
                    "end_x_percent": 0.5, "end_y_percent": 0.25,
                    "duration_ms": 450, "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Type Text", "type": "ARTEMIS Type Text", "default_config": {
                    "serial_variable": "artemis_phone", "text": "",
                    "text_variable": "", "clear_existing": False,
                    "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Clear Text", "type": "ARTEMIS Clear Text", "default_config": {
                    "serial_variable": "artemis_phone", "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Set Clipboard", "type": "ARTEMIS Set Clipboard", "default_config": {
                    "serial_variable": "artemis_phone", "text": "",
                    "text_variable": "", "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Key Event", "type": "ARTEMIS Key Event", "default_config": {
                    "serial_variable": "artemis_phone", "key": "BACK",
                    "output_variable": "phone_action", "timeout": 30,
                }},
                {"label": "ARTEMIS Screenshot", "type": "ARTEMIS Screenshot", "default_config": {
                    "serial_variable": "artemis_phone",
                    "output_path": "./artifacts/phone_screenshot.png",
                    "output_variable": "phone_screenshot", "timeout": 30,
                }},
                {"label": "ARTEMIS Find Image", "type": "ARTEMIS Find Image", "default_config": {
                    "serial_variable": "artemis_phone", "image_asset_id": "", "threshold": 0.86,
                    "scale_min": 0.8, "scale_max": 1.2, "scale_steps": 9,
                    "region": {}, "wait_timeout_seconds": 15, "poll_interval_seconds": 0.35,
                    "output_variable": "phone_image_match", "timeout": 30,
                }},
                {"label": "ARTEMIS Tap Image", "type": "ARTEMIS Tap Image", "default_config": {
                    "serial_variable": "artemis_phone", "image_asset_id": "", "threshold": 0.86,
                    "scale_min": 0.8, "scale_max": 1.2, "scale_steps": 9,
                    "region": {}, "wait_timeout_seconds": 8,
                    "output_variable": "phone_image_tap", "timeout": 30,
                }},
            ],
        },
        {
            "id": "app_control",
            "label": "App điều khiển",
            "nodes": [
                {"label": "Call App", "type": "Call App", "default_config": {
                    "app_id": "", "input_mapping": {}, "output_mapping": {}, "timeout": 300,
                }},
            ],
        },
    ]
