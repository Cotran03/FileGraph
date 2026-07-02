from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


STRENGTH_LABELS = {
    "HIGH": "상",
    "MEDIUM": "중",
    "LOW": "하",
}


class RelationDialog(QDialog):
    def __init__(
        self,
        nodes: list[dict[str, Any]],
        relation_types: list[dict[str, Any]],
        *,
        selected_node_id: int | None = None,
        initial_values: dict[str, Any] | None = None,
        lock_nodes: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.nodes = nodes
        self.relation_types = relation_types
        self.initial_values = initial_values
        self.setWindowTitle("관계 수정" if initial_values else "관계 추가")
        self.setMinimumWidth(420)

        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        self.relation_type_combo = QComboBox()
        self.relation_type_combo.setEditable(False)
        self.directional_check = QCheckBox("방향성 있음")
        self.strength_combo = QComboBox()
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("선택 입력")

        for node in nodes:
            label = f"{node.get('name', '')}  ({node.get('node_type', '')})"
            self.source_combo.addItem(label, node["node_id"])
            self.target_combo.addItem(label, node["node_id"])

        for relation_type in relation_types:
            self.relation_type_combo.addItem(relation_type["name"], relation_type)

        for code, label in STRENGTH_LABELS.items():
            self.strength_combo.addItem(label, code)
        self.strength_combo.setCurrentIndex(1)

        if selected_node_id is not None:
            self._select_combo_value(self.source_combo, selected_node_id)
            if self.target_combo.count() > 1:
                next_index = 1 if self.source_combo.currentIndex() == 0 else 0
                self.target_combo.setCurrentIndex(next_index)

        self._sync_direction_default()
        if initial_values:
            self._apply_initial_values(initial_values)
            self.source_combo.setEnabled(not lock_nodes)
            self.target_combo.setEnabled(not lock_nodes)

        form = QFormLayout()
        form.addRow("출발 노드", self.source_combo)
        form.addRow("도착 노드", self.target_combo)
        form.addRow("관계 타입", self.relation_type_combo)
        form.addRow("", self.directional_check)
        form.addRow("관계 강도", self.strength_combo)
        form.addRow("설명", self.description_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.relation_type_combo.currentIndexChanged.connect(self._sync_direction_default)

    def values(self) -> dict[str, Any]:
        relation_type = self._current_relation_type()
        return {
            "source_id": self.source_combo.currentData(Qt.UserRole),
            "target_id": self.target_combo.currentData(Qt.UserRole),
            "relation_type_id": relation_type["relation_type_id"] if isinstance(relation_type, dict) else None,
            "is_directional": self.directional_check.isChecked(),
            "strength": self.strength_combo.currentData(Qt.UserRole),
            "description": self.description_input.text().strip() or None,
        }

    def _sync_direction_default(self) -> None:
        relation_type = self._current_relation_type()
        if isinstance(relation_type, dict):
            self.directional_check.setChecked(bool(relation_type.get("default_is_directional")))

    def _apply_initial_values(self, values: dict[str, Any]) -> None:
        self._select_combo_value(self.source_combo, values["source_id"])
        self._select_combo_value(self.target_combo, values["target_id"])
        self._select_relation_type(values["relation_type_id"])
        self.directional_check.setChecked(bool(values.get("is_directional")))
        self._select_combo_value(self.strength_combo, values["strength"])
        self.description_input.setText(values.get("description") or "")

    def _select_combo_value(self, combo: QComboBox, value: Any) -> None:
        for index in range(combo.count()):
            if combo.itemData(index, Qt.UserRole) == value:
                combo.setCurrentIndex(index)
                return

    def _select_relation_type(self, relation_type_id: int) -> None:
        for index in range(self.relation_type_combo.count()):
            relation_type = self.relation_type_combo.itemData(index, Qt.UserRole)
            if isinstance(relation_type, dict) and relation_type["relation_type_id"] == relation_type_id:
                self.relation_type_combo.setCurrentIndex(index)
                return

    def _current_relation_type(self) -> dict[str, Any] | None:
        current_text = self.relation_type_combo.currentText().strip()
        for index in range(self.relation_type_combo.count()):
            relation_type = self.relation_type_combo.itemData(index, Qt.UserRole)
            if isinstance(relation_type, dict) and relation_type["name"].casefold() == current_text.casefold():
                return relation_type
        return None
