# autoIXB MCP for Codex

This local MCP server gives Codex read access to autoIXB workflows, node definitions, and IXBrowser profiles. It can validate graphs, save a workflow when requested, run a live test against one selected profile, inspect the result, and stop a run.

## Requirements

- autoIXB is running on this computer (default API: `http://127.0.0.1:8000`).
- The Python environment used by Codex has the packages from the project `requirements.txt` installed, including `mcp` and `httpx`.
- If `API_BEARER_TOKEN` is set in the project `.env`, the MCP process reads the same `.env` and uses that token locally. The token is never returned to Codex.

## Connect Codex

From the autoIXB repository root in a terminal where `codex` is available, run:

```powershell
$repoRoot = (Resolve-Path .).Path
codex mcp add autoixb -- python "$repoRoot\integrations\codex\mcp_server.py"
```

Then restart Codex and check the MCP server list. The Codex desktop app, CLI, and IDE extension share the host MCP configuration. The default MCP API address can be changed with `AUTOIXB_API_BASE_URL`, but the server only accepts loopback URLs.

The recommended approval policy for this MCP server is `writes`: read-only discovery and graph validation can proceed without approval, while creating/updating workflows, starting browser runs, and stopping runs require Codex approval.

## Typical prompt workflow

1. Ask Codex to inspect the node catalog and profiles, then describe the requested workflow plan.
2. Codex builds a complete graph with nodes, configs, and edges and calls `validate_automation_graph`.
3. When asked to save, Codex creates or updates the workflow and returns its app ID.
4. For a test, Codex selects one exact profile ID from the profile list and starts one run with zero retries and concurrency one.
5. Codex polls `get_automation_run` and may read sanitized logs. It can stop the run when requested.

Example:

> Tạo workflow kiểm tra trang đăng nhập trên profile `qa-s24`. Xem node/profile trước, đề xuất các bước, validate rồi lưu thành app. Chưa chạy browser cho đến khi tôi yêu cầu test.

Then:

> Chạy test app `<app_id>` trên đúng profile `qa-s24`, xem kết quả và dừng nếu gặp lỗi.

## Safety and data handling

- `run_automation_test` requires one numeric profile ID and an explicit confirmation field. It never accepts a group/tag/all-profile selection, sets concurrency to 1, disables retries, and leaves the IXBrowser profile open after completion.
- Codex marks all non-read-only actions as approval-required through the configured `writes` policy.
- App reads replace values under password, secret, token, API key, authorization, cookie, and credential keys with `[REDACTED]`. Updating an existing graph restores unchanged `[REDACTED]` values from the saved app.
- Run summaries omit browser output values and variables. Logs redact common token/password/email patterns.
- The MCP bridge is stdio-only and talks to the autoIXB API over loopback. Do not expose the local API without configuring `API_BEARER_TOKEN`.
