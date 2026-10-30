import tempfile
import unittest

from automation.store import AutomationStore


class StoreRunTests(unittest.TestCase):
    def test_run_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AutomationStore(f"{tmp}/auto.db")
            app = store.create_app(
                "A1",
                "",
                {"nodes": [{"id": "s", "type": "Start"}], "edges": [], "inputs": []},
            )
            run = store.create_run(
                app_id=app["id"],
                task_id=None,
                request={"app_id": app["id"]},
                summary={"total": 1, "pending": 1, "running": 0, "done": 0, "failed": 0, "cancelled": 0},
            )
            store.upsert_run_item(
                run_id=run["id"],
                run_item_id=f"{run['id']}:p1",
                profile_id="p1",
                status="running",
            )
            store.append_log(
                run_id=run["id"],
                run_item_id=f"{run['id']}:p1",
                level="info",
                message="test",
            )
            logs = store.get_logs(run["id"])
            items = store.list_run_items(run["id"])
            self.assertEqual(len(items), 1)
            self.assertEqual(len(logs), 1)

    def test_idempotency_reuses_same_run_and_rejects_different_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AutomationStore(f"{tmp}/auto.db")
            summary = {"total": 1, "pending": 1, "running": 0, "done": 0, "failed": 0, "cancelled": 0}
            first = store.create_run(
                app_id="app-1",
                task_id=None,
                request={"app_id": "app-1", "profile_selector": {"profile_ids": ["177"]}},
                summary=summary,
                idempotency_key="exec:node:0",
            )
            repeated = store.create_run(
                app_id="app-1",
                task_id=None,
                request={"profile_selector": {"profile_ids": ["177"]}, "app_id": "app-1"},
                summary=summary,
                idempotency_key="exec:node:0",
            )
            self.assertEqual(first["id"], repeated["id"])
            self.assertTrue(repeated["idempotency_reused"])

            with self.assertRaisesRegex(ValueError, "Idempotency-Key"):
                store.create_run(
                    app_id="app-1",
                    task_id=None,
                    request={"app_id": "app-1", "profile_selector": {"profile_ids": ["172"]}},
                    summary=summary,
                    idempotency_key="exec:node:0",
                )


if __name__ == "__main__":
    unittest.main()
