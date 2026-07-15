import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea

from gui.control_panel import ControlPanel


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def relation(relation_id: int) -> dict:
    return {
        "relation_id": relation_id,
        "source_name": "brief.md",
        "target_name": "deck.pptx",
        "is_directional": True,
        "relation_type_name": "참고자료",
        "strength": "HIGH",
    }


def test_show_relations_selects_first_relation_and_enables_buttons(app):
    panel = ControlPanel()

    panel.show_relations([relation(7), relation(8)])

    assert panel.selected_relation_id() == 7
    assert panel.edit_relation_button.isEnabled()
    assert panel.delete_relation_button.isEnabled()


def test_show_relations_disables_buttons_when_empty(app):
    panel = ControlPanel()

    panel.show_relations([])

    assert panel.selected_relation_id() is None
    assert not panel.edit_relation_button.isEnabled()
    assert not panel.delete_relation_button.isEnabled()


def test_edit_and_delete_buttons_emit_selected_relation_id(app):
    panel = ControlPanel()
    edited = []
    deleted = []
    panel.editRelationRequested.connect(edited.append)
    panel.deleteRelationRequested.connect(deleted.append)
    panel.show_relations([relation(7)])

    panel.edit_relation_button.click()
    panel.delete_relation_button.click()

    assert edited == [7]
    assert deleted == [7]


def test_show_node_enables_delete_node_button_and_emits_node_id(app):
    panel = ControlPanel()
    deleted = []
    panel.deleteNodeRequested.connect(deleted.append)

    panel.show_node({"node_id": 3, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE"})
    panel.delete_node_button.click()

    assert panel.selected_node_id() == 3
    assert panel.delete_node_button.isEnabled()
    assert panel.focus_depth_input.isEnabled()
    assert deleted == [3]


def test_show_node_disables_delete_node_button_when_empty(app):
    panel = ControlPanel()

    panel.show_node(None)

    assert panel.selected_node_id() is None
    assert not panel.delete_node_button.isEnabled()
    assert not panel.focus_depth_input.isEnabled()


def test_focus_depth_input_emits_depth_for_selected_node(app):
    panel = ControlPanel()
    depths = []
    full_view_requests = []
    panel.focusDepthRequested.connect(depths.append)
    panel.fullViewRequested.connect(lambda: full_view_requests.append(True))
    panel.show_node({"node_id": 3, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE"})

    panel.focus_depth_input.setValue(5)
    panel.focus_view_button.click()
    panel.full_view_button.click()

    assert depths == [5, 5]
    assert full_view_requests == [True]


def test_check_files_button_emits_request(app):
    panel = ControlPanel()
    requests = []
    panel.checkFilesRequested.connect(lambda: requests.append(True))

    panel.check_files_button.click()

    assert panel.check_files_button.text() == "파일 위치 갱신"
    assert "상태를 갱신" in panel.check_files_button.toolTip()
    assert requests == [True]


def test_locate_missing_button_emits_request(app):
    panel = ControlPanel()
    requests = []
    panel.locateMissingRequested.connect(lambda: requests.append(True))

    panel.locate_missing_button.click()

    assert requests == [True]


def test_import_database_button_emits_request(app):
    panel = ControlPanel()
    requests = []
    panel.importDatabaseRequested.connect(lambda: requests.append(True))

    panel.import_db_button.click()

    assert requests == [True]


def test_export_buttons_emit_requests(app):
    panel = ControlPanel()
    json_requests = []
    csv_requests = []
    panel.exportJsonRequested.connect(lambda: json_requests.append(True))
    panel.exportCsvRequested.connect(lambda: csv_requests.append(True))

    panel.export_json_button.click()
    panel.export_csv_button.click()

    assert json_requests == [True]
    assert csv_requests == [True]
    assert not hasattr(panel, "sample_button")


def test_view_preset_button_emits_selected_preset(app):
    panel = ControlPanel()
    presets = []
    panel.viewPresetRequested.connect(presets.append)

    panel.view_preset_combo.setCurrentIndex(panel.view_preset_combo.findData("missing"))
    panel.apply_view_preset_button.click()

    assert presets == ["missing"]


def test_settings_button_opens_separate_settings_flow(app):
    panel = ControlPanel()
    requests = []
    panel.settingsRequested.connect(lambda: requests.append(True))

    panel.settings_button.click()

    assert requests == [True]
    assert not hasattr(panel, "tabs")
    assert not hasattr(panel, "settings_tab")


def test_action_panel_scrolls_when_window_height_is_small(app):
    panel = ControlPanel()
    panel.resize(360, 300)
    panel.show()
    app.processEvents()

    assert isinstance(panel.actions_scroll_area, QScrollArea)
    assert panel.actions_scroll_area.widget() is panel.actions_content
    assert panel.actions_scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert panel.actions_scroll_area.verticalScrollBar().maximum() > 0
    panel.close()


def test_detail_sections_use_compact_tabs(app):
    panel = ControlPanel()

    assert panel.detail_tabs.count() == 3
    assert [panel.detail_tabs.tabText(index) for index in range(3)] == [
        "파일 맥락",
        "관계",
        "후보",
    ]

    panel.show_candidates(
        [
            {
                "candidate_id": 1,
                "source_name": "analysis.py",
                "target_name": "data.csv",
                "suggested_relation_type_name": "읽음",
                "confidence": 0.95,
                "evidence": "analysis.py:2",
            }
        ]
    )

    assert panel.detail_tabs.tabText(2) == "후보 (1)"


def test_control_panel_is_wide_enough_for_right_side_controls(app):
    panel = ControlPanel()

    assert panel.minimumWidth() >= 380
    assert panel.maximumWidth() >= 500


def test_control_panel_does_not_keep_embedded_settings_controls(app):
    panel = ControlPanel()

    assert not hasattr(panel, "apply_settings_button")
    assert not hasattr(panel, "ignored_folders_input")
    assert not hasattr(panel, "node_label_mode_combo")
    assert not hasattr(panel, "file_node_color_input")


def test_delete_button_can_emit_selected_node_group_without_current_node(app):
    panel = ControlPanel()
    selected_deletes = []
    single_deletes = []
    panel.deleteSelectedNodesRequested.connect(lambda: selected_deletes.append(True))
    panel.deleteNodeRequested.connect(single_deletes.append)

    panel.set_selected_node_count(2)
    panel.delete_node_button.click()

    assert selected_deletes == [True]
    assert single_deletes == []
    assert panel.delete_node_button.text() == "선택 노드 2개 삭제"
