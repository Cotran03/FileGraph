import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox

from gui.settings_dialog import SettingsDialog


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_settings_dialog_collects_icon_mapping_values(app):
    dialog = SettingsDialog(
        {
            "graph_font_size": 11,
            "node_label_mode": "hover",
            "edge_label_mode": "hover",
            "ignored_dir_names": [".git"],
            "node_type_colors": {"FILE": "#2563EB", "FOLDER": "#059669"},
            "highlight_color_slots": ["#F97316"],
            "extension_icon_overrides": {},
        }
    )

    dialog.icon_table.item(0, 0).setText("proto")
    combo = dialog.icon_table.cellWidget(0, 1)
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(combo.findData("code", Qt.UserRole))

    values = dialog.values()

    assert values["node_label_mode"] == "hover"
    assert values["visual_settings"]["extension_icon_overrides"] == {"proto": "code"}


def test_settings_dialog_updates_color_previews_and_resets_defaults(app):
    dialog = SettingsDialog(
        {
            "graph_font_size": 11,
            "node_label_mode": "hover",
            "edge_label_mode": "hover",
            "ignored_dir_names": [".git"],
            "node_type_colors": {"FILE": "#111111", "FOLDER": "#222222"},
            "highlight_color_slots": ["#333333", "#444444"],
            "extension_icon_overrides": {},
        }
    )

    assert dialog.file_node_color_preview.color_value == "#111111"
    assert dialog.folder_node_color_preview.color_value == "#222222"
    assert dialog.highlight_color_previews[0].color_value == "#333333"

    dialog.file_node_color_input.setText("#abcdef")
    assert dialog.file_node_color_preview.color_value == "#ABCDEF"

    dialog.reset_colors_to_defaults()
    values = dialog.values()["visual_settings"]

    assert values["node_type_colors"] == {"FILE": "#2563EB", "FOLDER": "#059669"}
    assert values["highlight_color_slots"] == ["#F97316", "#EAB308", "#22C55E", "#06B6D4", "#A855F7"]
    assert dialog.file_node_color_preview.color_value == "#2563EB"
