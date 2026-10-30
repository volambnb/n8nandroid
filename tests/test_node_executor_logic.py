import unittest

from automation.models import Node
from automation.node_executor import NodeExecutionContext, NodeExecutor


class NodeExecutorLogicTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.executor = NodeExecutor()

        async def _noop_log(level, message, node_id, data):
            return None

        self.ctx = NodeExecutionContext(
            run_id="r1",
            run_item_id="r1:p1",
            profile_id="p1",
            playwright=None,  # type: ignore[arg-type]
            browser=None,  # type: ignore[arg-type]
            browser_context=None,  # type: ignore[arg-type]
            active_page=None,  # type: ignore[arg-type]
            profile_debug_url="",
            variables={"a": 2, "b": 3, "text": "hello 123 world 456"},
            log=_noop_log,
        )

    async def test_if_node_true_branch(self) -> None:
        node = Node(id="n1", type="If", config={"expression": "a + b == 5"})
        result = await self.executor.run_node(self.ctx, node)
        self.assertEqual(result.next_label, "true")
        self.assertTrue(result.outputs["if_result"])

    async def test_regexp_extraction(self) -> None:
        node = Node(
            id="n2",
            type="RegExp (Data extraction)",
            config={
                "input_value": "{text}",
                "expression": r"\d+",
                "global": True,
                "output_variable": "nums",
            },
        )
        result = await self.executor.run_node(self.ctx, node)
        self.assertEqual(result.outputs["nums"], ["123", "456"])

    async def test_loop_count(self) -> None:
        node = Node(
            id="loop1",
            type="Loop",
            config={"mode": "count", "count": 2, "output_variable": "i"},
        )
        first = await self.executor.run_node(self.ctx, node)
        second = await self.executor.run_node(self.ctx, node)
        third = await self.executor.run_node(self.ctx, node)
        self.assertEqual(first.next_label, "loop")
        self.assertEqual(second.next_label, "loop")
        self.assertEqual(third.next_label, "next")

    async def test_case_path(self) -> None:
        self.ctx.variables["status"] = "ok"
        node = Node(
            id="n3",
            type="Case Path",
            config={"value": "{status}", "cases": {"success": "ok"}, "default_label": "fallback"},
        )
        result = await self.executor.run_node(self.ctx, node)
        self.assertEqual(result.next_label, "success")


if __name__ == "__main__":
    unittest.main()
