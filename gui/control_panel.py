from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ControlPanel(QWidget):
    refreshRequested = Signal()
    checkFilesRequested = Signal()
    locateMissingRequested = Signal()
    sampleDataRequested = Signal()
    resetLayoutRequested = Signal()
    addRelationRequested = Signal()
    deleteNodeRequested = Signal(int)
    focusDepthRequested = Signal(int)
    fullViewRequested = Signal()
    editRelationRequested = Signal(int)
    deleteRelationRequested = Signal(int)
    graphFontSizeChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)
        self._current_node_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(16)

        title = QLabel("FileGraph")
        title.setObjectName("panelTitle")
        root.addWidget(title)

        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        self.refresh_button = QPushButton("새로고침")
        self.check_files_button = QPushButton("상태 확인")
        self.locate_missing_button = QPushButton("누락 찾기")
        self.relation_button = QPushButton("관계 추가")
        self.sample_button = QPushButton("샘플")
        self.reset_button = QPushButton("자동 정렬")
        set_button_variant(self.relation_button, "primary")
        for button in (
            self.refresh_button,
            self.check_files_button,
            self.locate_missing_button,
            self.sample_button,
            self.reset_button,
        ):
            set_button_variant(button, "secondary")
        actions.addWidget(self.relation_button, 0, 0, 1, 2)
        actions.addWidget(self.refresh_button, 1, 0)
        actions.addWidget(self.check_files_button, 1, 1)
        actions.addWidget(self.sample_button, 2, 0)
        actions.addWidget(self.reset_button, 2, 1)
        actions.addWidget(self.locate_missing_button, 3, 0, 1, 2)
        root.addLayout(actions)

        font_controls = QHBoxLayout()
        font_controls.setSpacing(8)
        font_label = QLabel("글자 크기")
        font_label.setObjectName("fieldLabel")
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 24)
        self.font_size_input.setValue(11)
        self.font_size_input.setSuffix(" pt")
        font_controls.addWidget(font_label)
        font_controls.addWidget(self.font_size_input)
        root.addLayout(font_controls)

        self.node_section = Section("선택 노드")
        self.node_name = QLabel("선택된 노드가 없습니다.")
        self.node_name.setObjectName("nodeName")
        self.node_path = QLabel("")
        self.node_path.setObjectName("pathText")
        self.node_path.setWordWrap(True)
        self.node_meta = QLabel("")
        self.node_meta.setObjectName("metaText")
        self.node_meta.setWordWrap(True)
        self.node_section.body.addWidget(self.node_name)
        self.node_section.body.addWidget(self.node_path)
        self.node_section.body.addWidget(self.node_meta)
        self.node_section.body.addWidget(Separator())
        focus_actions = QHBoxLayout()
        focus_actions.setSpacing(8)
        self.focus_depth_input = QSpinBox()
        self.focus_depth_input.setRange(1, 99)
        self.focus_depth_input.setValue(2)
        self.focus_depth_input.setSuffix(" 단계")
        self.full_view_button = QPushButton("전체")
        set_button_variant(self.full_view_button, "segmented")
        focus_actions.addWidget(self.focus_depth_input)
        focus_actions.addWidget(self.full_view_button)
        self.node_section.body.addLayout(focus_actions)
        node_actions = QHBoxLayout()
        self.delete_node_button = QPushButton("선택 노드 삭제")
        set_button_variant(self.delete_node_button, "danger")
        node_actions.addWidget(self.delete_node_button)
        self.node_section.body.addLayout(node_actions)
        root.addWidget(self.node_section)

        self.relation_section = Section("관계")
        self.relation_list = QListWidget()
        self.relation_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.relation_section.body.addWidget(self.relation_list)
        relation_actions = QHBoxLayout()
        relation_actions.setSpacing(8)
        self.edit_relation_button = QPushButton("수정")
        self.delete_relation_button = QPushButton("삭제")
        set_button_variant(self.edit_relation_button, "secondary")
        set_button_variant(self.delete_relation_button, "danger")
        relation_actions.addWidget(self.edit_relation_button)
        relation_actions.addWidget(self.delete_relation_button)
        self.relation_section.body.addLayout(relation_actions)
        root.addWidget(self.relation_section, 1)

        self.summary = QLabel("노드 0개 / 관계 0개")
        self.summary.setObjectName("summary")
        root.addWidget(self.summary)

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.check_files_button.clicked.connect(self.checkFilesRequested.emit)
        self.locate_missing_button.clicked.connect(self.locateMissingRequested.emit)
        self.relation_button.clicked.connect(self.addRelationRequested.emit)
        self.sample_button.clicked.connect(self.sampleDataRequested.emit)
        self.reset_button.clicked.connect(self.resetLayoutRequested.emit)
        self.font_size_input.valueChanged.connect(self.graphFontSizeChanged.emit)
        self.delete_node_button.clicked.connect(self._emit_delete_node)
        self.focus_depth_input.valueChanged.connect(self._emit_focus_depth)
        self.full_view_button.clicked.connect(self.fullViewRequested.emit)
        self.edit_relation_button.clicked.connect(self._emit_edit_relation)
        self.delete_relation_button.clicked.connect(self._emit_delete_relation)
        self.relation_list.itemDoubleClicked.connect(lambda _item: self._emit_edit_relation())
        self.relation_list.itemSelectionChanged.connect(self._sync_relation_buttons)
        self._sync_node_buttons()
        self._sync_relation_buttons()

    def set_summary(self, node_count: int, relation_count: int) -> None:
        self.summary.setText(f"노드 {node_count}개 / 관계 {relation_count}개")

    def set_graph_font_size(self, point_size: int) -> None:
        self.font_size_input.blockSignals(True)
        self.font_size_input.setValue(point_size)
        self.font_size_input.blockSignals(False)

    def show_node(self, node: dict[str, Any] | None) -> None:
        if not node:
            self._current_node_id = None
            self.node_name.setText("선택된 노드가 없습니다.")
            self.node_path.setText("")
            self.node_meta.setText("")
            self._sync_node_buttons()
            return

        self._current_node_id = int(node["node_id"])
        self.node_name.setText(node.get("name", ""))
        self.node_path.setText(node.get("path", ""))
        self.node_meta.setText(
            f"{node.get('node_type', '')} · {node.get('status', '')} · AI {node.get('ai_status', '')}"
        )
        self._sync_node_buttons()

    def show_relations(self, relations: list[dict[str, Any]]) -> None:
        self.relation_list.clear()
        if not relations:
            item = QListWidgetItem("표시할 관계가 없습니다.")
            item.setFlags(Qt.NoItemFlags)
            self.relation_list.addItem(item)
            self._sync_relation_buttons()
            return

        for relation in relations:
            direction = "->" if relation.get("is_directional") else "--"
            label = (
                f"{relation.get('source_name', '')} {direction} {relation.get('target_name', '')}  "
                f"{relation.get('relation_type_name', '')} / {relation.get('strength', '')}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, relation.get("relation_id"))
            self.relation_list.addItem(item)
        self.relation_list.setCurrentRow(0)
        self._sync_relation_buttons()

    def selected_relation_id(self) -> int | None:
        item = self.relation_list.currentItem()
        if item is None:
            return None
        relation_id = item.data(Qt.UserRole)
        return int(relation_id) if relation_id is not None else None

    def selected_node_id(self) -> int | None:
        return self._current_node_id

    def _emit_edit_relation(self) -> None:
        relation_id = self.selected_relation_id()
        if relation_id is not None:
            self.editRelationRequested.emit(relation_id)

    def _emit_delete_relation(self) -> None:
        relation_id = self.selected_relation_id()
        if relation_id is not None:
            self.deleteRelationRequested.emit(relation_id)

    def _emit_delete_node(self) -> None:
        node_id = self.selected_node_id()
        if node_id is not None:
            self.deleteNodeRequested.emit(node_id)

    def _emit_focus_depth(self, depth: int) -> None:
        if self.selected_node_id() is not None:
            self.focusDepthRequested.emit(depth)

    def _sync_node_buttons(self) -> None:
        has_node = self.selected_node_id() is not None
        self.delete_node_button.setEnabled(has_node)
        self.focus_depth_input.setEnabled(has_node)
        self.full_view_button.setEnabled(True)

    def _sync_relation_buttons(self) -> None:
        has_relation = self.selected_relation_id() is not None
        self.edit_relation_button.setEnabled(has_relation)
        self.delete_relation_button.setEnabled(has_relation)


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


class Separator(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("separator")
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Plain)


def set_button_variant(button: QPushButton, variant: str) -> None:
    button.setProperty("variant", variant)
    button.setMinimumHeight(34)
