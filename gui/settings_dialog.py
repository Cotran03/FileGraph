from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QHeaderView,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
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


DEFAULT_NODE_TYPE_COLORS = {
    "FILE": "#2563EB",
    "FOLDER": "#059669",
}
DEFAULT_HIGHLIGHT_COLOR_SLOTS = (
    "#F97316",
    "#EAB308",
    "#22C55E",
    "#06B6D4",
    "#A855F7",
)


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
        self.file_node_color_preview = ColorPreview()
        self.folder_node_color_preview = ColorPreview()
        self.file_node_color_picker_button = QPushButton("선택")
        self.folder_node_color_picker_button = QPushButton("선택")
        self.file_node_color_picker_button.setToolTip("파일 노드 색상 선택")
        self.folder_node_color_picker_button.setToolTip("폴더 노드 색상 선택")
        set_button_variant(self.file_node_color_picker_button, "secondary")
        set_button_variant(self.folder_node_color_picker_button, "secondary")
        self.highlight_color_previews: list[ColorPreview] = []
        self.highlight_color_picker_buttons: list[QPushButton] = []
        color_grid.addWidget(field_label("파일 노드"), 0, 0)
        color_grid.addLayout(
            color_input_row(
                self.file_node_color_input,
                self.file_node_color_preview,
                self.file_node_color_picker_button,
            ),
            0,
            1,
        )
        color_grid.addWidget(field_label("폴더 노드"), 1, 0)
        color_grid.addLayout(
            color_input_row(
                self.folder_node_color_input,
                self.folder_node_color_preview,
                self.folder_node_color_picker_button,
            ),
            1,
            1,
        )
        color_grid.addWidget(field_label("강조색 슬롯"), 2, 0)
        color_grid.addWidget(self.highlight_colors_input, 2, 1)
        highlight_preview_row = QHBoxLayout()
        highlight_preview_row.setSpacing(10)
        for index in range(5):
            preview = ColorPreview()
            picker_button = QPushButton("선택")
            picker_button.setToolTip(f"강조 색상 {index + 1} 선택")
            set_button_variant(picker_button, "secondary")
            picker_button.clicked.connect(
                lambda _checked=False, index=index: self.choose_highlight_slot_color(index)
            )
            slot_row = QHBoxLayout()
            slot_row.setSpacing(6)
            slot_row.addWidget(preview)
            slot_row.addWidget(picker_button)
            highlight_preview_row.addLayout(slot_row)
            self.highlight_color_previews.append(preview)
            self.highlight_color_picker_buttons.append(picker_button)
        highlight_preview_row.addStretch(1)
        color_grid.addWidget(field_label("미리보기"), 3, 0)
        color_grid.addLayout(highlight_preview_row, 3, 1)
        color_actions = QHBoxLayout()
        reset_colors_button = QPushButton("기본 색상으로 초기화")
        set_button_variant(reset_colors_button, "secondary")
        reset_colors_button.clicked.connect(self.reset_colors_to_defaults)
        color_actions.addWidget(reset_colors_button)
        color_actions.addStretch(1)
        visual_section.body.addLayout(color_grid)
        visual_section.body.addLayout(color_actions)
        content_layout.addWidget(visual_section)

        icon_section = Section("확장자 아이콘")
        self.icon_table = QTableWidget(0, 2)
        self.icon_table.setHorizontalHeaderLabels(["직접 입력할 확장자", "아이콘 분류"])
        self.icon_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.icon_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.icon_table.verticalHeader().setVisible(False)
        self.icon_table.verticalHeader().setDefaultSectionSize(40)
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
        self.file_node_color_input.textChanged.connect(self.sync_color_previews)
        self.folder_node_color_input.textChanged.connect(self.sync_color_previews)
        self.highlight_colors_input.textChanged.connect(self.sync_color_previews)
        self.file_node_color_picker_button.clicked.connect(
            lambda: self.choose_color_for_input(self.file_node_color_input)
        )
        self.folder_node_color_picker_button.clicked.connect(
            lambda: self.choose_color_for_input(self.folder_node_color_input)
        )
        self.sync_color_previews()

    def add_icon_mapping_row(self, extension: str, icon_name: str) -> None:
        row = self.icon_table.rowCount()
        self.icon_table.insertRow(row)
        self.icon_table.setRowHeight(row, 40)
        extension_input = QLineEdit(str(extension).removeprefix("."))
        extension_input.setPlaceholderText("예: pdf, log")
        extension_input.setToolTip("아이콘을 바꿀 확장자를 직접 입력합니다. 점(.)은 입력해도 저장 시 제거됩니다.")
        extension_input.setMinimumHeight(30)
        self.icon_table.setCellWidget(row, 0, extension_input)
        self.icon_table.setCellWidget(row, 1, self.icon_combo(icon_name))

    def icon_combo(self, selected_icon_name: str) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumHeight(30)
        for icon_name in self.icon_names:
            combo.addItem(icon_label(icon_name), icon_name)
        index = combo.findData(selected_icon_name)
        combo.setCurrentIndex(index if index >= 0 else combo.findData("file"))
        return combo

    def remove_selected_icon_rows(self) -> None:
        rows = sorted({index.row() for index in self.icon_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.icon_table.removeRow(row)

    def reset_colors_to_defaults(self) -> None:
        self.file_node_color_input.setText(DEFAULT_NODE_TYPE_COLORS["FILE"])
        self.folder_node_color_input.setText(DEFAULT_NODE_TYPE_COLORS["FOLDER"])
        self.highlight_colors_input.setText(", ".join(DEFAULT_HIGHLIGHT_COLOR_SLOTS))
        self.sync_color_previews()

    def choose_color_for_input(self, input_widget: QLineEdit) -> None:
        current_color = QColor(input_widget.text().strip())
        fallback_color = QColor(input_widget.placeholderText())
        initial_color = current_color if current_color.isValid() else fallback_color
        color = QColorDialog.getColor(initial_color, self, "색상 선택")
        if color.isValid():
            input_widget.setText(color.name().upper())

    def choose_highlight_slot_color(self, index: int) -> None:
        if index < 0 or index >= len(DEFAULT_HIGHLIGHT_COLOR_SLOTS):
            return

        highlight_colors = parse_csv_values(self.highlight_colors_input.text())
        while len(highlight_colors) <= index:
            highlight_colors.append(DEFAULT_HIGHLIGHT_COLOR_SLOTS[len(highlight_colors)])

        current_color = QColor(highlight_colors[index])
        fallback_color = QColor(DEFAULT_HIGHLIGHT_COLOR_SLOTS[index])
        initial_color = current_color if current_color.isValid() else fallback_color
        color = QColorDialog.getColor(initial_color, self, f"강조 색상 {index + 1} 선택")
        if color.isValid():
            highlight_colors[index] = color.name().upper()
            self.highlight_colors_input.setText(", ".join(highlight_colors[:5]))

    def sync_color_previews(self) -> None:
        self.file_node_color_preview.set_color(self.file_node_color_input.text().strip())
        self.folder_node_color_preview.set_color(self.folder_node_color_input.text().strip())
        highlight_colors = parse_csv_values(self.highlight_colors_input.text())
        for index, preview in enumerate(self.highlight_color_previews):
            preview.set_color(highlight_colors[index] if index < len(highlight_colors) else "")

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
            extension_widget = self.icon_table.cellWidget(row, 0)
            extension = (
                extension_widget.text()
                if isinstance(extension_widget, QLineEdit)
                else ""
            ).strip().lower().removeprefix(".")
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


class ColorPreview(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.color_value = ""
        self.setFixedSize(26, 26)
        self.setObjectName("colorPreview")
        self.set_color("")

    def set_color(self, value: str) -> None:
        color = QColor(value)
        if color.isValid():
            self.color_value = color.name().upper()
            self.setToolTip(self.color_value)
            self.setStyleSheet(
                f"border: 1px solid #94A3B8; border-radius: 5px; background: {self.color_value};"
            )
            return

        self.color_value = ""
        self.setToolTip("색상 없음")
        self.setStyleSheet("border: 1px dashed #CBD5E1; border-radius: 5px; background: #FFFFFF;")


def color_input_row(
    input_widget: QLineEdit,
    preview: ColorPreview,
    picker_button: QPushButton | None = None,
) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(input_widget, 1)
    row.addWidget(preview)
    if picker_button is not None:
        row.addWidget(picker_button)
    return row


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
