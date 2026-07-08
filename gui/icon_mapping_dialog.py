from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gui.graph_viewer import ASSETS_DIR


ICON_LABELS = {
    "file": "일반 파일",
    "doc": "문서",
    "pdf": "PDF",
    "sheet": "스프레드시트",
    "slide": "프레젠테이션",
    "image": "이미지",
    "audio": "오디오",
    "video": "비디오",
    "archive": "압축 파일",
    "code": "코드",
    "data": "데이터",
    "db": "데이터베이스",
    "design": "디자인",
    "app": "앱/실행 파일",
}


class IconMappingDialog(QDialog):
    def __init__(
        self,
        overrides: dict[str, str],
        icon_names: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.icon_names = sorted(set(icon_names) | {"file"})
        self.setWindowTitle("확장자 아이콘 설정")
        self.setMinimumWidth(520)
        self.setMinimumHeight(360)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["확장자", "아이콘"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        for extension, icon_name in sorted(overrides.items()):
            self.add_mapping_row(extension, icon_name)
        if not overrides:
            self.add_mapping_row("", "file")

        add_button = QPushButton("추가")
        remove_button = QPushButton("선택 삭제")
        add_button.clicked.connect(lambda: self.add_mapping_row("", "file"))
        remove_button.clicked.connect(self.remove_selected_rows)

        row_actions = QHBoxLayout()
        row_actions.addWidget(add_button)
        row_actions.addWidget(remove_button)
        row_actions.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(row_actions)
        layout.addWidget(buttons)

    def add_mapping_row(self, extension: str, icon_name: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        extension_item = QTableWidgetItem(str(extension).removeprefix("."))
        extension_item.setData(Qt.UserRole, "extension")
        self.table.setItem(row, 0, extension_item)
        self.table.setCellWidget(row, 1, self.icon_combo(icon_name))

    def icon_combo(self, selected_icon_name: str) -> QComboBox:
        combo = QComboBox()
        for icon_name in self.icon_names:
            combo.addItem(icon_label(icon_name), icon_name)
        index = combo.findData(selected_icon_name)
        combo.setCurrentIndex(index if index >= 0 else combo.findData("file"))
        return combo

    def remove_selected_rows(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def values(self) -> dict[str, str]:
        overrides: dict[str, str] = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            extension = (item.text() if item is not None else "").strip().lower().removeprefix(".")
            combo = self.table.cellWidget(row, 1)
            if not extension or not isinstance(combo, QComboBox):
                continue
            overrides[extension] = str(combo.currentData(Qt.UserRole))
        return overrides


def available_icon_names() -> list[str]:
    excluded = {"access_denied", "app_icon", "folder", "missing"}
    return [
        path.stem
        for path in ASSETS_DIR.glob("*.svg")
        if path.stem not in excluded
    ]


def icon_label(icon_name: str) -> str:
    return ICON_LABELS.get(icon_name, icon_name)
