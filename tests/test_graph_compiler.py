import unittest

from automation.compiler import GraphCompiler
from automation.models import AppGraph


class GraphCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.compiler = GraphCompiler()

    def test_compile_with_start_node(self) -> None:
        graph = AppGraph.model_validate(
            {
                "nodes": [
                    {"id": "n1", "type": "Start"},
                    {"id": "n2", "type": "Log"},
                ],
                "edges": [{"from": "n1", "to": "n2", "label": "next"}],
            }
        )
        compiled = self.compiler.compile(graph)
        self.assertEqual(compiled.start_node_id, "n1")
        self.assertEqual(compiled.next_node("n1"), "n2")

    def test_compile_fails_on_duplicate_edge_label(self) -> None:
        graph = AppGraph.model_validate(
            {
                "nodes": [{"id": "a", "type": "Start"}, {"id": "b", "type": "Stop"}],
                "edges": [
                    {"from": "a", "to": "b", "label": "next"},
                    {"from": "a", "to": "b", "label": "next"},
                ],
            }
        )
        with self.assertRaises(ValueError):
            self.compiler.compile(graph)

    def test_compile_fails_on_unknown_node(self) -> None:
        graph = AppGraph.model_validate(
            {
                "nodes": [{"id": "a", "type": "Start"}],
                "edges": [{"from": "a", "to": "missing", "label": "next"}],
            }
        )
        with self.assertRaises(ValueError):
            self.compiler.compile(graph)


if __name__ == "__main__":
    unittest.main()
