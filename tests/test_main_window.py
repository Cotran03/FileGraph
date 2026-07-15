import os
import csv
from pathlib import Path
import shutil
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox

from core.database_manager import DatabaseManager
from core.file_integrity import compute_file_hash
from gui.main_window import (
    DUPLICATE_NODE_CANCEL,
    DUPLICATE_NODE_FOCUS,
    DUPLICATE_NODE_RELATION,
    EDGE_LABEL_MODE_SETTING,
    GRAPH_LABEL_FONT_SIZE_SETTING,
    IGNORED_DIR_NAMES_SETTING,
    MainWindow,
    NODE_CONTEXT_ADD_RELATION,
    NODE_CONTEXT_DELETE_NODE,
    NODE_CONTEXT_EDIT_RELATIONS,
    NODE_CONTEXT_TOGGLE_CONTAINS,
    NODE_LABEL_MODE_SETTING,
    NODE_LABEL_MODE_USER_SET_SETTING,
    build_import_plan,
    expand_import_paths,
    relation_context_label,
    validate_filegraph_database,
)


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_delete_node_soft_deletes_node_and_hides_its_relations(app, monkeypatch):
    window = MainWindow(":memory:")
    source_id = window.database.add_node("C:/workspace/brief.md", node_type="FILE")
    target_id = window.database.add_node("C:/workspace/deck.pptx", node_type="FILE")
    window.database.add_relation(source_id, target_id)
    window.selected_node = window.database.get_node(source_id)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    window.delete_node(source_id)

    assert window.database.get_node(source_id)["status"] == "DELETED"
    assert [node["node_id"] for node in window.database.list_nodes()] == [target_id]
    assert window.database.list_relations() == []
    assert len(window.database.list_relations(include_deleted=True)) == 1
    assert window.selected_node is None
    window.close()


def test_show_focus_graph_renders_only_nodes_within_depth(app):
    window = MainWindow(":memory:")
    first_id = window.database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = window.database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = window.database.add_node("C:/workspace/third.md", node_type="FILE")
    unrelated_id = window.database.add_node("C:/workspace/unrelated.md", node_type="FILE")
    window.database.add_relation(first_id, second_id)
    window.database.add_relation(second_id, third_id)
    window.selected_node = window.database.get_node(first_id)

    window.show_focus_graph(1)

    assert set(window.graph_viewer.node_items) == {first_id, second_id}
    assert third_id not in window.graph_viewer.node_items
    assert unrelated_id not in window.graph_viewer.node_items
    assert window.control_panel.selected_node_id() == first_id
    window.close()


def test_search_suggestions_show_matching_nodes(app):
    window = MainWindow(":memory:")
    node_id = window.database.add_node("C:/workspace/brief.md", node_type="FILE")

    window.update_search_suggestions("br")

    assert window.control_panel.search_suggestions.count() == 1
    assert window.control_panel.search_suggestions.item(0).data(Qt.UserRole) == node_id
    window.close()


def test_candidate_panel_keeps_global_recommendations_when_unrelated_node_is_selected(app):
    window = MainWindow(":memory:")
    source_id = window.database.add_node("C:/workspace/analysis.py", node_type="FILE")
    target_id = window.database.add_node("C:/workspace/data.csv", node_type="FILE")
    unrelated_id = window.database.add_node("C:/workspace/notes.txt", node_type="FILE")
    candidate_id = window.database.add_relationship_candidate(
        source_id,
        target_id,
        "READS",
        confidence=0.95,
        detector="test",
        evidence="analysis.py:1",
    )
    window.selected_node = window.database.get_node(unrelated_id)

    window.refresh_candidate_panel()

    assert window.control_panel.candidate_list.count() == 1
    assert window.control_panel.candidate_list.item(0).data(Qt.UserRole) == candidate_id
    window.close()


def test_approving_candidate_moves_view_to_related_nodes(app, monkeypatch):
    window = MainWindow(":memory:")
    source_id = window.database.add_node("C:/workspace/analysis.py", node_type="FILE")
    target_id = window.database.add_node("C:/workspace/data.csv", node_type="FILE")
    candidate_id = window.database.add_relationship_candidate(
        source_id,
        target_id,
        "READS",
        confidence=0.95,
        detector="test",
        evidence="analysis.py:1",
    )
    focused = []
    monkeypatch.setattr(window.graph_viewer, "focus_nodes", lambda node_ids: focused.append(node_ids))

    window.approve_relationship_candidate(candidate_id)

    assert focused == [[source_id, target_id]]
    assert window.database.list_relationship_candidates() == []
    window.close()


def test_root_folder_annotation_marks_folders_without_parent(app):
    window = MainWindow(":memory:")
    root_id = window.database.add_node("C:/workspace", node_type="FOLDER")
    child_id = window.database.add_node("C:/workspace/assets", node_type="FOLDER")
    window.database.add_relation(root_id, child_id, relation_type_code="CONTAINS")

    window.reload_graph()

    nodes = {node["node_id"]: node for node in window.current_graph_data["nodes"]}
    assert nodes[root_id]["is_root_folder"] is True
    assert nodes[child_id]["is_root_folder"] is False
    window.close()


def test_undo_restores_deleted_node(app, monkeypatch):
    window = MainWindow(":memory:")
    node_id = window.database.add_node("C:/workspace/brief.md", node_type="FILE")
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    window.delete_node(node_id)
    window.undo_last_action()

    assert window.database.get_node(node_id)["status"] == "ACTIVE"
    window.close()


def test_add_dropped_paths_registers_files_and_folders(app, monkeypatch):
    window = MainWindow(":memory:")
    file_path = os.path.abspath("README.md")
    folder_path = os.getcwd()
    monkeypatch.setattr(window, "ask_folder_import_options", lambda *, folder_count: False)

    window.add_dropped_paths([file_path, folder_path, file_path])

    nodes = window.database.list_nodes()
    assert len(nodes) == 2
    assert {node["node_type"] for node in nodes} == {"FILE", "FOLDER"}
    assert window.selected_node["path"] == str(Path(folder_path).resolve(strict=False))
    assert window.control_panel.selected_node_id() == window.selected_node["node_id"]
    window.close()


def test_add_dropped_paths_restores_deleted_node(app):
    window = MainWindow(":memory:")
    file_path = os.path.abspath("README.md")
    node_id = window.database.add_node(file_path, node_type="FILE")
    window.database.update_node_status(node_id, "DELETED")

    window.add_dropped_paths([file_path])

    assert window.database.get_node(node_id)["status"] == "ACTIVE"
    assert window.selected_node["node_id"] == node_id
    assert window.control_panel.selected_node_id() == node_id
    window.close()


def test_add_file_duplicate_can_focus_existing_node(app, monkeypatch):
    window = MainWindow(":memory:")
    file_path = os.path.abspath("README.md")
    node_id = window.database.add_node(file_path, node_type="FILE")
    monkeypatch.setattr(window, "ask_duplicate_node_action", lambda existing: DUPLICATE_NODE_FOCUS)

    window._add_node(file_path, node_type="FILE")

    assert window.selected_node["node_id"] == node_id
    assert window.control_panel.selected_node_id() == node_id
    assert node_id in window.graph_viewer.node_items
    window.close()


def test_add_file_duplicate_can_start_relation_flow(app, monkeypatch):
    window = MainWindow(":memory:")
    file_path = os.path.abspath("README.md")
    node_id = window.database.add_node(file_path, node_type="FILE")
    relation_requests = []
    monkeypatch.setattr(window, "ask_duplicate_node_action", lambda existing: DUPLICATE_NODE_RELATION)
    monkeypatch.setattr(window, "add_relation", lambda: relation_requests.append(window.selected_node["node_id"]))

    window._add_node(file_path, node_type="FILE")

    assert relation_requests == [node_id]
    assert window.control_panel.selected_node_id() == node_id
    window.close()


def test_add_file_duplicate_can_be_cancelled(app, monkeypatch):
    window = MainWindow(":memory:")
    file_path = os.path.abspath("README.md")
    window.database.add_node(file_path, node_type="FILE")
    monkeypatch.setattr(window, "ask_duplicate_node_action", lambda existing: DUPLICATE_NODE_CANCEL)

    window._add_node(file_path, node_type="FILE")

    assert window.selected_node is None
    window.close()


def test_add_dropped_paths_prompts_when_every_path_is_duplicate(app, monkeypatch):
    window = MainWindow(":memory:")
    file_path = os.path.abspath("README.md")
    node_id = window.database.add_node(file_path, node_type="FILE")
    prompted = []

    def choose_focus(existing):
        prompted.append(existing["node_id"])
        return DUPLICATE_NODE_FOCUS

    monkeypatch.setattr(window, "ask_duplicate_node_action", choose_focus)

    window.add_dropped_paths([file_path])

    assert prompted == [node_id]
    assert window.selected_node["node_id"] == node_id
    window.close()


def test_add_dropped_paths_skips_mixed_duplicates_without_prompt(app, monkeypatch):
    window = MainWindow(":memory:")
    existing_path = os.path.abspath("README.md")
    new_path = os.path.abspath("SPEC.md")
    window.database.add_node(existing_path, node_type="FILE")
    monkeypatch.setattr(
        window,
        "ask_duplicate_node_action",
        lambda existing: pytest.fail("mixed duplicate import should not prompt"),
    )

    window.add_dropped_paths([existing_path, new_path])

    assert len(window.database.list_nodes()) == 2
    assert window.selected_node["path"] == str(Path(new_path).resolve(strict=False))
    window.close()


def test_add_dropped_paths_cancelled_from_folder_popup_adds_nothing(app, monkeypatch):
    window = MainWindow(":memory:")
    folder_path = os.getcwd()
    monkeypatch.setattr(window, "ask_folder_import_options", lambda *, folder_count: None)

    window.add_dropped_paths([folder_path])

    assert window.database.list_nodes() == []
    window.close()


def test_add_dropped_paths_can_register_internal_files(app, monkeypatch):
    window = MainWindow(":memory:")
    folder_path = os.path.abspath("core")
    monkeypatch.setattr(window, "ask_folder_import_options", lambda *, folder_count: True)

    window.add_dropped_paths([folder_path])

    nodes = window.database.list_nodes()
    paths = {node["path"] for node in nodes}
    assert str(Path(folder_path).resolve(strict=False)) in paths
    assert str(Path("core/database_manager.py").resolve(strict=False)) in paths
    assert str(Path("core/graph_manager.py").resolve(strict=False)) in paths
    assert any(node["node_type"] == "FOLDER" for node in nodes)
    assert any(node["node_type"] == "FILE" for node in nodes)
    window.close()


def test_add_dropped_folder_contents_creates_contains_relations(app, monkeypatch):
    folder_path = Path("core").resolve(strict=True)
    first_file_path = Path("core/database_manager.py").resolve(strict=True)
    second_file_path = Path("core/graph_manager.py").resolve(strict=True)
    window = MainWindow(":memory:")
    monkeypatch.setattr(window, "ask_folder_import_options", lambda *, folder_count: True)

    window.add_dropped_paths([str(folder_path)])

    nodes_by_path = {node["path"]: node for node in window.database.list_nodes()}
    folder_id = nodes_by_path[str(folder_path)]["node_id"]
    first_file_id = nodes_by_path[str(first_file_path)]["node_id"]
    second_file_id = nodes_by_path[str(second_file_path)]["node_id"]
    relation_facts = {
        (relation["source_id"], relation["target_id"], relation["relation_type_code"], relation["strength"])
        for relation in window.database.list_relations(node_id=folder_id)
    }

    assert (folder_id, first_file_id, "CONTAINS", "HIGH") in relation_facts
    assert (folder_id, second_file_id, "CONTAINS", "HIGH") in relation_facts
    assert all(relation["is_directional"] for relation in window.database.list_relations(node_id=folder_id))
    assert window.selected_node["node_id"] == folder_id
    window.close()


def test_add_dropped_folder_contents_links_existing_nodes(app, monkeypatch):
    folder_path = Path("core").resolve(strict=True)
    file_path = Path("core/database_manager.py").resolve(strict=True)
    window = MainWindow(":memory:")
    imported_node_ids = {
        path: window.database.add_node(path, node_type=node_type)
        for path, node_type in expand_import_paths([str(folder_path)], include_folder_contents=True)
    }
    folder_id = imported_node_ids[str(folder_path)]
    file_id = imported_node_ids[str(file_path)]
    monkeypatch.setattr(window, "ask_folder_import_options", lambda *, folder_count: True)
    monkeypatch.setattr(
        window,
        "ask_duplicate_node_action",
        lambda existing: pytest.fail("contains relation creation should not prompt for all-duplicate imports"),
    )

    window.add_dropped_paths([str(folder_path)])

    assert len(window.database.list_nodes()) == len(imported_node_ids)
    relations = window.database.list_relations(node_id=folder_id)
    relation_facts = {
        (relation["source_id"], relation["target_id"], relation["relation_type_code"])
        for relation in relations
    }
    assert (folder_id, file_id, "CONTAINS") in relation_facts
    assert window.selected_node["node_id"] == folder_id
    window.close()


def test_expand_import_paths_skips_repeated_paths_and_cache_dirs():
    paths = expand_import_paths(["core", "core/database_manager.py"], include_folder_contents=True)
    path_values = [path for path, _node_type in paths]

    assert path_values.count(str(Path("core/database_manager.py").resolve(strict=False))) == 1
    assert not any("__pycache__" in path for path in path_values)


def test_build_import_plan_tracks_folder_contains_pairs():
    folder_path = Path("core").resolve(strict=True)
    file_path = Path("core/database_manager.py").resolve(strict=True)

    plan = build_import_plan([str(folder_path)], include_folder_contents=True)

    assert (str(folder_path), "FOLDER") in plan.entries
    assert (str(file_path), "FILE") in plan.entries
    assert (str(folder_path), str(file_path)) in plan.contains_pairs


def test_build_import_plan_tracks_nested_folder_hierarchy():
    root_path = Path.cwd() / f".filegraph-hierarchy-{uuid.uuid4().hex}"
    try:
        nested_path = root_path / "child"
        nested_path.mkdir(parents=True)
        file_path = nested_path / "note.txt"
        file_path.write_text("hello", encoding="utf-8")

        plan = build_import_plan([str(root_path)], include_folder_contents=True)

        assert (str(root_path.resolve(strict=False)), "FOLDER") in plan.entries
        assert (str(nested_path.resolve(strict=False)), "FOLDER") in plan.entries
        assert (str(file_path.resolve(strict=False)), "FILE") in plan.entries
        assert (str(root_path.resolve(strict=False)), str(nested_path.resolve(strict=False))) in plan.contains_pairs
        assert (str(nested_path.resolve(strict=False)), str(file_path.resolve(strict=False))) in plan.contains_pairs
    finally:
        shutil.rmtree(root_path, ignore_errors=True)


def test_build_import_plan_uses_custom_ignored_dirs():
    root_path = Path.cwd() / f".filegraph-ignore-{uuid.uuid4().hex}"
    try:
        keep_path = root_path / "keep"
        skip_path = root_path / "skip"
        keep_path.mkdir(parents=True)
        skip_path.mkdir()
        (keep_path / "visible.txt").write_text("visible", encoding="utf-8")
        (skip_path / "hidden.txt").write_text("hidden", encoding="utf-8")

        plan = build_import_plan(
            [str(root_path)],
            include_folder_contents=True,
            ignored_dir_names={"skip"},
        )
        paths = {path for path, _node_type in plan.entries}

        assert str((keep_path / "visible.txt").resolve(strict=False)) in paths
        assert str(skip_path.resolve(strict=False)) not in paths
        assert str((skip_path / "hidden.txt").resolve(strict=False)) not in paths
    finally:
        shutil.rmtree(root_path, ignore_errors=True)


def test_build_import_plan_skips_direct_ignored_folder():
    root_path = Path.cwd() / f".filegraph-ignore-root-{uuid.uuid4().hex}"
    try:
        skip_path = root_path / "skip"
        skip_path.mkdir(parents=True)
        (skip_path / "hidden.txt").write_text("hidden", encoding="utf-8")

        plan = build_import_plan(
            [str(skip_path)],
            include_folder_contents=True,
            ignored_dir_names={"skip"},
        )

        assert plan.entries == []
        assert plan.contains_pairs == []
    finally:
        shutil.rmtree(root_path, ignore_errors=True)


def test_add_dropped_paths_skips_direct_ignored_folder_without_prompt(app, monkeypatch):
    root_path = Path.cwd() / f".filegraph-drop-ignore-{uuid.uuid4().hex}"
    try:
        skip_path = root_path / "skip"
        skip_path.mkdir(parents=True)
        (skip_path / "hidden.txt").write_text("hidden", encoding="utf-8")
        window = MainWindow(":memory:")
        window.ignored_dir_names = {"skip"}
        monkeypatch.setattr(
            window,
            "ask_folder_import_options",
            lambda *, folder_count: pytest.fail("ignored folders should not prompt for import options"),
        )

        window.add_dropped_paths([str(skip_path)])

        assert window.database.list_nodes() == []
        window.close()
    finally:
        shutil.rmtree(root_path, ignore_errors=True)


def test_graph_font_size_updates_viewer_control_and_setting(app):
    window = MainWindow(":memory:")

    window.set_graph_font_size(16)

    assert window.graph_font_size == 16
    assert window.graph_viewer.label_font_size == 16
    assert window.database.get_setting(GRAPH_LABEL_FONT_SIZE_SETTING) == "16"
    window.close()


def test_settings_updates_viewer_and_database(app):
    window = MainWindow(":memory:")

    window.set_node_label_mode("all")
    window.set_edge_label_mode("always")
    window.set_ignored_dir_names(["build", ".cache"])

    assert window.graph_viewer.node_label_visibility == "all"
    assert window.graph_viewer.edge_label_visibility == "always"
    assert window.database.get_setting(NODE_LABEL_MODE_SETTING) == "all"
    assert window.database.get_setting(EDGE_LABEL_MODE_SETTING) == "always"
    assert window.database.get_setting(IGNORED_DIR_NAMES_SETTING) == ".cache,build"
    window.close()


def test_legacy_always_node_label_mode_loads_as_all(app):
    window = MainWindow(":memory:")

    window.set_node_label_mode("always")

    assert window.node_label_mode == "all"
    assert window.database.get_setting(NODE_LABEL_MODE_SETTING) == "all"
    window.close()


def test_legacy_unclaimed_node_label_mode_defaults_to_hover(app):
    window = MainWindow(":memory:")
    window.database.set_setting(NODE_LABEL_MODE_SETTING, "files")

    assert window._load_node_label_mode() == "hover"
    window.close()


def test_user_saved_node_label_mode_is_preserved(app):
    window = MainWindow(":memory:")
    window.database.set_setting(NODE_LABEL_MODE_SETTING, "files")
    window.database.set_setting(NODE_LABEL_MODE_USER_SET_SETTING, "1")

    assert window._load_node_label_mode() == "files"
    window.close()


def test_missing_view_preset_renders_only_missing_nodes(app):
    window = MainWindow(":memory:")
    active_id = window.database.add_node("C:/workspace/active.md", node_type="FILE")
    missing_id = window.database.add_node("C:/workspace/missing.md", node_type="FILE")
    window.database.update_node_status(missing_id, "MISSING")

    window.apply_view_preset("missing")

    assert active_id not in window.graph_viewer.node_items
    assert set(window.graph_viewer.node_items) == {missing_id}
    assert "누락 파일만" in window.statusBar().currentMessage()
    window.close()


def test_highlighted_view_preset_includes_neighbors(app):
    window = MainWindow(":memory:")
    highlighted_id = window.database.add_node("C:/workspace/highlighted.md", node_type="FILE")
    neighbor_id = window.database.add_node("C:/workspace/neighbor.md", node_type="FILE")
    unrelated_id = window.database.add_node("C:/workspace/unrelated.md", node_type="FILE")
    window.database.add_relation(highlighted_id, neighbor_id)
    window.database.update_node_highlight_color(highlighted_id, "#F97316")

    window.apply_view_preset("highlighted")

    assert set(window.graph_viewer.node_items) == {highlighted_id, neighbor_id}
    assert unrelated_id not in window.graph_viewer.node_items
    window.close()


def test_folder_view_preset_renders_selected_folder_subtree(app):
    window = MainWindow(":memory:")
    root_id = window.database.add_node("C:/workspace", node_type="FOLDER")
    child_folder_id = window.database.add_node("C:/workspace/assets", node_type="FOLDER")
    file_id = window.database.add_node("C:/workspace/assets/logo.png", node_type="FILE")
    unrelated_id = window.database.add_node("C:/other/readme.md", node_type="FILE")
    window.database.add_relation(root_id, child_folder_id, relation_type_code="CONTAINS")
    window.database.add_relation(child_folder_id, file_id, relation_type_code="CONTAINS")
    window.selected_node = window.database.get_node(root_id)

    window.apply_view_preset("folder")

    assert set(window.graph_viewer.node_items) == {root_id, child_folder_id, file_id}
    assert unrelated_id not in window.graph_viewer.node_items
    window.close()


def test_validate_filegraph_database_accepts_initialized_database(tmp_path):
    db_path = tmp_path / "filegraph.db"
    database = DatabaseManager(db_path)
    database.init_db()
    database.close()

    is_valid, message = validate_filegraph_database(db_path)

    assert is_valid is True
    assert message == ""


def test_validate_filegraph_database_rejects_non_database_file(tmp_path):
    bad_path = tmp_path / "not-a-db.db"
    bad_path.write_text("not sqlite", encoding="utf-8")

    is_valid, message = validate_filegraph_database(bad_path)

    assert is_valid is False
    assert "SQLite DB" in message


def test_replace_database_file_imports_nodes_and_keeps_backup(app, tmp_path):
    target_path = tmp_path / "target.db"
    source_path = tmp_path / "source.db"
    window = MainWindow(target_path)
    window.database.add_node("C:/workspace/old.md", node_type="FILE")
    source = DatabaseManager(source_path)
    source.init_db()
    new_id = source.add_node("C:/workspace/new.md", node_type="FILE")
    source.close()

    backup_path = window.replace_database_file(source_path)

    imported_paths = {node["path"] for node in window.database.list_nodes()}
    assert backup_path.exists()
    assert window.database.get_node(new_id) is not None
    assert any(path.endswith("workspace\\new.md") or path.endswith("workspace/new.md") for path in imported_paths)
    assert not any(path.endswith("workspace\\old.md") or path.endswith("workspace/old.md") for path in imported_paths)
    window.close()


def test_export_graph_csv_writes_nodes_and_relations(app, monkeypatch):
    export_dir = Path.cwd() / f".filegraph-export-{uuid.uuid4().hex}"
    window = MainWindow(":memory:")
    try:
        export_dir.mkdir()
        source_id = window.database.add_node("C:/workspace/brief.md", node_type="FILE")
        target_id = window.database.add_node("C:/workspace/deck.pptx", node_type="FILE")
        relation_id = window.database.add_relation(source_id, target_id, relation_type_code="REFERENCE")
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(export_dir))

        window.export_graph_csv()

        with (export_dir / "nodes.csv").open(encoding="utf-8-sig", newline="") as handle:
            nodes = list(csv.DictReader(handle))
        with (export_dir / "relations.csv").open(encoding="utf-8-sig", newline="") as handle:
            relations = list(csv.DictReader(handle))

        assert {row["name"] for row in nodes} == {"brief.md", "deck.pptx"}
        assert relations[0]["relation_id"] == str(relation_id)
        assert relations[0]["relation_type_code"] == "REFERENCE"
        assert "CSV" in window.statusBar().currentMessage()
    finally:
        window.close()
        shutil.rmtree(export_dir, ignore_errors=True)


def test_refresh_file_statuses_marks_missing_paths(app):
    window = MainWindow(":memory:")
    file_path = Path.cwd() / f".filegraph-main-window-missing-{uuid.uuid4().hex}.tmp"
    node_id = window.database.add_node(file_path, node_type="FILE")

    window.refresh_file_statuses()

    assert window.database.get_node(node_id)["status"] == "MISSING"
    assert node_id in window.graph_viewer.node_items
    assert "변경 1개" in window.statusBar().currentMessage()
    window.close()


def test_rediscover_missing_files_restores_node_path(app):
    window = MainWindow(":memory:")
    found_path = Path("README.md").resolve(strict=True)
    file_hash = compute_file_hash(found_path)
    node_id = window.database.add_node(
        Path.cwd() / f".filegraph-main-window-old-{uuid.uuid4().hex}.tmp",
        node_type="FILE",
        file_hash=file_hash,
    )
    window.database.update_node_status(node_id, "MISSING")

    result = window.rediscover_missing_files([str(Path.cwd())])

    restored = window.database.get_node(node_id)
    assert result.restored_count == 1
    assert restored["status"] == "ACTIVE"
    assert restored["path"] == str(found_path)
    assert "복구 1개" in window.statusBar().currentMessage()
    window.close()


def test_show_node_context_menu_selects_right_clicked_node(app, monkeypatch):
    window = MainWindow(":memory:")
    node_id = window.database.add_node("C:/workspace/brief.md", node_type="FILE")
    positions = []
    monkeypatch.setattr(window, "exec_context_menu", lambda _menu, position: positions.append(position))

    window.show_node_context_menu(window.database.get_node(node_id), QPoint(15, 25))

    assert window.selected_node["node_id"] == node_id
    assert window.control_panel.selected_node_id() == node_id
    assert positions == [QPoint(15, 25)]
    window.close()


def test_node_context_menu_actions_reuse_relation_and_delete_flows(app, monkeypatch):
    window = MainWindow(":memory:")
    source_id = window.database.add_node("C:/workspace/source.md", node_type="FILE")
    target_id = window.database.add_node("C:/workspace/target.md", node_type="FILE")
    relation_id = window.database.add_relation(source_id, target_id)
    calls = []
    monkeypatch.setattr(window, "add_relation", lambda: calls.append(("add_relation", window.selected_node["node_id"])))
    monkeypatch.setattr(window, "edit_relation", lambda edited_id: calls.append(("edit_relation", edited_id)))
    monkeypatch.setattr(window, "delete_node_or_selection", lambda deleted_id: calls.append(("delete_node", deleted_id)))
    node = window.database.get_node(source_id)
    window.on_node_selected(node)

    menu = window.build_node_context_menu(node)
    action_with_data(menu, NODE_CONTEXT_ADD_RELATION).trigger()
    edit_menu = action_with_data(menu, NODE_CONTEXT_EDIT_RELATIONS).menu()
    edit_menu.actions()[0].trigger()
    action_with_data(menu, NODE_CONTEXT_DELETE_NODE).trigger()

    assert calls == [
        ("add_relation", source_id),
        ("edit_relation", relation_id),
        ("delete_node", source_id),
    ]
    window.close()


def test_node_context_menu_disables_relation_edit_when_node_has_no_relations(app):
    window = MainWindow(":memory:")
    node_id = window.database.add_node("C:/workspace/source.md", node_type="FILE")

    menu = window.build_node_context_menu(window.database.get_node(node_id))
    edit_menu = action_with_data(menu, NODE_CONTEXT_EDIT_RELATIONS).menu()

    assert not edit_menu.isEnabled()
    assert not edit_menu.actions()[0].isEnabled()
    window.close()


def test_folder_context_menu_toggles_contained_file_nodes(app):
    window = MainWindow(":memory:")
    folder_id = window.database.add_node("C:/workspace/assets", node_type="FOLDER")
    file_id = window.database.add_node("C:/workspace/assets/logo.png", node_type="FILE")
    window.database.add_relation(folder_id, file_id, relation_type_code="CONTAINS", strength="HIGH")
    window.on_node_selected(window.database.get_node(folder_id))
    window.reload_graph()

    assert folder_id in window.graph_viewer.node_items
    assert file_id in window.graph_viewer.node_items

    collapse_menu = window.build_node_context_menu(window.database.get_node(folder_id))
    collapse_action = action_with_data(collapse_menu, NODE_CONTEXT_TOGGLE_CONTAINS)
    assert collapse_action.isEnabled()
    assert "접기" in collapse_action.text()

    collapse_action.trigger()

    assert folder_id in window.graph_viewer.node_items
    assert file_id not in window.graph_viewer.node_items
    assert folder_id in window.collapsed_folder_node_ids
    assert window.graph_viewer.node_items[folder_id].node["is_collapsed"] is True
    assert window.graph_viewer.node_items[folder_id].node["collapsed_file_count"] == 1
    assert window.graph_viewer.node_items[folder_id].collapsed_badge_item is not None

    expand_menu = window.build_node_context_menu(window.database.get_node(folder_id))
    expand_action = action_with_data(expand_menu, NODE_CONTEXT_TOGGLE_CONTAINS)
    assert "펼치기" in expand_action.text()

    expand_action.trigger()

    assert folder_id in window.graph_viewer.node_items
    assert file_id in window.graph_viewer.node_items
    assert folder_id not in window.collapsed_folder_node_ids
    window.close()


def test_expanding_moved_folder_translates_contained_file_positions(app):
    window = MainWindow(":memory:")
    folder_id = window.database.add_node("C:/workspace/assets", node_type="FOLDER")
    file_id = window.database.add_node("C:/workspace/assets/logo.png", node_type="FILE")
    window.database.add_relation(folder_id, file_id, relation_type_code="CONTAINS", strength="HIGH")
    window.database.update_node_layouts({folder_id: (0.0, 0.0), file_id: (120.0, 40.0)})
    window.reload_graph()

    window.toggle_folder_contents(folder_id)
    window.graph_viewer.node_items[folder_id].setPos(300.0, 200.0)
    window.on_node_moved(folder_id, 300.0, 200.0)
    window.toggle_folder_contents(folder_id)

    moved_file = window.database.get_node(file_id)
    assert moved_file["layout_x"] == pytest.approx(420.0)
    assert moved_file["layout_y"] == pytest.approx(240.0)
    window.close()


def test_focus_graph_respects_collapsed_folder_contents(app):
    window = MainWindow(":memory:")
    folder_id = window.database.add_node("C:/workspace/assets", node_type="FOLDER")
    file_id = window.database.add_node("C:/workspace/assets/logo.png", node_type="FILE")
    neighbor_id = window.database.add_node("C:/workspace/neighbor.md", node_type="FILE")
    window.database.add_relation(folder_id, file_id, relation_type_code="CONTAINS", strength="HIGH")
    window.database.add_relation(folder_id, neighbor_id)
    window.collapsed_folder_node_ids.add(folder_id)
    window.selected_node = window.database.get_node(folder_id)

    window.show_focus_graph(1)

    assert set(window.graph_viewer.node_items) == {folder_id, neighbor_id}
    assert file_id not in window.graph_viewer.node_items
    assert window.graph_viewer.node_items[folder_id].node["is_collapsed"] is True
    assert window.control_panel.relation_list.count() == 1
    window.close()


def test_folder_context_menu_disables_toggle_without_contained_files(app):
    window = MainWindow(":memory:")
    folder_id = window.database.add_node("C:/workspace/assets", node_type="FOLDER")

    menu = window.build_node_context_menu(window.database.get_node(folder_id))
    toggle_action = action_with_data(menu, NODE_CONTEXT_TOGGLE_CONTAINS)

    assert not toggle_action.isEnabled()
    assert toggle_action.text() == "내부 파일 없음"
    window.close()


def test_context_delete_uses_all_selected_nodes(app, monkeypatch):
    window = MainWindow(":memory:")
    first_id = window.database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = window.database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = window.database.add_node("C:/workspace/third.md", node_type="FILE")
    window.reload_graph()
    window.graph_viewer.node_items[first_id].setSelected(True)
    window.graph_viewer.node_items[second_id].setSelected(True)
    deleted_groups = []
    monkeypatch.setattr(window, "delete_nodes", lambda node_ids: deleted_groups.append(node_ids))

    window.delete_node_or_selection(first_id)

    assert deleted_groups == [[first_id, second_id]]
    assert window.context_delete_node_ids(third_id) == [third_id]
    window.close()


def test_delete_nodes_soft_deletes_selected_nodes_and_hides_their_relations(app, monkeypatch):
    window = MainWindow(":memory:")
    first_id = window.database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = window.database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = window.database.add_node("C:/workspace/third.md", node_type="FILE")
    first_relation_id = window.database.add_relation(first_id, third_id)
    second_relation_id = window.database.add_relation(second_id, third_id)
    window.selected_node = window.database.get_node(first_id)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    window.delete_nodes([first_id, second_id])

    assert window.database.get_node(first_id)["status"] == "DELETED"
    assert window.database.get_node(second_id)["status"] == "DELETED"
    assert window.database.get_node(third_id)["status"] == "ACTIVE"
    assert window.database.list_relations() == []
    assert {relation["relation_id"] for relation in window.database.list_relations(include_deleted=True)} == {
        first_relation_id,
        second_relation_id,
    }
    assert window.selected_node is None
    window.close()


def test_delete_selected_nodes_from_panel_reloads_without_deleted_item_errors(app, monkeypatch):
    window = MainWindow(":memory:")
    first_id = window.database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = window.database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = window.database.add_node("C:/workspace/third.md", node_type="FILE")
    window.reload_graph()
    window.graph_viewer.node_items[first_id].setSelected(True)
    window.graph_viewer.node_items[second_id].setSelected(True)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    window.delete_selected_nodes_from_panel()

    assert window.database.get_node(first_id)["status"] == "DELETED"
    assert window.database.get_node(second_id)["status"] == "DELETED"
    assert window.database.get_node(third_id)["status"] == "ACTIVE"
    assert set(window.graph_viewer.node_items) == {third_id}
    assert window.graph_viewer.selected_node_ids() == []
    window.close()


def test_relation_context_label_marks_directionality():
    assert relation_context_label(
        {
            "source_name": "a.md",
            "target_name": "b.md",
            "is_directional": True,
            "relation_type_name": "Reference",
        }
    ) == "a.md -> b.md / Reference"
    assert relation_context_label(
        {
            "source_name": "a.md",
            "target_name": "b.md",
            "is_directional": False,
            "relation_type_name": "Related",
        }
    ) == "a.md -- b.md / Related"


def test_reset_layout_uses_new_seed_and_persists_positions(app, monkeypatch):
    window = MainWindow(":memory:")
    first_id = window.database.add_node("C:/workspace/first.md", node_type="FILE")
    second_id = window.database.add_node("C:/workspace/second.md", node_type="FILE")
    third_id = window.database.add_node("C:/workspace/third.md", node_type="FILE")
    window.database.add_relation(first_id, second_id)
    window.database.add_relation(second_id, third_id)
    seeds = iter([1, 2])
    monkeypatch.setattr(window, "next_layout_seed", lambda: next(seeds))

    window.reset_layout()
    first_positions = {
        node_id: (
            window.database.get_node(node_id)["layout_x"],
            window.database.get_node(node_id)["layout_y"],
        )
        for node_id in (first_id, second_id, third_id)
    }

    window.reset_layout()
    second_positions = {
        node_id: (
            window.database.get_node(node_id)["layout_x"],
            window.database.get_node(node_id)["layout_y"],
        )
        for node_id in (first_id, second_id, third_id)
    }

    assert all(x is not None and y is not None for x, y in first_positions.values())
    assert all(x is not None and y is not None for x, y in second_positions.values())
    assert first_positions != second_positions
    window.close()


def action_with_data(menu: QMenu, data):
    for action in menu.actions():
        if action.data() == data:
            return action
    raise AssertionError(f"menu action with data {data!r} not found")
