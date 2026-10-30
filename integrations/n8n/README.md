# AutoIXB node for n8n

This private n8n node connects to the existing autoIXB FastAPI service. The browser automation graphs and saved tasks remain in autoIXB; n8n starts them, waits for completion, and receives one result item per profile.

## Current operations

| Resource | Operation | Purpose |
| --- | --- | --- |
| Automation | List Apps / List Tasks / List Profiles | Discover saved autoIXB resources and IXBrowser profiles |
| Automation | Run App | Execute a saved graph against explicitly selected profile IDs, group, tag, or all profiles |
| Automation | Run Saved Task | Execute its saved inputs and profile selector |
| Run | Get / Stop | Check or stop an existing run |

Runs default to concurrency `1`, zero retries, and a 300-second per-profile timeout. Waiting returns each profile's status and result. A n8n `Idempotency-Key` protects against n8n retrying the same start request and creating a second browser run. The key is retained by autoIXB for seven days.

The node refuses an unfiltered app run. “All Profiles” requires a separate confirmation toggle. A saved task with no profile filter also fails unless “Allow All When Task Has No Selection” is explicitly enabled. This guards against accidentally starting browser actions on every profile.

## Configure API authentication

If `API_BEARER_TOKEN` is configured in autoIXB's local `.env`, set the same value in a new n8n credential of type **AutoIXB API**. Do not commit `.env`. The token field can be blank only while API auth is disabled; keep autoIXB bound to localhost in that case. The credential's Base URL must be reachable from the n8n process:

- n8n and autoIXB running directly on this Windows machine: `http://127.0.0.1:8000`
- n8n running in Docker: use the Windows host address reachable from the container, not container-local `127.0.0.1`

The existing API accepts requests without a token when `API_BEARER_TOKEN` is blank. Configure a token before exposing autoIXB beyond localhost.

## Build and install on the current Windows n8n

From this folder (the npm cache/log folders below are local temporary paths and may be changed):

```powershell
$env:npm_config_cache = Join-Path $env:LOCALAPPDATA 'autoixb-npm-cache'
$env:npm_config_logs_dir = Join-Path $env:LOCALAPPDATA 'autoixb-npm-logs'
npm ci
npm run build
npm test
Push-Location (Resolve-Path ..\..)
python -m unittest discover -s tests
Pop-Location
```

Set `$N8nRoot` to the folder containing your n8n installation, then install the compiled node and restart n8n:

```powershell
$N8nRoot = 'C:\path\to\n8n'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-local.ps1 -N8nRoot $N8nRoot -Restart
```

The installer checks the n8n folder, backs up any previous AutoIXB node files, copies only this node's compiled JavaScript and icon, and can restart the current n8n process. It does not change the n8n database or other custom nodes. Use `-Restart` only when no workflow executions are active.

To load an update later, rebuild and rerun the install script. To remove the node, remove the `data\.n8n\custom\autoixb` folder under your n8n data directory; credentials already saved in n8n remain in n8n's encrypted database.

## Import a sample workflow

Import `workflows/autoixb-list-profiles.json`, then select the AutoIXB API credential. It returns one output item per IXBrowser profile. For a real browser run, add the node, choose **Automation → Run App**, select an app, and select the profile IDs that the app may control.

## n8n data and privacy

When **Include Result Details** is enabled, browser text and other app output are stored in normal n8n execution data. Disable it when the workflow only needs run status. The node does not attach screenshots or log page contents by itself. Browser graphs can still return page data through their configured result variables.

## Development

The package uses the `n8n-workflow` 2.42 API surface that ships with the current local n8n installation. The node uses n8n's authenticated HTTP helper so instance egress and SSRF controls apply to requests. The package is intended for this private autoIXB instance; it is not published to npm.
