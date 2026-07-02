from __future__ import annotations

from collections import deque
import math
from typing import Any

import networkx as nx

from .database_manager import DatabaseManager


STRENGTH_WEIGHTS = {
    "HIGH": 3.0,
    "MEDIUM": 2.0,
    "LOW": 1.0,
}

DEFAULT_LAYOUT_SCALE = 900.0
LAYOUT_SCALE_PER_NODE = 260.0
LAYOUT_SPRING_DISTANCE_FACTOR = 1.8


class GraphManager:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def build_layout_graph(
        self,
        *,
        nodes: list[dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> nx.Graph:
        graph = nx.Graph()
        graph_nodes = nodes if nodes is not None else self.database.list_nodes()
        graph_relations = relations if relations is not None else self.database.list_relations()
        node_ids = {node["node_id"] for node in graph_nodes}

        for node in graph_nodes:
            graph.add_node(node["node_id"], **node)

        for relation in graph_relations:
            source_id = relation["source_id"]
            target_id = relation["target_id"]
            if source_id not in node_ids or target_id not in node_ids:
                continue
            weight = relation_strength_weight(relation["strength"])
            if graph.has_edge(source_id, target_id):
                edge = graph[source_id][target_id]
                edge["weight"] = max(edge["weight"], weight)
                edge["relation_ids"].append(relation["relation_id"])
            else:
                graph.add_edge(
                    source_id,
                    target_id,
                    weight=weight,
                    relation_ids=[relation["relation_id"]],
                )

        return graph

    def compute_layout(
        self,
        *,
        nodes: list[dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
        scale: float | None = None,
        seed: int = 42,
    ) -> dict[int, tuple[float, float]]:
        graph_nodes = nodes if nodes is not None else self.database.list_nodes()
        graph_relations = relations if relations is not None else self.database.list_relations()
        graph = self.build_layout_graph(nodes=graph_nodes, relations=graph_relations)
        if graph.number_of_nodes() == 0:
            return {}

        fixed_positions = {
            node["node_id"]: (float(node["layout_x"]), float(node["layout_y"]))
            for node in graph_nodes
            if node.get("layout_x") is not None and node.get("layout_y") is not None
        }

        if graph.number_of_nodes() == 1:
            node_id = next(iter(graph.nodes))
            return {node_id: fixed_positions.get(node_id, (0.0, 0.0))}

        if len(fixed_positions) == graph.number_of_nodes():
            return fixed_positions

        node_count = graph.number_of_nodes()
        layout = nx.spring_layout(
            graph,
            pos=fixed_positions or None,
            fixed=list(fixed_positions) or None,
            k=layout_spring_distance(node_count),
            weight="weight",
            scale=scale if scale is not None else default_layout_scale(node_count),
            seed=seed,
        )
        return {
            int(node_id): (float(position[0]), float(position[1]))
            for node_id, position in layout.items()
        }

    def get_graph_data(
        self,
        *,
        nodes: list[dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
        seed: int = 42,
    ) -> dict[str, list[dict[str, Any]]]:
        graph_nodes = nodes if nodes is not None else self.database.list_nodes()
        graph_relations = relations if relations is not None else self.database.list_relations()
        layout = self.compute_layout(nodes=graph_nodes, relations=graph_relations, seed=seed)

        rendered_nodes = []
        for node in graph_nodes:
            x, y = layout.get(node["node_id"], (0.0, 0.0))
            rendered = dict(node)
            rendered["x"] = x
            rendered["y"] = y
            rendered_nodes.append(rendered)

        return {
            "nodes": rendered_nodes,
            "relations": graph_relations,
        }

    def get_focus_node_ids(self, center_node_id: int, *, depth: int = 2) -> set[int]:
        if depth < 0:
            raise ValueError("depth must be greater than or equal to 0.")

        graph = self.build_layout_graph()
        if center_node_id not in graph:
            return set()

        visited = {center_node_id}
        queue: deque[tuple[int, int]] = deque([(center_node_id, 0)])

        while queue:
            node_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for neighbor_id in graph.neighbors(node_id):
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                queue.append((neighbor_id, current_depth + 1))

        return visited

    def get_focus_graph_data(self, center_node_id: int, *, depth: int = 2) -> dict[str, list[dict[str, Any]]]:
        focus_ids = self.get_focus_node_ids(center_node_id, depth=depth)
        nodes = [
            node
            for node in self.database.list_nodes()
            if node["node_id"] in focus_ids
        ]
        relations = [
            relation
            for relation in self.database.list_relations()
            if relation["source_id"] in focus_ids and relation["target_id"] in focus_ids
        ]
        return self.get_graph_data(nodes=nodes, relations=relations)


def relation_strength_weight(strength: str) -> float:
    return STRENGTH_WEIGHTS.get(strength.upper(), STRENGTH_WEIGHTS["MEDIUM"])


def default_layout_scale(node_count: int) -> float:
    return max(DEFAULT_LAYOUT_SCALE, LAYOUT_SCALE_PER_NODE * math.sqrt(max(1, node_count)))


def layout_spring_distance(node_count: int) -> float:
    return LAYOUT_SPRING_DISTANCE_FACTOR / math.sqrt(max(1, node_count))
