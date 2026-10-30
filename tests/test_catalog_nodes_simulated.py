from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from automation.catalog import node_catalog
from automation.models import Node
from automation.node_executor import NodeExecutionContext, NodeExecutor


class FakeLocator:
    def __init__(self, events):
        self.events = events

    @property
    def first(self) -> "FakeLocator":
        return self

    async def wait_for(self, **_kwargs):
        return None

    async def click(self, **_kwargs):
        self.events.append(("locator_click", _kwargs))
        return None

    async def fill(self, *_args, **_kwargs):
        self.events.append(("fill", _args, _kwargs))
        return None

    async def type(self, *_args, **_kwargs):
        self.events.append(("type", _args, _kwargs))
        return None

    async def text_content(self, **_kwargs):
        return " simulated text "

    async def input_value(self, **_kwargs):
        return "simulated value"

    async def get_attribute(self, _name):
        return "https://fixture.invalid/image.png"

    async def select_option(self, **_kwargs):
        self.events.append(("select_option", _kwargs))
        return None

    async def set_input_files(self, *_args, **_kwargs):
        self.events.append(("set_input_files", _args, _kwargs))
        return None


class FakePage:
    def __init__(self, url: str = "https://fixture.invalid/", events=None):
        self.url = url
        self.events = events if events is not None else []
        self.keyboard = self
        self.mouse = self
        self.frames = []
        self.dialog_callback = None
        self.closed = False
        self.screenshot_bytes = b""

    def locator(self, _selector):
        return FakeLocator(self.events)

    async def goto(self, url, **_kwargs):
        self.events.append(("goto", url))
        self.url = url

    async def title(self):
        return "Fixture page"

    async def content(self):
        return "<html><body>fixture</body></html>"

    async def reload(self, **_kwargs):
        self.events.append(("reload",))
        return None

    async def close(self):
        self.events.append(("close",))
        self.closed = True

    async def press(self, *_args, **_kwargs):
        self.events.append(("press", _args, _kwargs))
        return None

    async def type(self, *_args, **_kwargs):
        self.events.append(("keyboard_type", _args, _kwargs))
        return None

    async def insert_text(self, *_args, **_kwargs):
        self.events.append(("insert_text", _args, _kwargs))
        return None

    async def click(self, *_args, **_kwargs):
        self.events.append(("mouse_click", _args, _kwargs))
        return None

    async def move(self, *_args, **_kwargs):
        self.events.append(("mouse_move", _args, _kwargs))
        return None

    async def wheel(self, *_args, **_kwargs):
        self.events.append(("mouse_wheel", _args, _kwargs))
        return None

    async def evaluate(self, *_args, **_kwargs):
        self.events.append(("evaluate", _args, _kwargs))
        return "simulated evaluation"

    async def set_viewport_size(self, *_args, **_kwargs):
        self.events.append(("set_viewport_size", _args, _kwargs))
        return None

    async def screenshot(self, *, path=None, **_kwargs):
        if path:
            Path(path).write_bytes(self.screenshot_bytes)
            self.events.append(("screenshot", path))
        else:
            self.events.append(("screenshot", None))
        return self.screenshot_bytes

    async def query_selector(self, _selector):
        return None

    def on(self, event, callback):
        if event == "dialog":
            self.dialog_callback = callback


class FakeBrowserContext:
    def __init__(self, pages, effects):
        self.pages = pages
        self.effects = effects

    async def new_page(self):
        page = FakePage(events=self.effects)
        self.pages.append(page)
        return page

    async def cookies(self):
        self.effects.append(("cookies",))
        return [{"name": "fixture", "value": "simulated"}]

    async def add_cookies(self, _cookies):
        self.effects.append(("add_cookies",))
        return None


class FakeBrowser:
    def __init__(self, effects):
        self.effects = effects

    async def close(self):
        self.effects.append(("browser_close",))
        return None


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    content = b"fixture-bytes"
    text = "fixture response"

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": "simulated model response"}}],
            "fixture": True,
        }


class FakeHttpClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def request(self, *_args, **_kwargs):
        return FakeResponse()

    async def get(self, *_args, **_kwargs):
        return FakeResponse()

    async def post(self, *_args, **_kwargs):
        return FakeResponse()


class FakeImap:
    def __init__(self, *_args, **_kwargs):
        pass

    def login(self, *_args):
        return "OK", []

    def select(self, *_args):
        return "OK", []

    def search(self, *_args):
        return "OK", [b""]

    def logout(self):
        return "BYE", []


class FakeProcess:
    returncode = 0

    async def communicate(self):
        return b"simulated stdout", b""


class CatalogNodeSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_catalog_node_runs_with_isolated_fakes(self):
        executor = NodeExecutor()
        nodes = [node for group in node_catalog() for node in group["nodes"]]
        self.assertEqual(len(nodes), 57)

        with tempfile.TemporaryDirectory(prefix="autoixb-node-sim-") as temp_dir:
            root = Path(temp_dir)
            input_file = root / "input.txt"
            input_file.write_text("fixture line\n", encoding="utf-8")
            screenshot = np.random.default_rng(7).integers(0, 255, (12, 12, 3), dtype=np.uint8)
            ok, encoded = cv2.imencode(".png", screenshot)
            self.assertTrue(ok)
            png_bytes = encoded.tobytes()
            template = base64.b64encode(png_bytes).decode("ascii")
            failures = []
            fallbacks = {}

            def make_context():
                effects = []
                page = FakePage(events=effects)
                page.screenshot_bytes = png_bytes
                ext_page = FakePage("chrome-extension://fixture/popup.html", effects)
                browser_context = FakeBrowserContext(
                    [page, FakePage("https://fixture.invalid/second", effects), ext_page], effects
                )
                browser = FakeBrowser(effects)
                log_entries = []

                async def log_noop(*args, **_kwargs):
                    log_entries.append(args)

                async def reconnect():
                    replacement = FakePage(events=effects)
                    browser_context.pages.append(replacement)
                    return browser, browser_context, replacement

                async def get_field(_profile_id, key):
                    effects.append(("get_field", key))
                    return "saved note" if key == "note" else None

                async def set_field(_profile_id, key, value):
                    effects.append(("set_field", key, value))
                    return None

                async def get_tags(_profile_id):
                    effects.append(("get_tags",))
                    return ["fixture"]

                async def set_tags(_profile_id, tags):
                    effects.append(("set_tags", tags))
                    return None

                ctx = NodeExecutionContext(
                    run_id="simulation",
                    run_item_id="simulation:item",
                    profile_id="fixture-profile",
                    playwright=None,  # type: ignore[arg-type]
                    browser=browser,  # type: ignore[arg-type]
                    browser_context=browser_context,  # type: ignore[arg-type]
                    active_page=page,  # type: ignore[arg-type]
                    profile_debug_url="",
                    variables={"text": "fixture 123", "value": "fixture", "status": "ok"},
                    log=log_noop,
                    reconnect=reconnect,
                    profile_field_get=get_field,
                    profile_field_set=set_field,
                    profile_tag_get=get_tags,
                    profile_tag_set=set_tags,
                )
                ctx.simulated_effects = effects
                ctx.simulated_log_entries = log_entries
                ctx.simulated_original_page = page
                return ctx

            async def fake_create_subprocess_shell(*_args, **_kwargs):
                return FakeProcess()

            clipboard = {"value": "simulated clipboard"}
            fake_pyperclip = type(
                "FakePyperclip",
                (),
                {
                    "copy": staticmethod(lambda value: clipboard.update(value=value)),
                    "paste": staticmethod(lambda: clipboard["value"]),
                },
            )

            with (
                patch("automation.node_executor.httpx.AsyncClient", FakeHttpClient),
                patch("automation.node_executor.imaplib.IMAP4_SSL", FakeImap),
                patch("automation.node_executor.asyncio.create_subprocess_shell", fake_create_subprocess_shell),
                patch.dict("sys.modules", {"pyperclip": fake_pyperclip}),
            ):
                for node_index, spec in enumerate(nodes):
                    config = dict(spec.get("default_config", {}))
                    node_type = spec["type"]
                    config["timeout"] = 1
                    config["sleep_before_run_seconds"] = 0
                    config.update(
                        {
                            "file_path": str(root / f"{node_index}-{node_type.replace('/', '_')}.csv"),
                            "output_path": str(root / "assets"),
                            "folder_output": str(root / "screenshots"),
                        }
                    )
                    if node_type == "File Upload":
                        config.update(file_type="file", file_path=str(input_file))
                    elif node_type == "Read file/variable":
                        config.update(input_type="file", file_path=str(input_file))
                    elif node_type == "Save asset":
                        config.update(url="https://fixture.invalid/asset.bin", filename="asset.bin")
                    elif node_type == "Open AI":
                        config.update(api_key="test-only", base_url="https://fixture.invalid/v1")
                    elif node_type == "IMAP (Read mail)":
                        config.update(email="test@example.invalid", password="test-only")
                    elif node_type == "Two FA":
                        config.update(secret="JBSWY3DPEHPK3PXP")
                    elif node_type == "Image search":
                        config.update(input_base64_image=template)
                    elif node_type == "Trigger Extension":
                        config.update(extension_url="chrome-extension://fixture/options.html")
                    elif node_type == "Sleep":
                        config.update(seconds=0)
                    elif node_type == "Disconnect":
                        config.update(timeout_before_reconnect=0)
                    elif node_type == "Variables":
                        config.update(custom_variables=[{"name": "simulated_var", "value": "works"}])

                    if node_type == "Write file":
                        config.update(file_path=str(root / "written.txt"))
                    elif node_type == "Cookies":
                        config.update(file_path=str(root / "cookies.json"))
                    elif node_type == "Spreadsheet":
                        config.update(file_path=str(root / "sheet.csv"))
                    elif node_type == "Screenshot":
                        config.update(file_name=f"{node_index}.png")

                    ctx = make_context()
                    if node_type == "Stop":
                        config["stop_browser"] = False
                    node = Node(id=f"sim-{node_index}", type=node_type, config=config)
                    try:
                        result = await executor.run_node(ctx, node)
                        self.assertEqual(result.status, "ok")
                        if result.capability_flags:
                            fallbacks[node_type] = result.capability_flags
                        self._assert_behavior(node_type, result, ctx, root, input_file)
                    except Exception as exc:  # collect the complete catalog report
                        failures.append(f"{node_type}: {type(exc).__name__}: {exc}")

            self.assertFalse(failures, "Node simulation failures:\n" + "\n".join(failures))
            self.assertFalse(fallbacks, f"Unexpected capability fallbacks: {fallbacks}")
            self.assertEqual(len(nodes), 57)

    def _assert_behavior(self, node_type, result, ctx, root, input_file):
        outputs = result.outputs
        effects = ctx.simulated_effects
        page_events = ctx.active_page.events
        expected_output = {
            "Get URL": ("url", "https://fixture.invalid/"),
            "Get Text": ("text", "simulated text"),
            "Get Value": ("value", "simulated value"),
            "Get Attribute": ("attr", "https://fixture.invalid/image.png"),
            "HTTP": ("http_response_status", 200),
            "Open AI": ("ai", "simulated model response"),
            "RegExp (Data extraction)": ("matches", ["123"]),
            "Update field": ("status", "done"),
            "Cmd": ("cmd_out", "simulated stdout"),
            "Get tag": ("tags", ["fixture"]),
            "Profile note": ("profile_note", "saved note"),
            "Eval": ("eval_result", 2),
            "Javascript": ("js_result", "simulated evaluation"),
        }
        if node_type in expected_output:
            key, expected = expected_output[node_type]
            self.assertEqual(outputs.get(key), expected, node_type)
        elif node_type == "Variables":
            self.assertEqual(outputs["simulated_var"], "works")
        elif node_type == "Stop":
            self.assertTrue(ctx.stop_requested)
        elif node_type == "New Tab":
            self.assertIsNot(ctx.active_page, ctx.simulated_original_page)
        elif node_type == "Activate Tab":
            self.assertIs(ctx.active_page, ctx.simulated_original_page)
        elif node_type == "Open URL":
            self.assertEqual(ctx.active_page.url, "https://example.com")
        elif node_type == "Close Tab":
            self.assertTrue(ctx.simulated_original_page.closed)
        elif node_type == "Reload Tab":
            self.assertIn("reload", [event[0] for event in page_events])
        elif node_type == "Click":
            self.assertIn("locator_click", [event[0] for event in page_events])
        elif node_type == "Mouse Movement":
            self.assertIn("mouse_move", [event[0] for event in page_events])
        elif node_type == "Scroll":
            self.assertIn("mouse_wheel", [event[0] for event in page_events])
        elif node_type == "Press Key":
            self.assertIn("press", [event[0] for event in page_events])
        elif node_type == "Type Text":
            self.assertIn("fill", [event[0] for event in page_events])
        elif node_type == "Element Exist":
            self.assertTrue(outputs["exists"])
            self.assertEqual(result.next_label, "true")
        elif node_type == "Select Dropdown":
            self.assertEqual(outputs["selected_option_value"], "1")
        elif node_type == "Random":
            self.assertRegex(outputs["random_value"], r"^user\d+@example\.com$")
        elif node_type == "File Upload":
            self.assertTrue(input_file.exists())
            self.assertIn("set_input_files", [event[0] for event in page_events])
        elif node_type == "Read file/variable":
            self.assertEqual(outputs["lines"], ["fixture line"])
        elif node_type == "Write file":
            self.assertTrue(Path(outputs["written_file"]).is_file())
        elif node_type == "Cookies":
            self.assertTrue(Path(outputs["cookies_path"]).is_file())
            self.assertIn(("cookies",), effects)
        elif node_type == "Save asset":
            self.assertEqual(Path(outputs["asset_path"]).read_bytes(), b"fixture-bytes")
        elif node_type == "Spreadsheet":
            self.assertEqual(outputs["sheet"], [])
        elif node_type == "Case Path":
            self.assertEqual(result.next_label, "success")
        elif node_type == "Insert Data":
            self.assertEqual(outputs["inserted_row"], {"field": "fixture"})
        elif node_type == "IMAP (Read mail)":
            self.assertEqual(outputs["mail"]["count"], 0)
        elif node_type == "Two FA":
            self.assertRegex(outputs["otp"], r"^\d{6}$")
        elif node_type == "Bypass":
            self.assertTrue(outputs["bypassed"])
        elif node_type == "Disconnect":
            self.assertIsNot(ctx.active_page, ctx.simulated_original_page)
        elif node_type == "Update tag":
            self.assertIn(("set_tags", ["processed"]), effects)
        elif node_type == "Image search":
            self.assertTrue(outputs["image"]["image_found"])
        elif node_type == "Screenshot":
            self.assertTrue(Path(outputs["shot"]).is_file())
        elif node_type == "Clipboard":
            self.assertEqual(outputs["clipboard"], "fixture 123")
        elif node_type == "Switch Page":
            self.assertEqual(outputs["active_page_url"], "https://fixture.invalid/")
        elif node_type == "Switch Extension Popup V2":
            self.assertTrue(outputs["active_popup_url"].startswith("chrome-extension://"))
        elif node_type == "Trigger Extension":
            self.assertEqual(ctx.active_page.url, "chrome-extension://fixture/options.html")
        elif node_type == "Dialog/Alert":
            self.assertTrue(ctx.dialog_handler_registered)
        elif node_type == "If":
            self.assertTrue(outputs["if_result"])
            self.assertEqual(result.next_label, "true")
        elif node_type == "Loop":
            self.assertEqual(result.next_label, "loop")
        elif node_type == "Loop V2 - Break loop":
            self.assertEqual(result.next_label, "break")
        elif node_type == "Emulate":
            self.assertIn("set_viewport_size", [event[0] for event in page_events])
        elif node_type in {"Log", "Comment"}:
            self.assertTrue(ctx.simulated_log_entries)


if __name__ == "__main__":
    unittest.main()
