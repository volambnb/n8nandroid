from __future__ import annotations

from dataclasses import dataclass, field

from automation.models import AppGraph, Node


@dataclass
class CompiledGraph:
    nodes: dict[str, Node]
    edges: dict[str, dict[str, str]]
    start_node_id: str
    secret_inputs: set[str] = field(default_factory=set)
    input_defaults: dict[str, object] = field(default_factory=dict)

    def next_node(self, node_id: str, label: str = "next") -> str | None:
        edge_map = self.edges.get(node_id, {})
        if not edge_map:
            return None
        key = str(label or "next").lower()
        direct = edge_map.get(key)
        if direct:
            return direct
        if key == "next":
            return edge_map.get("true") or edge_map.get("success") or edge_map.get("next")
        if key == "error":
            return edge_map.get("false") or edge_map.get("fallback")
        if key == "true":
            return edge_map.get("next") or edge_map.get("success")
        if key == "false":
            return edge_map.get("error") or edge_map.get("fallback")
        return edge_map.get("next") or edge_map.get("true") or edge_map.get("success")


class GraphCompiler:
    """Validates and compiles graph wiring into a lookup-friendly structure."""

    def compile(self, graph: AppGraph) -> CompiledGraph:
        if not graph.nodes:
            raise ValueError("Graph has no nodes")

        nodes = {n.id: n for n in graph.nodes}
        edges: dict[str, dict[str, str]] = {}
        for edge in graph.edges:
            if edge.from_node not in nodes:
                raise ValueError(f"Edge.from not found: {edge.from_node}")
            if edge.to not in nodes:
                raise ValueError(f"Edge.to not found: {edge.to}")
            edges.setdefault(edge.from_node, {})
            if edge.label in edges[edge.from_node]:
                raise ValueError(
                    f"Duplicated edge label '{edge.label}' from node {edge.from_node}"
                )
            edges[edge.from_node][edge.label] = edge.to

        # Prefer explicit Start node, fallback to first node.
        start_candidates = [
            n.id for n in graph.nodes if n.type.strip().lower() in {"start", "start-stop"}
        ]
        start_node_id = start_candidates[0] if start_candidates else graph.nodes[0].id
        # Variables placed by the editor beside Start are deliberately left
        # unlinked on the canvas. Compile an execution-only path through those
        # isolated nodes before the first regular action.
        incoming = {edge.to for edge in graph.edges}
        isolated_variables = [
            node.id for node in graph.nodes
            if node.id != start_node_id
            and node.type.strip().lower() in {"variables", "variable"}
            and node.id not in incoming
            and not edges.get(node.id)
        ]
        if isolated_variables:
            start_edges = edges.setdefault(start_node_id, {})
            original_next = (
                start_edges.get("next") or start_edges.get("true")
                or start_edges.get("success")
            )
            start_edges["next"] = isolated_variables[0]
            for first, second in zip(isolated_variables, isolated_variables[1:]):
                edges[first] = {"next": second}
            if original_next:
                edges[isolated_variables[-1]] = {"next": original_next}
        return CompiledGraph(
            nodes=nodes,
            edges=edges,
            start_node_id=start_node_id,
            secret_inputs={item.name for item in graph.inputs if item.secret},
            input_defaults={item.name: item.default for item in graph.inputs if item.default is not None},
        )
