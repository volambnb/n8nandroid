from __future__ import annotations

import json
import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


def _now() -> float:
    return time.time()


class AutomationStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS mini_apps (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    graph_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS saved_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (app_id) REFERENCES mini_apps(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS run_batches (
                    id TEXT PRIMARY KEY,
                    app_id TEXT,
                    task_id TEXT,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    stop_requested INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL
                );

                CREATE TABLE IF NOT EXISTS run_items (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL,
                    finished_at REAL,
                    error TEXT,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (run_id) REFERENCES run_batches(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS run_idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    request_hash TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES run_batches(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS run_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    run_item_id TEXT,
                    ts REAL NOT NULL,
                    level TEXT NOT NULL,
                    node_id TEXT,
                    message TEXT NOT NULL,
                    data_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    interval_seconds INTEGER,
                    cron_expr TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    input_overrides_json TEXT NOT NULL DEFAULT '{}',
                    next_run_at REAL,
                    last_run_at REAL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES saved_tasks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS profile_metadata (
                    profile_id TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (profile_id, field)
                );

                CREATE TABLE IF NOT EXISTS global_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phone_recordings (
                    id TEXT PRIMARY KEY,
                    serial TEXT NOT NULL,
                    status TEXT NOT NULL,
                    events_json TEXT NOT NULL DEFAULT '[]',
                    segments_json TEXT NOT NULL DEFAULT '[]',
                    assets_json TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS phone_image_assets (
                    id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    mime_type TEXT NOT NULL DEFAULT 'image/png',
                    data BLOB NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )
            recording_columns = {row["name"] for row in conn.execute("PRAGMA table_info(phone_recordings)")}
            if "assets_json" not in recording_columns:
                conn.execute("ALTER TABLE phone_recordings ADD COLUMN assets_json TEXT NOT NULL DEFAULT '[]'")
            conn.commit()
        finally:
            conn.close()

    # ---- apps ----
    def create_app(self, name: str, description: str, graph: dict[str, Any]) -> dict[str, Any]:
        app_id = uuid.uuid4().hex[:12]
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO mini_apps(id, name, description, graph_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (app_id, name, description, json.dumps(graph), now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_app(app_id)

    def create_app_bundle(self, apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _now()
        created = [{**item, "id": str(item.get("id") or uuid.uuid4().hex[:12])} for item in apps]
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for item in created:
                conn.execute(
                    "INSERT INTO mini_apps(id, name, description, graph_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (item["id"], item["name"], item.get("description", ""), json.dumps(item["graph"], ensure_ascii=False), now, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return [self.get_app(item["id"]) for item in created]

    def list_apps(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, name, description, version, created_at, updated_at FROM mini_apps ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_app(self, app_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM mini_apps WHERE id = ?", (app_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["graph"] = json.loads(data.pop("graph_json"))
            return data
        finally:
            conn.close()

    def update_app(
        self,
        app_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        graph: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        existing = self.get_app(app_id)
        if not existing:
            return None
        name = name if name is not None else existing["name"]
        description = description if description is not None else existing["description"]
        graph_obj = graph if graph is not None else existing["graph"]
        old_assets = self._collect_phone_asset_ids(existing["graph"])
        version = int(existing["version"]) + 1
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE mini_apps
                SET name = ?, description = ?, graph_json = ?, version = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, description, json.dumps(graph_obj), version, now, app_id),
            )
            self._delete_orphan_phone_assets(conn, old_assets)
            conn.commit()
        finally:
            conn.close()
        return self.get_app(app_id)

    def delete_app(self, app_id: str) -> bool:
        conn = self._conn()
        try:
            target = conn.execute("SELECT graph_json FROM mini_apps WHERE id = ?", (app_id,)).fetchone()
            if not target:
                return False
            candidates = self._collect_phone_asset_ids(json.loads(target["graph_json"]))
            rows = conn.execute("SELECT id, graph_json FROM mini_apps WHERE id != ?", (app_id,)).fetchall()
            for row in rows:
                graph = json.loads(row["graph_json"])
                if any(str(node.get("type", "")).lower().replace(" ", "_") == "call_app"
                       and str((node.get("config") or {}).get("app_id", "")) == app_id
                       for node in graph.get("nodes", [])):
                    raise ValueError(f"App {app_id} is referenced by app {row['id']} and cannot be deleted.")
            cur = conn.execute("DELETE FROM mini_apps WHERE id = ?", (app_id,))
            self._delete_orphan_phone_assets(conn, candidates)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def create_phone_recording(self, session_id: str, serial: str) -> dict[str, Any]:
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO phone_recordings(id, serial, status, created_at, updated_at) VALUES (?, ?, 'recording', ?, ?)",
                (session_id, serial, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_phone_recording(session_id)  # type: ignore[return-value]

    def get_phone_recording(self, session_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["events"] = json.loads(data.pop("events_json"))
            data["segments"] = json.loads(data.pop("segments_json"))
            data["assets"] = json.loads(data.pop("assets_json", "[]"))
            return data
        finally:
            conn.close()

    def set_phone_recording_serial(self, session_id: str, serial: str) -> None:
        """Rebind a paused/stopped draft without touching its recorded events."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE phone_recordings SET serial = ?, updated_at = ? "
                "WHERE id = ? AND status IN ('paused', 'stopped')",
                (serial, _now(), session_id),
            )
            if cur.rowcount == 0:
                row = conn.execute(
                    "SELECT status FROM phone_recordings WHERE id = ?", (session_id,)
                ).fetchone()
                if not row:
                    raise ValueError("Phone recording session not found.")
                raise ValueError("Pause the phone recorder before changing its device.")
            conn.commit()
        finally:
            conn.close()

    def list_phone_recordings(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM phone_recordings ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(200, int(limit))),),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["events"] = json.loads(item.pop("events_json"))
                item["segments"] = json.loads(item.pop("segments_json"))
                item["assets"] = json.loads(item.pop("assets_json", "[]"))
                result.append(item)
            return result
        finally:
            conn.close()

    def append_phone_recording_event(self, session_id: str, event: dict[str, Any]) -> int:
        conn = self._conn()
        try:
            row = conn.execute("SELECT events_json FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Phone recording session not found.")
            events = json.loads(row["events_json"])
            event["index"] = len(events) + 1
            events.append(event)
            conn.execute("UPDATE phone_recordings SET events_json = ?, updated_at = ? WHERE id = ?",
                         (json.dumps(events, ensure_ascii=False), _now(), session_id))
            conn.commit()
            return int(event["index"])
        finally:
            conn.close()

    def update_phone_recording_event(self, session_id: str, event_index: int, patch: dict[str, Any]) -> dict[str, Any]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT events_json FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Phone recording session not found.")
            events = json.loads(row["events_json"])
            if event_index < 1 or event_index > len(events):
                raise ValueError("Recording event index is invalid.")
            old_asset = str(events[event_index - 1].get("image_asset_id") or "")
            events[event_index - 1].update(patch)
            conn.execute("UPDATE phone_recordings SET events_json = ?, updated_at = ? WHERE id = ?",
                         (json.dumps(events, ensure_ascii=False), _now(), session_id))
            if old_asset and old_asset != str(events[event_index - 1].get("image_asset_id") or ""):
                self._delete_orphan_phone_assets(conn, {old_asset})
            conn.commit()
            return events[event_index - 1]
        finally:
            conn.close()

    def append_phone_recording_segment(self, session_id: str, name: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            row = conn.execute("SELECT segments_json FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Phone recording session not found.")
            segments = json.loads(row["segments_json"])
            segment = {"id": uuid.uuid4().hex[:10], "name": str(name).strip()[:100], "start_event": 1 if not segments else int(segments[-1]["end_event"]) + 1,
                       "end_event": len(json.loads(conn.execute("SELECT events_json FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()["events_json"]))}
            if segment["end_event"] < segment["start_event"]:
                raise ValueError("Record at least one phone action before marking a segment.")
            segments.append(segment)
            conn.execute("UPDATE phone_recordings SET segments_json = ?, updated_at = ? WHERE id = ?",
                         (json.dumps(segments, ensure_ascii=False), _now(), session_id))
            conn.commit()
            return segment
        finally:
            conn.close()

    def delete_phone_recording(self, session_id: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute("SELECT events_json, assets_json FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return False
            candidates = self._collect_phone_asset_ids(json.loads(row["events_json"]))
            candidates.update(str(asset_id) for asset_id in json.loads(row["assets_json"] or "[]"))
            cur = conn.execute("DELETE FROM phone_recordings WHERE id = ?", (session_id,))
            self._delete_orphan_phone_assets(conn, candidates)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def _collect_phone_asset_ids(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            asset_id = value.get("image_asset_id")
            if asset_id:
                found.add(str(asset_id))
            for child in value.values():
                found.update(AutomationStore._collect_phone_asset_ids(child))
        elif isinstance(value, list):
            for child in value:
                found.update(AutomationStore._collect_phone_asset_ids(child))
        return found

    def _delete_orphan_phone_assets(self, conn: sqlite3.Connection, candidates: set[str]) -> None:
        if not candidates:
            return
        referenced: set[str] = set()
        try:
            for row in conn.execute("SELECT events_json, assets_json FROM phone_recordings"):
                referenced.update(self._collect_phone_asset_ids(json.loads(row["events_json"])))
                referenced.update(str(asset_id) for asset_id in json.loads(row["assets_json"] or "[]"))
            for row in conn.execute("SELECT graph_json FROM mini_apps"):
                referenced.update(self._collect_phone_asset_ids(json.loads(row["graph_json"])))
        except (TypeError, json.JSONDecodeError):
            # Keep candidate assets if any persisted reference cannot be inspected safely.
            return
        for asset_id in candidates - referenced:
            conn.execute("DELETE FROM phone_image_assets WHERE id = ?", (asset_id,))

    def cleanup_orphan_phone_assets(self, candidates: set[str]) -> None:
        conn = self._conn()
        try:
            self._delete_orphan_phone_assets(conn, {str(asset_id) for asset_id in candidates})
            conn.commit()
        finally:
            conn.close()

    def attach_phone_recording_asset(self, session_id: str, asset_id: str) -> None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT assets_json FROM phone_recordings WHERE id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Phone recording session not found.")
            assets = json.loads(row["assets_json"] or "[]")
            if asset_id not in assets:
                assets.append(asset_id)
            conn.execute("UPDATE phone_recordings SET assets_json = ?, updated_at = ? WHERE id = ?",
                         (json.dumps(assets), _now(), session_id))
            conn.commit()
        finally:
            conn.close()

    def set_phone_recording_status(self, session_id: str, status: str) -> None:
        conn = self._conn()
        try:
            cur = conn.execute("UPDATE phone_recordings SET status = ?, updated_at = ? WHERE id = ?",
                               (status, _now(), session_id))
            conn.commit()
            if cur.rowcount == 0:
                raise ValueError("Phone recording session not found.")
        finally:
            conn.close()

    def put_phone_image_asset(self, data: bytes, name: str = "Phone image") -> str:
        digest = hashlib.sha256(data).hexdigest()
        asset_id = uuid.uuid4().hex[:16]
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO phone_image_assets(id, sha256, name, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (asset_id, digest, str(name)[:120], sqlite3.Binary(data), _now()),
            )
            row = conn.execute("SELECT id FROM phone_image_assets WHERE sha256 = ?", (digest,)).fetchone()
            conn.commit()
            return str(row["id"])
        finally:
            conn.close()

    def get_phone_image_asset(self, asset_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM phone_image_assets WHERE id = ?", (asset_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_phone_image_assets(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT id, sha256, name, mime_type, created_at FROM phone_image_assets ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ---- tasks ----
    def create_task(self, name: str, app_id: str, config: dict[str, Any]) -> dict[str, Any]:
        task_id = uuid.uuid4().hex[:12]
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO saved_tasks(id, name, app_id, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, name, app_id, json.dumps(config), now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_task(task_id)  # type: ignore[return-value]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM saved_tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["config"] = json.loads(data.pop("config_json"))
            return data
        finally:
            conn.close()

    def list_tasks(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, name, app_id, config_json, created_at, updated_at FROM saved_tasks ORDER BY updated_at DESC"
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["config"] = json.loads(item.pop("config_json"))
                out.append(item)
            return out
        finally:
            conn.close()

    def update_task(
        self,
        task_id: str,
        *,
        name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        existing = self.get_task(task_id)
        if not existing:
            return None
        payload_name = name if name is not None else existing["name"]
        payload_cfg = config if config is not None else existing["config"]
        now = _now()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE saved_tasks
                SET name = ?, config_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (payload_name, json.dumps(payload_cfg), now, task_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute("DELETE FROM saved_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ---- runs ----
    def create_run(
        self,
        *,
        app_id: str | None,
        task_id: str | None,
        request: dict[str, Any],
        summary: dict[str, Any],
        idempotency_key: str | None = None,
        idempotency_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now()
        request_hash = hashlib.sha256(
            json.dumps(
                {"app_id": app_id, "task_id": task_id, "request": idempotency_request if idempotency_request is not None else request},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        run_id = uuid.uuid4().hex[:12]
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                # Keep a bounded retry window while allowing a later execution to reuse its key.
                conn.execute(
                    "DELETE FROM run_idempotency_keys WHERE created_at < ?",
                    (now - 7 * 24 * 60 * 60,),
                )
                existing = conn.execute(
                    "SELECT request_hash, run_id FROM run_idempotency_keys WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise ValueError("Idempotency-Key was already used with a different request")
                    row = conn.execute(
                        "SELECT * FROM run_batches WHERE id = ?", (existing["run_id"],)
                    ).fetchone()
                    if row is not None:
                        data = dict(row)
                        data["request"] = json.loads(data.pop("request_json"))
                        data["summary"] = json.loads(data.pop("summary_json"))
                        data["idempotency_reused"] = True
                        conn.commit()
                        return data

            conn.execute(
                """
                INSERT INTO run_batches(
                    id, app_id, task_id, status, request_json, summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, app_id, task_id, "queued", json.dumps(request), json.dumps(summary), now),
            )
            if idempotency_key:
                conn.execute(
                    """
                    INSERT INTO run_idempotency_keys(idempotency_key, request_hash, run_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (idempotency_key, request_hash, run_id, now),
                )
            conn.commit()
        finally:
            conn.close()
        created = self.get_run(run_id)  # type: ignore[assignment]
        if created is not None:
            created["idempotency_reused"] = False
        return created  # type: ignore[return-value]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM run_batches WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["request"] = json.loads(data.pop("request_json"))
            data["summary"] = json.loads(data.pop("summary_json"))
            return data
        finally:
            conn.close()

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM run_batches
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["request"] = json.loads(data.pop("request_json"))
                data["summary"] = json.loads(data.pop("summary_json"))
                out.append(data)
            return out
        finally:
            conn.close()

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        summary: dict[str, Any] | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
        stop_requested: bool | None = None,
    ) -> None:
        updates: list[str] = []
        values: list[Any] = []
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if summary is not None:
            updates.append("summary_json = ?")
            values.append(json.dumps(summary))
        if started_at is not None:
            updates.append("started_at = ?")
            values.append(started_at)
        if finished_at is not None:
            updates.append("finished_at = ?")
            values.append(finished_at)
        if stop_requested is not None:
            updates.append("stop_requested = ?")
            values.append(int(stop_requested))
        if not updates:
            return
        conn = self._conn()
        try:
            conn.execute(f"UPDATE run_batches SET {', '.join(updates)} WHERE id = ?", (*values, run_id))
            conn.commit()
        finally:
            conn.close()

    def upsert_run_item(
        self,
        *,
        run_id: str,
        run_item_id: str,
        profile_id: str,
        status: str,
        started_at: float | None = None,
        finished_at: float | None = None,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        result = result or {}
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO run_items(
                    id, run_id, profile_id, status, started_at, finished_at, error, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    error = excluded.error,
                    result_json = excluded.result_json
                """,
                (
                    run_item_id,
                    run_id,
                    profile_id,
                    status,
                    started_at,
                    finished_at,
                    error,
                    json.dumps(result),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_run_items(self, run_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM run_items WHERE run_id = ? ORDER BY profile_id ASC", (run_id,)
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["result"] = json.loads(data.pop("result_json"))
                out.append(data)
            return out
        finally:
            conn.close()

    def refresh_run_summary(self, run_id: str, *, recover_stopped: bool = False) -> dict[str, Any] | None:
        """Recompute a run's terminal state from its items in one serialized transaction.

        A stop request is durable intent: queued profiles must not remain pending
        forever if the process was restarted before the queue drained. A caller
        that knows the previous process is gone may also cancel orphaned running
        items, since no worker can still complete them.
        """
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            run = conn.execute(
                "SELECT status, stop_requested, finished_at FROM run_batches WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                conn.rollback()
                return None

            if bool(run["stop_requested"]) and recover_stopped:
                conn.execute(
                    """
                    UPDATE run_items
                    SET status = 'cancelled', finished_at = COALESCE(finished_at, ?),
                        error = COALESCE(error, 'Run stop requested')
                    WHERE run_id = ? AND status = 'pending'
                    """,
                    (_now(), run_id),
                )
                conn.execute(
                    """
                    UPDATE run_items
                    SET status = 'cancelled', finished_at = COALESCE(finished_at, ?),
                        error = COALESCE(error, 'Run was stopped before the worker restarted')
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (_now(), run_id),
                )

            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM run_items WHERE run_id = ? GROUP BY status",
                (run_id,),
            ).fetchall()
            summary = {"total": 0, "pending": 0, "running": 0, "done": 0, "failed": 0, "cancelled": 0}
            for row in rows:
                count = int(row["count"])
                summary["total"] += count
                if row["status"] in summary:
                    summary[row["status"]] += count

            if summary["running"] or summary["pending"]:
                status = "running"
                finished_at = run["finished_at"]
            elif bool(run["stop_requested"]) and summary["cancelled"] > 0:
                status = "cancelled"
                finished_at = run["finished_at"] or _now()
            elif summary["failed"] > 0:
                status = "failed"
                finished_at = run["finished_at"] or _now()
            elif summary["total"] > 0 and summary["done"] == summary["total"]:
                status = "done"
                finished_at = run["finished_at"] or _now()
            elif summary["total"] > 0 and summary["cancelled"] == summary["total"]:
                status = "cancelled"
                finished_at = run["finished_at"] or _now()
            else:
                status = run["status"]
                finished_at = run["finished_at"]

            conn.execute(
                "UPDATE run_batches SET status = ?, summary_json = ?, finished_at = ? WHERE id = ?",
                (status, json.dumps(summary), finished_at, run_id),
            )
            conn.commit()
            return {"status": status, "summary": summary, "finished_at": finished_at}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def append_log(
        self,
        *,
        run_id: str,
        run_item_id: str | None,
        level: str,
        message: str,
        node_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO run_logs(run_id, run_item_id, ts, level, node_id, message, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, run_item_id, _now(), level, node_id, message, json.dumps(data or {})),
            )
            conn.commit()
        finally:
            conn.close()

    def get_logs(self, run_id: str, *, after_id: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM run_logs
                WHERE run_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (run_id, after_id, limit),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["data"] = json.loads(data.pop("data_json"))
                out.append(data)
            return out
        finally:
            conn.close()

    # ---- schedules ----
    def create_schedule(
        self,
        *,
        name: str,
        task_id: str,
        interval_seconds: int | None,
        cron_expr: str | None,
        enabled: bool,
        input_overrides: dict[str, Any],
    ) -> dict[str, Any]:
        schedule_id = uuid.uuid4().hex[:12]
        now = _now()
        next_run_at = now + interval_seconds if interval_seconds else now + 60
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO schedules(
                    id, name, task_id, interval_seconds, cron_expr, enabled,
                    input_overrides_json, next_run_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule_id,
                    name,
                    task_id,
                    interval_seconds,
                    cron_expr,
                    int(enabled),
                    json.dumps(input_overrides),
                    next_run_at,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_schedule(schedule_id)  # type: ignore[return-value]

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["enabled"] = bool(data["enabled"])
            data["input_overrides"] = json.loads(data.pop("input_overrides_json"))
            return data
        finally:
            conn.close()

    def list_schedules(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM schedules ORDER BY updated_at DESC").fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["enabled"] = bool(data["enabled"])
                data["input_overrides"] = json.loads(data.pop("input_overrides_json"))
                out.append(data)
            return out
        finally:
            conn.close()

    def update_schedule(self, schedule_id: str, **fields: Any) -> dict[str, Any] | None:
        existing = self.get_schedule(schedule_id)
        if not existing:
            return None
        payload = {
            "name": fields.get("name", existing["name"]),
            "interval_seconds": fields.get("interval_seconds", existing["interval_seconds"]),
            "cron_expr": fields.get("cron_expr", existing["cron_expr"]),
            "enabled": int(fields.get("enabled", existing["enabled"])),
            "input_overrides_json": json.dumps(
                fields.get("input_overrides", existing["input_overrides"])
            ),
            "updated_at": _now(),
            "next_run_at": existing["next_run_at"],
            "id": schedule_id,
        }
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE schedules
                SET name = ?, interval_seconds = ?, cron_expr = ?, enabled = ?,
                    input_overrides_json = ?, updated_at = ?, next_run_at = ?
                WHERE id = ?
                """,
                (
                    payload["name"],
                    payload["interval_seconds"],
                    payload["cron_expr"],
                    payload["enabled"],
                    payload["input_overrides_json"],
                    payload["updated_at"],
                    payload["next_run_at"],
                    payload["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_schedule(schedule_id)

    def delete_schedule(self, schedule_id: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def due_schedules(self, now_ts: float) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM schedules
                WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now_ts,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                data["enabled"] = bool(data["enabled"])
                data["input_overrides"] = json.loads(data.pop("input_overrides_json"))
                out.append(data)
            return out
        finally:
            conn.close()

    def mark_schedule_run(self, schedule_id: str, *, now_ts: float, next_run_at: float | None) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE schedules
                SET last_run_at = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now_ts, next_run_at, now_ts, schedule_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ---- profile metadata fallback ----
    def update_profile_field(self, profile_id: str, field: str, value: str) -> None:
        conn = self._conn()
        now = _now()
        try:
            conn.execute(
                """
                INSERT INTO profile_metadata(profile_id, field, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(profile_id, field) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (profile_id, field, value, now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_profile_field(self, profile_id: str, field: str) -> str | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT value FROM profile_metadata WHERE profile_id = ? AND field = ?",
                (profile_id, field),
            ).fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    # ---- global settings ----
    def get_global_setting(self, key: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT value_json FROM global_settings WHERE key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["value_json"])
        finally:
            conn.close()

    def set_global_setting(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        conn = self._conn()
        now = _now()
        try:
            conn.execute(
                """
                INSERT INTO global_settings(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), now),
            )
            conn.commit()
        finally:
            conn.close()
        return value

    def get_extension_settings(self) -> dict[str, Any] | None:
        return self.get_global_setting("extension_settings_v1")

    def set_extension_settings(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.set_global_setting("extension_settings_v1", value)
