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

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required:**
- `OPENAI_API_KEY` – GPT-4o API key cho Page-Agent
- `TELEGRAM_BOT_TOKEN` – Telegram bot token (nếu dùng Telegram)
- IXBrowser phải đang chạy trên local machine

### 3. Run

```bash
python main.py
```

Starts both FastAPI server (port 8000) and Telegram bot.

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
├── telegram/
│   └── bot.py                # Telegram bot interface
├── openfang/
│   ├── mcp_server.py         # MCP server for OpenFang
│   └── skill.md              # OpenFang skill definition
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
