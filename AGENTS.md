# Codex workflow automation guidance

When the user asks to design or edit an autoIXB browser automation, use the `autoixb` MCP tools when available:

1. Read `get_node_catalog`; inspect existing workflows and matching IXBrowser profiles before editing.
2. Build the complete node graph from supported node types and defaults, then call `validate_automation_graph` before saving.
3. Save only when the user asks to create or update the workflow. Preserve `[REDACTED]` configuration values exactly when updating an existing app.
4. A live browser test must target one exact profile ID selected from `list_ixbrowser_profiles`. Never broaden a test to all profiles, groups, or tags. Use the live-run tool only after the user asks to run the test and Codex approves the write action.
5. After starting a test, poll the run status and report per-node outcomes. Do not expose passwords, tokens, cookies, or raw output values.
