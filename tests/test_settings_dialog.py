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
            "ai_enabled": False,
            "gemini_model": "gemini-test",
            "api_key_saved": False,
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
