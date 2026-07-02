import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gui.relation_dialog import RelationDialog


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def nodes():
    return [
        {"node_id": 1, "name": "brief.md", "node_type": "FILE"},
        {"node_id": 2, "name": "deck.pptx", "node_type": "FILE"},
    ]


def relation_types():
    return [
        {
            "relation_type_id": 1,
            "name": "관련 있음",
            "default_is_directional": 0,
        },
        {
            "relation_type_id": 2,
            "name": "참고자료",
            "default_is_directional": 1,
        },
    ]


def test_relation_type_combo_is_preset_only(app):
    dialog = RelationDialog(nodes(), relation_types())

    assert not dialog.relation_type_combo.isEditable()
    assert dialog.values()["relation_type_id"] == 1
    assert "relation_type_name" not in dialog.values()


def test_description_captures_custom_relation_detail(app):
    dialog = RelationDialog(nodes(), relation_types())
    dialog.description_input.setText("발표 자료가 캠페인 기획서를 요약함")

    values = dialog.values()

    assert values["relation_type_id"] == 1
    assert values["description"] == "발표 자료가 캠페인 기획서를 요약함"
