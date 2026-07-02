import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

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
    panel.full_view_button.click()

    assert depths == [5]
    assert full_view_requests == [True]


def test_font_size_control_emits_and_can_be_set(app):
    panel = ControlPanel()
    font_sizes = []
    panel.graphFontSizeChanged.connect(font_sizes.append)

    panel.font_size_input.setValue(14)

    assert font_sizes == [14]

    panel.set_graph_font_size(12)

    assert panel.font_size_input.value() == 12
    assert font_sizes == [14]


def test_check_files_button_emits_request(app):
    panel = ControlPanel()
    requests = []
    panel.checkFilesRequested.connect(lambda: requests.append(True))

    panel.check_files_button.click()

    assert requests == [True]


def test_locate_missing_button_emits_request(app):
    panel = ControlPanel()
    requests = []
    panel.locateMissingRequested.connect(lambda: requests.append(True))

    panel.locate_missing_button.click()

    assert requests == [True]
