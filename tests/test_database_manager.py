import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

import core.database_manager as database_manager_module
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
        "SAME_FILE",
        "READS",
        "WRITES",
    ]
    assert relation_types[0]["name"] == "관련 있음"


def test_add_node_creates_same_file_relation_for_different_paths(database, monkeypatch):
    monkeypatch.setattr(
        database_manager_module,
        "get_file_identity",
        lambda _path: {"file_id": "shared-file-id", "volume_serial": "E:"},
    )

    first_id = database.add_node("E:/tools/git.exe", node_type="FILE")
    second_id = database.add_node("E:/tools/git-lfs.exe", node_type="FILE")

    assert first_id != second_id
    relations = database.list_relations()
    assert len(relations) == 1
    assert relations[0]["relation_type_code"] == "SAME_FILE"
    assert relations[0]["relation_type_name"] == "같은 파일"
    assert relations[0]["is_directional"] == 0
    assert relations[0]["strength"] == "HIGH"


def test_same_file_relation_is_hidden_while_matching_node_is_deleted(database, monkeypatch):
    monkeypatch.setattr(
        database_manager_module,
        "get_file_identity",
        lambda _path: {"file_id": "shared-file-id", "volume_serial": "E:"},
    )

    first_id = database.add_node("E:/tools/git-lfs.exe", node_type="FILE")
    database.update_node_status(first_id, "DELETED")
    database.add_node("E:/tools/git.exe", node_type="FILE")

    assert database.list_relations() == []
    assert database.list_relations(include_deleted=True)[0]["relation_type_code"] == "SAME_FILE"


def test_init_db_migrates_legacy_file_identity_unique_constraint(monkeypatch):
    db_path = Path("tests") / f"legacy-{uuid4().hex}.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE nodes (
            node_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            volume_serial TEXT NOT NULL,
            node_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            file_hash TEXT,
            layout_x REAL,
            layout_y REAL,
            note TEXT,
            highlight_color TEXT,
            last_seen TEXT,
            deleted_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (path),
            UNIQUE (file_id, volume_serial)
        );
        INSERT INTO nodes (
            file_id, volume_serial, node_type, status, name, path
        ) VALUES (
            'shared-file-id', 'E:', 'FILE', 'ACTIVE', 'git.exe', 'E:\\tools\\git.exe'
        );
        """
    )
    connection.close()

    migrated = DatabaseManager(db_path)
    try:
        migrated.init_db()
        monkeypatch.setattr(
            database_manager_module,
            "get_file_identity",
            lambda _path: {"file_id": "shared-file-id", "volume_serial": "E:"},
        )
        migrated.add_node("E:/tools/git-lfs.exe", node_type="FILE")

        assert len(migrated.list_nodes()) == 2
        assert migrated.list_relations()[0]["relation_type_code"] == "SAME_FILE"
        assert migrated.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        migrated.close()
        db_path.unlink(missing_ok=True)


def test_add_node_rejects_duplicate_path(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    with pytest.raises(DuplicateNodeError) as exc_info:
        database.add_node("C:/workspace/brief.md", node_type="FILE")

    assert exc_info.value.existing_node["node_id"] == node_id


def test_search_nodes_matches_name_and_path(database):
    database.add_node("C:/workspace/brief.md", node_type="FILE")
    database.add_node("C:/workspace/budget.xlsx", node_type="FILE")

    assert [node["name"] for node in database.search_nodes("brief")] == ["brief.md"]
    assert [node["name"] for node in database.search_nodes("workspace")] == ["brief.md", "budget.xlsx"]
    assert [node["name"] for node in database.search_nodes("budget")] == ["budget.xlsx"]


def test_update_node_layout_persists_coordinates(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    database.update_node_layout(node_id, 12.5, -8.25)

    node = database.get_node(node_id)
    assert node["layout_x"] == 12.5
    assert node["layout_y"] == -8.25


def test_update_node_note_and_highlight_persist(database):
    node_id = database.add_node("C:/workspace/brief.md", node_type="FILE")

    database.update_node_note(node_id, "review this")
    database.update_node_highlight_color(node_id, "#F97316")

    node = database.get_node(node_id)
    assert node["note"] == "review this"
    assert node["highlight_color"] == "#F97316"


def test_list_orphan_nodes_excludes_connected_nodes(database):
    orphan_id = database.add_node("C:/workspace/orphan.md", node_type="FILE")
    source_id = database.add_node("C:/workspace/source.md", node_type="FILE")
    target_id = database.add_node("C:/workspace/target.md", node_type="FILE")
    database.add_relation(source_id, target_id)

    assert [node["node_id"] for node in database.list_orphan_nodes()] == [orphan_id]


def test_duplicate_candidate_groups_include_hash_and_name_matches(database):
    first_id = database.add_node("C:/workspace/a/report.md", node_type="FILE", file_hash="same")
    second_id = database.add_node("C:/workspace/b/report.md", node_type="FILE", file_hash="same")

    groups = database.list_duplicate_candidate_groups()

    assert any(group["kind"] == "hash" and {node["node_id"] for node in group["nodes"]} == {first_id, second_id} for group in groups)
    assert any(group["kind"] == "name" and {node["node_id"] for node in group["nodes"]} == {first_id, second_id} for group in groups)


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
