from pathlib import Path
import shutil
import uuid

import pytest

from core.database_manager import DatabaseManager
from core.file_integrity import (
    ACCESS_DENIED,
    ACTIVE,
    MISSING,
    compute_file_hash,
    iter_search_files,
    probe_path_status,
    rediscover_missing_nodes,
    scan_file_statuses,
)


@pytest.fixture
def database():
    db = DatabaseManager(":memory:")
    db.init_db()
    yield db
    db.close()


def test_probe_path_status_detects_active_and_missing_paths():
    file_path = Path("README.md").resolve(strict=True)

    assert probe_path_status(file_path) == ACTIVE
    assert probe_path_status(unique_missing_path()) == MISSING


def test_scan_file_statuses_marks_missing_and_restores_active_paths(database):
    file_path = unique_missing_path()
    node_id = database.add_node(file_path, node_type="FILE")

    missing_result = scan_file_statuses(database, status_probe=lambda _node: MISSING)

    missing_node = database.get_node(node_id)
    assert missing_result.total == 1
    assert missing_result.missing == 1
    assert missing_result.changed[0].old_status == ACTIVE
    assert missing_result.changed[0].new_status == MISSING
    assert missing_node["status"] == MISSING
    assert missing_node["deleted_at"] is not None

    restored_result = scan_file_statuses(database, status_probe=lambda _node: ACTIVE)

    restored_node = database.get_node(node_id)
    assert restored_result.active == 1
    assert restored_result.changed[0].old_status == MISSING
    assert restored_result.changed[0].new_status == ACTIVE
    assert restored_node["status"] == ACTIVE
    assert restored_node["deleted_at"] is None


def test_scan_file_statuses_stores_hash_for_active_files(database):
    file_path = Path("README.md").resolve(strict=True)
    node_id = database.add_node(file_path, node_type="FILE")

    result = scan_file_statuses(database)

    assert result.hashes_updated == 1
    assert database.get_node(node_id)["file_hash"] == compute_file_hash(file_path)


def test_scan_file_statuses_can_cancel_after_progress_callback(database):
    database.add_node(unique_missing_path("first"), node_type="FILE")
    second_id = database.add_node(unique_missing_path("second"), node_type="FILE")

    result = scan_file_statuses(
        database,
        status_probe=lambda _node: MISSING,
        update_hashes=False,
        progress_callback=lambda completed, _total, _label: completed < 1,
    )

    assert result.cancelled is True
    assert result.processed_count == 1
    assert database.get_node(second_id)["status"] == ACTIVE


def test_rediscover_missing_nodes_restores_path_by_hash(database):
    found_path = Path("README.md").resolve(strict=True)
    file_hash = compute_file_hash(found_path)
    node_id = database.add_node(unique_missing_path("old-location"), node_type="FILE", file_hash=file_hash)
    database.update_node_status(node_id, MISSING)

    result = rediscover_missing_nodes(database, [Path.cwd()])

    restored = database.get_node(node_id)
    assert result.total_missing == 1
    assert result.eligible_missing == 1
    assert result.restored_count == 1
    assert restored["status"] == ACTIVE
    assert restored["path"] == str(found_path)
    assert restored["file_hash"] == file_hash


def test_scan_file_statuses_can_mark_access_denied_and_skips_deleted_nodes(database):
    active_path = unique_missing_path("active")
    deleted_path = unique_missing_path("deleted")
    active_id = database.add_node(active_path, node_type="FILE")
    deleted_id = database.add_node(deleted_path, node_type="FILE")
    database.update_node_status(deleted_id, "DELETED")
    probed_node_ids = []

    def deny_access(node):
        probed_node_ids.append(node["node_id"])
        return ACCESS_DENIED

    result = scan_file_statuses(database, status_probe=deny_access)

    assert result.total == 1
    assert result.access_denied == 1
    assert result.changed_count == 1
    assert database.get_node(active_id)["status"] == ACCESS_DENIED
    assert database.get_node(deleted_id)["status"] == "DELETED"
    assert probed_node_ids == [active_id]


def test_iter_search_files_uses_custom_ignored_dir_names():
    root_path = Path.cwd() / f".filegraph-search-{uuid.uuid4().hex}"
    try:
        keep_path = root_path / "keep"
        skip_path = root_path / "skip"
        keep_path.mkdir(parents=True)
        skip_path.mkdir()
        visible_file = keep_path / "visible.txt"
        hidden_file = skip_path / "hidden.txt"
        visible_file.write_text("visible", encoding="utf-8")
        hidden_file.write_text("hidden", encoding="utf-8")

        paths = set(iter_search_files([root_path], ignored_dir_names={"skip"}))

        assert visible_file in paths
        assert hidden_file not in paths
    finally:
        shutil.rmtree(root_path, ignore_errors=True)


def unique_missing_path(label: str = "missing") -> Path:
    return Path.cwd() / f".filegraph-{label}-{uuid.uuid4().hex}.tmp"
