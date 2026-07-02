import pytest

from core.database_manager import (
    DatabaseManager,
    DuplicateNodeError,
    DuplicateRelationError,
)


@pytest.fixture
def database():
    db = DatabaseManager(":memory:")
    db.init_db()
    yield db
    db.close()


def test_init_db_seeds_default_relation_types(database):
    relation_types = database.list_relation_types()

    assert [relation_type["code"] for relation_type in relation_types] == [
        "RELATED",
        "REFERENCE",
        "GENERATED_FROM",
        "CONTAINS",
        "VERSION_OF",
    ]
    assert relation_types[0]["name"] == "관련 있음"


def test_add_node_rejects_duplicate_path(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    with pytest.raises(DuplicateNodeError) as exc_info:
        database.add_node("C:/workspace/brief.md", node_type="FILE")

    assert exc_info.value.existing_node["node_id"] == node_id


def test_search_nodes_matches_name_path_category_and_context(database):
    database.add_node(
        "C:/workspace/brief.md",
        node_type="FILE",
        ai_category="마케팅",
        ai_context="launch campaign plan",
    )
    database.add_node("C:/workspace/budget.xlsx", node_type="FILE")

    assert [node["name"] for node in database.search_nodes("brief")] == ["brief.md"]
    assert [node["name"] for node in database.search_nodes("마케팅")] == ["brief.md"]
    assert [node["name"] for node in database.search_nodes("campaign")] == ["brief.md"]
    assert [node["name"] for node in database.search_nodes("budget")] == ["budget.xlsx"]


def test_update_node_layout_persists_coordinates(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    database.update_node_layout(node_id, 12.5, -8.25)

    node = database.get_node(node_id)
    assert node["layout_x"] == 12.5
    assert node["layout_y"] == -8.25


def test_update_node_status_soft_deletes_node(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    database.update_node_status(node_id, "DELETED")

    assert database.get_node(node_id)["status"] == "DELETED"
    assert database.get_node(node_id)["deleted_at"] is not None
    assert database.list_nodes() == []
    assert database.list_nodes(include_deleted=True)[0]["node_id"] == node_id


def test_add_node_restores_deleted_node_for_same_path(database):
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/deck.pptx", node_type="FILE")
    relation_id = database.add_relation(source_id, target_id)
    database.update_node_status(source_id, "DELETED")

    restored_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    restored = database.get_node(restored_id)
    assert restored_id == source_id
    assert restored["status"] == "ACTIVE"
    assert restored["deleted_at"] is None
    assert database.list_nodes()[0]["node_id"] == source_id
    assert database.list_relations()[0]["relation_id"] == relation_id


def test_add_relation_rejects_duplicate_undirected_reverse_pair(database):
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/deck.pptx", node_type="FILE")
    relation_id = database.add_relation(
        source_id,
        target_id,
        relation_type_code="RELATED",
        is_directional=False,
    )

    with pytest.raises(DuplicateRelationError) as exc_info:
        database.add_relation(
            target_id,
            source_id,
            relation_type_code="RELATED",
            is_directional=False,
        )

    assert exc_info.value.existing_relation["relation_id"] == relation_id


def test_list_relations_hides_relations_for_deleted_nodes_by_default(database):
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/deck.pptx", node_type="FILE")
    relation_id = database.add_relation(source_id, target_id)

    database.update_node_status(source_id, "DELETED")

    assert database.list_relations() == []
    assert database.list_relations(include_deleted=True)[0]["relation_id"] == relation_id


def test_directional_relation_allows_reverse_direction(database):
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/deck.pptx", node_type="FILE")

    first_id = database.add_relation(
        source_id,
        target_id,
        relation_type_code="REFERENCE",
        is_directional=True,
    )
    second_id = database.add_relation(
        target_id,
        source_id,
        relation_type_code="REFERENCE",
        is_directional=True,
    )

    assert first_id != second_id
    assert len(database.list_relations()) == 2


def test_update_and_delete_relation(database):
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/deck.pptx", node_type="FILE")
    relation_id = database.add_relation(source_id, target_id)

    database.update_relation(relation_id, strength="HIGH", description="uses the brief")

    relation = database.get_relation(relation_id)
    assert relation["strength"] == "HIGH"
    assert relation["description"] == "uses the brief"

    database.delete_relation(relation_id)

    assert database.get_relation(relation_id) is None


def test_custom_relation_type_can_be_used(database):
    relation_type_id = database.add_relation_type("검토 필요", default_is_directional=True)
    source_id = database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/review.md", node_type="FILE")

    relation_id = database.add_relation(source_id, target_id, relation_type_id=relation_type_id)

    relation = database.get_relation(relation_id)
    assert relation["relation_type_name"] == "검토 필요"
    assert relation["is_directional"] == 1
