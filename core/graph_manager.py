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

DEFAULT_LAYOUT_SCALE = 720.0
LAYOUT_SCALE_PER_NODE = 180.0
LAYOUT_SPRING_DISTANCE_FACTOR = 1.05
NODE_RADIUS_BY_TYPE = {
    "FILE": 28.0,
    "FOLDER": 34.0,
}
MIN_LAYOUT_NODE_GAP = 40.0
LAYOUT_OVERLAP_ITERATIONS = 80
EDGE_NODE_CLEARANCE = 22.0
EDGE_NODE_OVERLAP_ITERATIONS = 10
MULTI_START_LAYOUT_NODE_LIMIT = 220
MULTI_START_LAYOUT_COUNT = 3
MULTI_START_LAYOUT_MIN_NODES = 30


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
        use_saved_layout: bool = True,
    ) -> dict[int, tuple[float, float]]:
        graph_nodes = nodes if nodes is not None else self.database.list_nodes()
        graph_relations = relations if relations is not None else self.database.list_relations()
        graph = self.build_layout_graph(nodes=graph_nodes, relations=graph_relations)
        if graph.number_of_nodes() == 0:
            return {}

        fixed_positions = {}
        if use_saved_layout:
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
        use_multi_start = (
            MULTI_START_LAYOUT_MIN_NODES <= node_count <= MULTI_START_LAYOUT_NODE_LIMIT
            and len(graph_relations) >= node_count // 2
        )
        candidate_count = MULTI_START_LAYOUT_COUNT if use_multi_start else 1
        layout_candidates = []
        for seed_offset in range(candidate_count):
            layout = nx.spring_layout(
                graph,
                pos=fixed_positions or None,
                fixed=list(fixed_positions) or None,
                k=layout_spring_distance(node_count),
                weight="weight",
                scale=scale if scale is not None else default_layout_scale(node_count),
                seed=seed + seed_offset * 97,
            )
            candidate = {
                int(node_id): (float(position[0]), float(position[1]))
                for node_id, position in layout.items()
            }
            candidate = resolve_layout_overlaps(
                candidate,
                graph_nodes,
                fixed_node_ids=set(fixed_positions),
            )
            layout_candidates.append(candidate)
        layout_by_id = min(
            layout_candidates,
            key=lambda candidate: layout_quality_score(candidate, graph_nodes, graph_relations),
        )
        use_edge_node_avoidance = len(graph_nodes) <= 80 and len(graph_relations) <= 120
        if use_edge_node_avoidance:
            layout_by_id = resolve_layout_edge_node_overlaps(
                layout_by_id,
                graph_nodes,
                graph_relations,
                fixed_node_ids=set(fixed_positions),
            )
        layout_by_id = resolve_layout_overlaps(
            layout_by_id,
            graph_nodes,
            fixed_node_ids=set(fixed_positions),
            iterations=24,
        )
        if use_edge_node_avoidance:
            layout_by_id = resolve_layout_edge_node_overlaps(
                layout_by_id,
                graph_nodes,
                graph_relations,
                fixed_node_ids=set(fixed_positions),
                iterations=4,
            )
        return resolve_layout_overlaps(
            layout_by_id,
            graph_nodes,
            fixed_node_ids=set(fixed_positions),
            iterations=12,
        )

    def get_graph_data(
        self,
        *,
        nodes: list[dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
        seed: int = 42,
        scale: float | None = None,
        use_saved_layout: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        graph_nodes = nodes if nodes is not None else self.database.list_nodes()
        graph_relations = relations if relations is not None else self.database.list_relations()
        layout = self.compute_layout(
            nodes=graph_nodes,
            relations=graph_relations,
            seed=seed,
            scale=scale,
            use_saved_layout=use_saved_layout,
        )
        root_folder_ids = root_folder_node_ids(graph_nodes, graph_relations)

        rendered_nodes = []
        for node in graph_nodes:
            x, y = layout.get(node["node_id"], (0.0, 0.0))
            rendered = dict(node)
            rendered["x"] = x
            rendered["y"] = y
            rendered["is_root_folder"] = int(node["node_id"]) in root_folder_ids
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

    def get_downstream_impact_node_ids(self, center_node_id: int) -> set[int]:
        relations = self.database.list_relations()
        adjacency: dict[int, set[int]] = {}
        for relation in relations:
            source_id = int(relation["source_id"])
            target_id = int(relation["target_id"])
            code = str(relation.get("relation_type_code") or "")
            if code in {"READS", "GENERATED_FROM"}:
                source_id, target_id = target_id, source_id
            elif code not in {"WRITES", "EXPORTED_AS", "USED_BY"}:
                continue
            adjacency.setdefault(source_id, set()).add(target_id)

        visited = {int(center_node_id)}
        queue = deque([int(center_node_id)])
        while queue:
            node_id = queue.popleft()
            for target_id in adjacency.get(node_id, set()):
                if target_id in visited:
                    continue
                visited.add(target_id)
                queue.append(target_id)
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
        return self.get_graph_data(nodes=nodes, relations=relations, scale=focus_layout_scale(len(nodes)))


def relation_strength_weight(strength: str) -> float:
    return STRENGTH_WEIGHTS.get(strength.upper(), STRENGTH_WEIGHTS["MEDIUM"])


def default_layout_scale(node_count: int) -> float:
    return max(DEFAULT_LAYOUT_SCALE, LAYOUT_SCALE_PER_NODE * math.sqrt(max(1, node_count)))


def focus_layout_scale(node_count: int) -> float:
    return max(360.0, 120.0 * math.sqrt(max(1, node_count)))


def layout_spring_distance(node_count: int) -> float:
    return LAYOUT_SPRING_DISTANCE_FACTOR / math.sqrt(max(1, node_count))


def root_folder_node_ids(
    nodes: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> set[int]:
    folder_ids = {
        int(node["node_id"])
        for node in nodes
        if str(node.get("node_type") or "").upper() == "FOLDER"
    }
    contained_folder_ids = {
        int(relation["target_id"])
        for relation in relations
        if relation.get("relation_type_code") == "CONTAINS"
        and int(relation.get("source_id")) in folder_ids
        and int(relation.get("target_id")) in folder_ids
    }
    return folder_ids - contained_folder_ids


def layout_node_radius(node: dict[str, Any]) -> float:
    return NODE_RADIUS_BY_TYPE.get(str(node.get("node_type") or "").upper(), NODE_RADIUS_BY_TYPE["FILE"])


def resolve_layout_overlaps(
    layout: dict[int, tuple[float, float]],
    nodes: list[dict[str, Any]],
    *,
    fixed_node_ids: set[int] | None = None,
    min_gap: float = MIN_LAYOUT_NODE_GAP,
    iterations: int = LAYOUT_OVERLAP_ITERATIONS,
) -> dict[int, tuple[float, float]]:
    if len(layout) < 2:
        return dict(layout)

    fixed_ids = fixed_node_ids or set()
    radii = {int(node["node_id"]): layout_node_radius(node) for node in nodes}
    positions = {int(node_id): [float(x), float(y)] for node_id, (x, y) in layout.items()}
    node_ids = list(positions)

    for _iteration in range(iterations):
        moved = False
        for index, first_id in enumerate(node_ids):
            for second_id in node_ids[index + 1 :]:
                first_position = positions[first_id]
                second_position = positions[second_id]
                dx = second_position[0] - first_position[0]
                dy = second_position[1] - first_position[1]
                distance = math.hypot(dx, dy)
                min_distance = radii.get(first_id, NODE_RADIUS_BY_TYPE["FILE"]) + radii.get(
                    second_id,
                    NODE_RADIUS_BY_TYPE["FILE"],
                ) + min_gap
                overlap = min_distance - distance
                if overlap <= 0:
                    continue

                if distance < 1e-6:
                    ux, uy = deterministic_unit_vector(first_id, second_id)
                else:
                    ux, uy = dx / distance, dy / distance

                first_fixed = first_id in fixed_ids
                second_fixed = second_id in fixed_ids
                if first_fixed and second_fixed:
                    continue
                if first_fixed:
                    second_position[0] += ux * overlap
                    second_position[1] += uy * overlap
                elif second_fixed:
                    first_position[0] -= ux * overlap
                    first_position[1] -= uy * overlap
                else:
                    push = overlap / 2.0
                    first_position[0] -= ux * push
                    first_position[1] -= uy * push
                    second_position[0] += ux * push
                    second_position[1] += uy * push
                moved = True
        if not moved:
            break

    return {node_id: (position[0], position[1]) for node_id, position in positions.items()}


def deterministic_unit_vector(first_id: int, second_id: int) -> tuple[float, float]:
    angle = ((first_id * 31 + second_id * 17) % 360) * math.pi / 180.0
    return math.cos(angle), math.sin(angle)


def resolve_layout_edge_node_overlaps(
    layout: dict[int, tuple[float, float]],
    nodes: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    *,
    fixed_node_ids: set[int] | None = None,
    clearance: float = EDGE_NODE_CLEARANCE,
    iterations: int = EDGE_NODE_OVERLAP_ITERATIONS,
) -> dict[int, tuple[float, float]]:
    fixed_ids = fixed_node_ids or set()
    positions = {int(node_id): [float(x), float(y)] for node_id, (x, y) in layout.items()}
    radii = {int(node["node_id"]): layout_node_radius(node) for node in nodes}
    edges = [
        (int(relation["source_id"]), int(relation["target_id"]))
        for relation in relations
        if int(relation["source_id"]) in positions and int(relation["target_id"]) in positions
    ]
    for _iteration in range(iterations):
        moved = False
        for source_id, target_id in edges:
            source = positions[source_id]
            target = positions[target_id]
            for node_id, position in positions.items():
                if node_id in {source_id, target_id} or node_id in fixed_ids:
                    continue
                closest_x, closest_y = closest_point_on_segment(position, source, target)
                dx = position[0] - closest_x
                dy = position[1] - closest_y
                distance = math.hypot(dx, dy)
                required = radii.get(node_id, NODE_RADIUS_BY_TYPE["FILE"]) + clearance
                if distance >= required:
                    continue
                if distance < 1e-6:
                    ux, uy = deterministic_unit_vector(node_id, source_id + target_id)
                else:
                    ux, uy = dx / distance, dy / distance
                push = required - distance
                position[0] += ux * push
                position[1] += uy * push
                moved = True
        if not moved:
            break
    return {node_id: (position[0], position[1]) for node_id, position in positions.items()}


def closest_point_on_segment(
    point: list[float],
    start: list[float],
    end: list[float],
) -> tuple[float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared < 1e-12:
        return start[0], start[1]
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    ratio = max(0.0, min(1.0, ratio))
    return start[0] + ratio * dx, start[1] + ratio * dy


def layout_quality_score(
    layout: dict[int, tuple[float, float]],
    nodes: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> float:
    positions = {node_id: [position[0], position[1]] for node_id, position in layout.items()}
    unique_edges = sorted(
        {
            tuple(sorted((int(relation["source_id"]), int(relation["target_id"]))))
            for relation in relations
            if int(relation["source_id"]) in positions and int(relation["target_id"]) in positions
        }
    )
    crossings = 0
    for index, (first_source, first_target) in enumerate(unique_edges):
        for second_source, second_target in unique_edges[index + 1 :]:
            if {first_source, first_target} & {second_source, second_target}:
                continue
            if segments_cross(
                positions[first_source],
                positions[first_target],
                positions[second_source],
                positions[second_target],
            ):
                crossings += 1

    radii = {int(node["node_id"]): layout_node_radius(node) for node in nodes}
    edge_node_penalty = 0.0
    for source_id, target_id in unique_edges:
        for node_id, position in positions.items():
            if node_id in {source_id, target_id}:
                continue
            closest_x, closest_y = closest_point_on_segment(
                position, positions[source_id], positions[target_id]
            )
            distance = math.hypot(position[0] - closest_x, position[1] - closest_y)
            required = radii.get(node_id, NODE_RADIUS_BY_TYPE["FILE"]) + EDGE_NODE_CLEARANCE
            if distance < required:
                edge_node_penalty += required - distance
    return crossings * 10000.0 + edge_node_penalty


def segments_cross(
    first_start: list[float],
    first_end: list[float],
    second_start: list[float],
    second_end: list[float],
) -> bool:
    def orientation(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    first_a = orientation(first_start, first_end, second_start)
    first_b = orientation(first_start, first_end, second_end)
    second_a = orientation(second_start, second_end, first_start)
    second_b = orientation(second_start, second_end, first_end)
    return first_a * first_b < 0 and second_a * second_b < 0
