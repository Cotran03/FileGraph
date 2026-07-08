import math

import pytest

from core.database_manager import DatabaseManager
from core.graph_manager import (
    DEFAULT_LAYOUT_SCALE,
    MIN_LAYOUT_NODE_GAP,
    GraphManager,
    default_layout_scale,
    layout_spring_distance,
    resolve_layout_overlaps,
    relation_strength_weight,
)


@pytest.fixture
def database():
    db = DatabaseManager(":memory:")
    db.init_db()
    yield db
    db.close()


def test_relation_strength_weight_defaults_to_medium_for_unknown_value():
    assert relation_strength_weight("HIGH") == 3.0
    assert relation_strength_weight("MEDIUM") == 2.0
    assert relation_strength_weight("LOW") == 1.0
    assert relation_strength_weight("unexpected") == 2.0


def test_get_graph_data_includes_nodes_relations_and_layout(database):
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/assets", node_type="FOLDER")
    relation_id = database.add_relation(
        source_id,
        target_id,
        relation_type_code="CONTAINS",
        is_directional=True,
        strength="HIGH",
    )

    data = GraphManager(database).get_graph_data()

    assert {node["node_id"] for node in data["nodes"]} == {source_id, target_id}
    assert data["relations"][0]["relation_id"] == relation_id
    assert all("x" in node and "y" in node for node in data["nodes"])


def test_compute_layout_uses_default_scale_bounds(database):
    first_id = database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = database.add_node("C:/workspace/third.md", node_type="FILE")
    database.add_relation(first_id, second_id)
    database.add_relation(second_id, third_id)

    layout = GraphManager(database).compute_layout()

    assert max(max(abs(x), abs(y)) for x, y in layout.values()) <= default_layout_scale(len(layout)) + 1e-6


def test_compute_layout_keeps_connected_pair_well_spaced(database):
    source_id = database.add_node("C:/workspace/source.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/target.md", node_type="FILE")
    database.add_relation(source_id, target_id)

    layout = GraphManager(database).compute_layout()
    source = layout[source_id]
    target = layout[target_id]

    assert math.dist(source, target) >= DEFAULT_LAYOUT_SCALE


def test_compute_layout_seed_changes_unfixed_layout(database):
    first_id = database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = database.add_node("C:/workspace/third.md", node_type="FILE")
    database.add_relation(first_id, second_id)
    database.add_relation(second_id, third_id)

    first_layout = GraphManager(database).compute_layout(seed=1)
    second_layout = GraphManager(database).compute_layout(seed=2)

    assert any(
        math.dist(first_layout[node_id], second_layout[node_id]) > 1e-6
        for node_id in first_layout
    )


def test_layout_defaults_expand_with_node_count():
    assert default_layout_scale(2) == DEFAULT_LAYOUT_SCALE
    assert default_layout_scale(25) > DEFAULT_LAYOUT_SCALE
    assert layout_spring_distance(4) > layout_spring_distance(16)


def test_compute_layout_keeps_saved_single_node_position(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    database.update_node_layout(node_id, 42.0, -12.0)

    layout = GraphManager(database).compute_layout()

    assert layout[node_id] == (42.0, -12.0)


def test_resolve_layout_overlaps_pushes_nodes_apart():
    nodes = [
        {"node_id": 1, "node_type": "FILE"},
        {"node_id": 2, "node_type": "FILE"},
    ]
    layout = {1: (0.0, 0.0), 2: (5.0, 0.0)}

    resolved = resolve_layout_overlaps(layout, nodes)

    assert math.dist(resolved[1], resolved[2]) >= 56.0 + MIN_LAYOUT_NODE_GAP - 1e-6


def test_focus_node_ids_returns_nodes_within_depth(database):
    first_id = database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = database.add_node("C:/workspace/third.md", node_type="FILE")
    database.add_relation(first_id, second_id)
    database.add_relation(second_id, third_id)

    graph_manager = GraphManager(database)

    assert graph_manager.get_focus_node_ids(first_id, depth=0) == {first_id}
    assert graph_manager.get_focus_node_ids(first_id, depth=1) == {first_id, second_id}
    assert graph_manager.get_focus_node_ids(first_id, depth=2) == {
        first_id,
        second_id,
        third_id,
    }


def test_focus_graph_data_filters_out_unrelated_nodes(database):
    center_id = database.add_node("C:/workspace/center.md", node_type="FILE")
    neighbor_id = database.add_node("C:/workspace/neighbor.md", node_type="FILE")
    unrelated_id = database.add_node("C:/workspace/unrelated.md", node_type="FILE")
    database.add_relation(center_id, neighbor_id)

    data = GraphManager(database).get_focus_graph_data(center_id, depth=1)

    assert {node["node_id"] for node in data["nodes"]} == {center_id, neighbor_id}
    assert unrelated_id not in {node["node_id"] for node in data["nodes"]}
    assert len(data["relations"]) == 1
