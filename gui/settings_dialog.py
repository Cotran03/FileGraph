from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.control_panel import (
    EDGE_LABEL_MODE_ITEMS,
    NODE_LABEL_MODE_ITEMS,
    parse_csv_values,
    parse_ignored_dir_names,
    set_button_variant,
    set_combo_value,
)
from gui.icon_mapping_dialog import available_icon_names, icon_label


class SettingsDialog(QDialog):
    def __init__(self, settings: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setMinimumSize(680, 620)
        self.icon_names = sorted(set(available_icon_names()) | {"file"})

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(14)

        graph_section = Section("그래프 표시")
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 24)
        self.font_size_input.setValue(int(settings.get("graph_font_size", 11)))
        self.font_size_input.setSuffix(" pt")
        self.node_label_combo = settings_combo(NODE_LABEL_MODE_ITEMS, settings.get("node_label_mode", "hover"))
        self.edge_label_combo = settings_combo(EDGE_LABEL_MODE_ITEMS, settings.get("edge_label_mode", "hover"))
        graph_grid = QGridLayout()
        graph_grid.setHorizontalSpacing(10)
        graph_grid.setVerticalSpacing(8)
        graph_grid.addWidget(field_label("글자 크기"), 0, 0)
        graph_grid.addWidget(self.font_size_input, 0, 1)
        graph_grid.addWidget(field_label("노드 이름"), 1, 0)
        graph_grid.addWidget(self.node_label_combo, 1, 1)
        graph_grid.addWidget(field_label("관계 이름"), 2, 0)
        graph_grid.addWidget(self.edge_label_combo, 2, 1)
        graph_section.body.addLayout(graph_grid)
        content_layout.addWidget(graph_section)

        visual_section = Section("색상")
        node_colors = settings.get("node_type_colors") or {}
        color_grid = QGridLayout()
        color_grid.setHorizontalSpacing(10)
        color_grid.setVerticalSpacing(8)
        self.file_node_color_input = QLineEdit(str(node_colors.get("FILE", "")))
        self.folder_node_color_input = QLineEdit(str(node_colors.get("FOLDER", "")))
        self.highlight_colors_input = QLineEdit(", ".join(settings.get("highlight_color_slots") or []))
        self.file_node_color_input.setPlaceholderText("#2563EB")
        self.folder_node_color_input.setPlaceholderText("#059669")
        self.highlight_colors_input.setPlaceholderText("#F97316, #EAB308, #22C55E, #06B6D4, #A855F7")
        color_grid.addWidget(field_label("파일 노드"), 0, 0)
        color_grid.addWidget(self.file_node_color_input, 0, 1)
        color_grid.addWidget(field_label("폴더 노드"), 1, 0)
        color_grid.addWidget(self.folder_node_color_input, 1, 1)
        color_grid.addWidget(field_label("강조색 슬롯"), 2, 0)
        color_grid.addWidget(self.highlight_colors_input, 2, 1)
        visual_section.body.addLayout(color_grid)
        content_layout.addWidget(visual_section)

        icon_section = Section("확장자 아이콘")
        self.icon_table = QTableWidget(0, 2)
        self.icon_table.setHorizontalHeaderLabels(["확장자", "아이콘"])
        self.icon_table.horizontalHeader().setStretchLastSection(True)
        self.icon_table.verticalHeader().setVisible(False)
        self.icon_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.icon_table.setAlternatingRowColors(True)
        self.icon_table.setMinimumHeight(180)
        for extension, icon_name in sorted((settings.get("extension_icon_overrides") or {}).items()):
            self.add_icon_mapping_row(extension, icon_name)
        if self.icon_table.rowCount() == 0:
            self.add_icon_mapping_row("", "file")
        icon_actions = QHBoxLayout()
        add_icon_button = QPushButton("추가")
        remove_icon_button = QPushButton("선택 삭제")
        set_button_variant(add_icon_button, "secondary")
        set_button_variant(remove_icon_button, "danger")
        add_icon_button.clicked.connect(lambda: self.add_icon_mapping_row("", "file"))
        remove_icon_button.clicked.connect(self.remove_selected_icon_rows)
        icon_actions.addWidget(add_icon_button)
        icon_actions.addWidget(remove_icon_button)
        icon_actions.addStretch(1)
        icon_section.body.addWidget(self.icon_table)
        icon_section.body.addLayout(icon_actions)
        content_layout.addWidget(icon_section)

        ignore_section = Section("무시 폴더")
        self.ignored_folders_input = QLineEdit(", ".join(settings.get("ignored_dir_names") or []))
        self.ignored_folders_input.setPlaceholderText(".git, .venv, node_modules")
        ignore_section.body.addWidget(self.ignored_folders_input)
        content_layout.addWidget(ignore_section)

        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content)
        scroll_area.setFrameShape(QFrame.NoFrame)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area)
        layout.addWidget(buttons)

    def add_icon_mapping_row(self, extension: str, icon_name: str) -> None:
        row = self.icon_table.rowCount()
        self.icon_table.insertRow(row)
        self.icon_table.setItem(row, 0, QTableWidgetItem(str(extension).removeprefix(".")))
        self.icon_table.setCellWidget(row, 1, self.icon_combo(icon_name))

    def icon_combo(self, selected_icon_name: str) -> QComboBox:
        combo = QComboBox()
        for icon_name in self.icon_names:
            combo.addItem(icon_label(icon_name), icon_name)
        index = combo.findData(selected_icon_name)
        combo.setCurrentIndex(index if index >= 0 else combo.findData("file"))
        return combo

    def remove_selected_icon_rows(self) -> None:
        rows = sorted({index.row() for index in self.icon_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.icon_table.removeRow(row)

    def values(self) -> dict[str, Any]:
        return {
            "graph_font_size": self.font_size_input.value(),
            "ignored_dir_names": parse_ignored_dir_names(self.ignored_folders_input.text()),
            "node_label_mode": self.node_label_combo.currentData(Qt.UserRole),
            "edge_label_mode": self.edge_label_combo.currentData(Qt.UserRole),
            "visual_settings": {
                "node_type_colors": {
                    "FILE": self.file_node_color_input.text().strip(),
                    "FOLDER": self.folder_node_color_input.text().strip(),
                },
                "highlight_color_slots": parse_csv_values(self.highlight_colors_input.text()),
                "extension_icon_overrides": self.icon_mapping_values(),
            },
        }

    def icon_mapping_values(self) -> dict[str, str]:
        overrides: dict[str, str] = {}
        for row in range(self.icon_table.rowCount()):
            item = self.icon_table.item(row, 0)
            extension = (item.text() if item is not None else "").strip().lower().removeprefix(".")
            combo = self.icon_table.cellWidget(row, 1)
            if extension and isinstance(combo, QComboBox):
                overrides[extension] = str(combo.currentData(Qt.UserRole))
        return overrides


class Section(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("section")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        layout.addLayout(self.body)


def settings_combo(items: tuple[tuple[str, str], ...], selected_value: str) -> QComboBox:
    combo = QComboBox()
    combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    for text, value in items:
        combo.addItem(text, value)
    set_combo_value(combo, selected_value)
    return combo


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label
