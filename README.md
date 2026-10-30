# IXBrowser Automation System

Hệ thống automation hàng loạt 1000+ IXBrowser profile cho marketing trên X.com, Facebook, TikTok.

## Architecture

```
Telegram → OpenFang → FastAPI → IXBrowser API → Playwright CDP → Page-Agent + GPT-4o
```

| Layer | Technology | Role |
|---|---|---|
| Command Input | Telegram / OpenFang / REST API | Nhận lệnh từ user |
| Orchestrator | Python asyncio + FastAPI | Dispatch tasks, quản lý queue |
| Profile Manager | IXBrowser Local API | Mở/đóng browser profiles |
| Browser Bridge | Playwright CDP | Kết nối đến profile browser |
| AI Agent | Page-Agent + GPT-4o | Thực hiện task bằng NL trên web |

## Windows all-in-one setup

These steps install autoIXB on a fresh Windows 10/11 computer. Python 3.12 is recommended. IXBrowser is needed for browser profiles; ARTEMIS and Android Platform Tools are only needed for phone nodes.

### 1. Install prerequisites

- Install [Python 3.12](https://www.python.org/downloads/) and enable **Add Python to PATH**.
- Install [Git for Windows](https://git-scm.com/download/win).
- Install and sign in to IXBrowser, then enable its Local API at `127.0.0.1:53200`.
- For phone automation, install Android Platform Tools and authorize the phone's ADB connection. Samsung Remote Test Lab phones also need an active reservation and its Remote Debug Bridge (RDB) connection.

### 2. Download and install autoIXB

Open PowerShell:

```powershell
git clone https://github.com/volatoken/codex.git
Set-Location .\codex
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_autoixb.ps1
```

The setup script creates `.venv`, installs `requirements.txt`, installs Playwright Chromium, and copies `.env.example` to `.env` only when `.env` does not already exist. To skip the Chromium download, pass `-SkipBrowserInstall`.

### 3. Configure and run

Review `.env` if you use optional services, then start the local app:

```powershell
notepad .env
.\scripts\run_autoixb_web.ps1
```

Open [http://127.0.0.1:8000/automation/ui](http://127.0.0.1:8000/automation/ui). The API listens on `127.0.0.1:8000`; `API_BEARER_TOKEN` is blank by default for local use. Set a strong token before exposing the API to another computer or network. IXBrowser must be running on the same computer as autoIXB.

`OPENAI_API_KEY` is needed only for tasks that use the Page-Agent / LLM integration. `TELEGRAM_BOT_TOKEN` is needed only for Telegram. The no-code editor and browser workflow API can be used without either credential.

### 4. Optional ARTEMIS phone setup

The autoIXB package includes its ARTEMIS bridge, but ARTEMIS itself must be installed locally. Clone it beside the autoIXB folder, then run its Windows setup:

```powershell
Set-Location ..
git clone https://github.com/google/artemis.git
Set-Location .\artemis
.\start.bat
```

ARTEMIS's setup provisions its required toolchains and Python environment. Return to the autoIXB folder and configure these entries in `.env`:

```dotenv
ARTEMIS_ROOT=..\artemis
ARTEMIS_PYTHON=
ADB_PATH=adb
```

The default ARTEMIS path is a sibling checkout beside `codex`; a blank `ARTEMIS_PYTHON` auto-detects its `.venv`. Set absolute paths if you installed it elsewhere. Ensure `adb` is on `PATH`. For **Install APKs**, set `ADB_PATH` to the Android SDK's full `platform-tools\adb.exe` path and install Android SDK Build Tools so `aapt.exe` is available. The first helper-enabled connection may ask you to enable the ARTEMIS Accessibility Helper on the phone. Stop ARTEMIS's standalone web UI before starting autoIXB if both are configured to use port 8000.

For a Samsung Remote Test Lab device, reserve/start the phone in Samsung's web client, open **Remote Debug Bridge**, and connect RDB from the host first. Then choose the live ADB serial in autoIXB. ADB being installed on the PC alone does not create the Samsung remote-device session.

### 5. Start automatically on later sessions

```powershell
Set-Location .\codex
.\scripts\run_autoixb_web.ps1
```

The launcher uses the project's `.venv` first, then Python on `PATH` (or Python 3.12 through the Windows `py` launcher). Set `AUTOIXB_PYTHON` to override the executable.

### 6. No-Code Builder UI

Open in browser:

```bash
http://localhost:8000/automation/ui
```

Static assets are served from:

```bash
http://localhost:8000/automation-ui/
```

If `API_BEARER_TOKEN` is set, enter the token in the UI `Bearer Token` field.

### Record and replay phone actions

Set `ARTEMIS_ROOT`, `ARTEMIS_PYTHON`, and `ADB_PATH` in `.env` for the local ARTEMIS checkout, its virtual environment, and Android platform-tools. Keep the target phone connected and authorized in ADB, then open **Ghi thao tác phone** in App Editor and choose its exact serial.

The recorder saves taps, long presses, swipes, text entry, Back, and Home. Mark segment boundaries while recording, then finish and choose **Tạo app con và app cha**. Each segment becomes a child app; the parent connects to the selected phone, calls those apps in order, and can repeat them on the same ARTEMIS session. Text is treated as sensitive by default; clear the sensitive checkbox only for text you want retained in the draft.

Recorded taps use a unique ARTEMIS accessibility selector first when available and add a phone screenshot crop as a visual fallback. **Thử khớp** previews the match score and expected screen position. If no unique selector exists, the generated child uses **ARTEMIS Tap Image**. These nodes match on the Android screenshot and are separate from Chromium's **Image search** node.

Use **Analyze Error** from the **Other** palette to diagnose a failed node. Connect the failed node's red **error** output to it; the output variable contains the failed node, error/traceback, likely cause, and suggested fix. Phone accessibility context is optional and off by default. Retry suggestions are off by default, limited to read-only nodes, and require wiring **true** back to the failed node; connect **false** to logging, recovery, or Stop. It never retries clicks, text entry, installs, or other potentially repeated actions.

The external [android-reverse-engineering-skill](https://github.com/SimoneAvogadro/android-reverse-engineering-skill) is a static APK analysis workflow, not a runtime library that autoIXB can call directly. For APK/package/activity failures, Analyze Error points to checking the manifest and code flow with that workflow/JADX; runtime failures are diagnosed from autoIXB's node error and optional ARTEMIS accessibility counts.

Use **Call App** to compose saved workflows. Export a saved parent with **Export app bundle** to include its child apps and referenced phone images; importing the ZIP remaps those references. Deleting a draft or an app removes phone image assets only after no other saved app or draft references them.

## Usage

### Via Telegram Bot

```
/profiles              – Xem danh sách profiles
/templates             – Xem task templates
/run x post_tweet content="Hello from automation!"
/run facebook like_post
/run generic warm_up
/status <batch_id>     – Kiểm tra tiến độ
/stop <batch_id>       – Hủy batch
```

Interactive mode: gõ `/run` → chọn platform → chọn task → nhập nội dung.

### Via REST API

```bash
# Execute task on all profiles
curl -X POST http://localhost:8000/tasks/execute \
  -H "Content-Type: application/json" \
  -d '{"platform": "x", "task_type": "post_tweet", "params": {"content": "Hello!"}}'

# Filter by tag
curl -X POST http://localhost:8000/tasks/execute \
  -d '{"platform": "x", "task_type": "like_tweet", "params": {"target_user": "elonmusk"}, "tag_id": 5}'

# Check status
curl http://localhost:8000/tasks/{batch_id}/status

# List profiles
curl http://localhost:8000/profiles

# List templates
curl http://localhost:8000/templates
```

### Via OpenFang

1. Start the MCP server:
```bash
python -m openfang.mcp_server
```

2. Configure OpenFang to connect:
```toml
# In OpenFang config
[[mcp.servers]]
name = "ixbrowser"
command = "python"
args = ["-m", "openfang.mcp_server"]
```

3. OpenFang agents can now use tools:
   - `execute_task` – Run automation tasks
   - `list_profiles` – View profiles
   - `get_task_status` – Monitor batches
   - `list_templates` – See available tasks
   - `stop_batch` – Cancel tasks

### Via Codex

autoIXB provides a local MCP bridge for Codex to inspect the node catalog and profiles, create or update workflow graphs, validate them, and run a browser test against one explicitly selected IXBrowser profile. See [integrations/codex/README.md](integrations/codex/README.md) for setup and safety details.

## Project Structure

```
codex/
├── config/
│   ├── settings.py           # Pydantic settings (.env)
│   └── task_templates.yaml   # Task prompt templates
├── core/
│   ├── profile_manager.py    # IXBrowser profile lifecycle
│   ├── browser_agent.py      # Playwright CDP + Page-Agent bridge
│   ├── task_queue.py         # Async queue with concurrency control
│   ├── task_registry.py      # YAML template resolver
│   └── orchestrator.py       # Central coordinator
├── api/
│   └── server.py             # FastAPI REST + WebSocket
├── telegram_bot/
│   └── bot.py                # Telegram bot interface
├── openfang/
│   ├── mcp_server.py         # MCP server for OpenFang
│   └── skill.md              # OpenFang skill definition
├── integrations/
│   └── codex/                 # Local MCP bridge for Codex
├── assets/
│   └── page_agent_inject.js  # Page-Agent JS injection helper
├── main.py                   # Entry point
├── requirements.txt
└── .env.example
```

## Task Templates

Defined in `config/task_templates.yaml`. Add your own:

```yaml
platforms:
  x:
    tasks:
      my_custom_task:
        prompt: "Do something specific: {my_param}"
        url: "https://x.com/{target_user}"
        min_delay: 3
        max_delay: 8
```

Use `{variable}` placeholders → filled from `params` at runtime.

## Key Constraints

- **IXBrowser API limit**: Max 3 concurrent requests → enforced by Semaphore
- **Page-Agent**: AI-powered, resilient to UI changes (no CSS selectors to maintain)
- **Anti-detection**: Random delays between actions (`min_delay`/`max_delay` per task)
- **Retries**: Failed tasks retry up to `TASK_MAX_RETRIES` times automatically

## How It Works

1. **Command received** (Telegram/API/OpenFang)
2. **Orchestrator** resolves template → finds matching profiles → creates TaskItems
3. **TaskQueue** dispatches max 3 concurrent workers
4. Each worker: **open IXBrowser profile** → get CDP endpoint → **Playwright connects** → **inject Page-Agent JS** → AI executes NL task → collect result → **close profile**
5. Results reported back to caller

## n8n custom node

This repository includes a private n8n node for running saved browser automations and returning per-profile results. See [`integrations/n8n/README.md`](integrations/n8n/README.md) for the credential, local build, install, and sample workflow steps.
