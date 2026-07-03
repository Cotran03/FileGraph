import os
from pathlib import Path
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from core.file_integrity import compute_file_hash
from gui.main_window import (
    DUPLICATE_NODE_CANCEL,
    DUPLICATE_NODE_FOCUS,
    DUPLICATE_NODE_RELATION,
    GRAPH_LABEL_FONT_SIZE_SETTING,
    MainWindow,
    NODE_CONTEXT_ADD_RELATION,
    NODE_CONTEXT_DELETE_NODE,
    NODE_CONTEXT_EDIT_RELATIONS,
    NODE_CONTEXT_TOGGLE_CONTAINS,
    build_import_plan,
    expand_import_paths,
    relation_context_label,
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


def test_graph_font_size_updates_viewer_control_and_setting(app):
    window = MainWindow(":memory:")

    window.set_graph_font_size(16)

    assert window.graph_font_size == 16
    assert window.graph_viewer.label_font_size == 16
    assert window.control_panel.font_size_input.value() == 16
    assert window.database.get_setting(GRAPH_LABEL_FONT_SIZE_SETTING) == "16"
    window.close()


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

    expand_menu = window.build_node_context_menu(window.database.get_node(folder_id))
    expand_action = action_with_data(expand_menu, NODE_CONTEXT_TOGGLE_CONTAINS)
    assert "펼치기" in expand_action.text()

    expand_action.trigger()

    assert folder_id in window.graph_viewer.node_items
    assert file_id in window.graph_viewer.node_items
    assert folder_id not in window.collapsed_folder_node_ids
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
