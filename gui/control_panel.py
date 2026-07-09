from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


NODE_LABEL_MODE_ITEMS = (
    ("폴더 이름만", "folders"),
    ("파일 이름만", "files"),
    ("둘 다", "all"),
    ("마우스가 올라가면 보이기", "hover"),
)

EDGE_LABEL_MODE_ITEMS = (
    ("항상 보이기", "always"),
    ("마우스가 올라가면 보이기", "hover"),
)


class ControlPanel(QWidget):
    addFileRequested = Signal()
    addFolderRequested = Signal()
    settingsRequested = Signal()
    searchRequested = Signal(str)
    searchTextChanged = Signal(str)
    searchSuggestionActivated = Signal(int)
    refreshRequested = Signal()
    checkFilesRequested = Signal()
    locateMissingRequested = Signal()
    sampleDataRequested = Signal()
    resetLayoutRequested = Signal()
    addRelationRequested = Signal()
    deleteNodeRequested = Signal(int)
    deleteSelectedNodesRequested = Signal()
    focusDepthRequested = Signal(int)
    fullViewRequested = Signal()
    editRelationRequested = Signal(int)
    deleteRelationRequested = Signal(int)
    graphFontSizeChanged = Signal(int)
    ignoredFoldersChanged = Signal(list)
    nodeLabelModeChanged = Signal(str)
    edgeLabelModeChanged = Signal(str)
    visualSettingsChanged = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self.setMinimumWidth(330)
        self.setMaximumWidth(460)
        self._current_node_id: int | None = None
        self._selected_node_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("FileGraph")
        title.setObjectName("panelTitle")
        self.settings_button = QPushButton("설정")
        set_button_variant(self.settings_button, "secondary")
        header.addWidget(title, 1)
        header.addWidget(self.settings_button)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.actions_tab = QWidget()
        self.settings_tab = QWidget()
        self.tabs.addTab(self.actions_tab, "작업")
        self.tabs.tabBar().hide()
        root.addWidget(self.tabs, 1)

        action_root = QVBoxLayout(self.actions_tab)
        action_root.setContentsMargins(0, 10, 0, 0)
        action_root.setSpacing(14)

        settings_root = QVBoxLayout(self.settings_tab)
        settings_root.setContentsMargins(0, 10, 0, 0)
        settings_root.setSpacing(14)

        import_actions = QGridLayout()
        import_actions.setHorizontalSpacing(8)
        import_actions.setVerticalSpacing(8)
        self.add_file_button = QPushButton("파일 추가")
        self.add_folder_button = QPushButton("폴더 추가")
        set_button_variant(self.add_file_button, "secondary")
        set_button_variant(self.add_folder_button, "secondary")
        import_actions.addWidget(self.add_file_button, 0, 0)
        import_actions.addWidget(self.add_folder_button, 0, 1)
        action_root.addLayout(import_actions)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("파일명, 경로, 카테고리 검색")
        self.search_input.setClearButtonEnabled(True)
        self.search_button = QPushButton("검색")
        self.full_view_button = QPushButton("전체 보기")
        set_button_variant(self.search_button, "secondary")
        set_button_variant(self.full_view_button, "segmented")
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button)
        search_row.addWidget(self.full_view_button)
        action_root.addLayout(search_row)
        self.search_suggestions = QListWidget()
        self.search_suggestions.setMaximumHeight(112)
        self.search_suggestions.setVisible(False)
        action_root.addWidget(self.search_suggestions)

        actions = QGridLayout()
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)
        self.refresh_button = QPushButton("새로고침")
        self.check_files_button = QPushButton("파일 위치 갱신")
        self.locate_missing_button = QPushButton("누락 파일 찾기")
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
        self.check_files_button.setToolTip(
            "등록한 파일/폴더의 현재 위치와 접근 가능 여부를 다시 확인하고 상태를 갱신합니다."
        )
        actions.addWidget(self.relation_button, 0, 0, 1, 2)
        actions.addWidget(self.refresh_button, 1, 0)
        actions.addWidget(self.check_files_button, 1, 1)
        actions.addWidget(self.sample_button, 2, 0)
        actions.addWidget(self.reset_button, 2, 1)
        actions.addWidget(self.locate_missing_button, 3, 0, 1, 2)
        action_root.addLayout(actions)

        self.selection_summary = QLabel("선택 노드 0개")
        self.selection_summary.setObjectName("metaText")
        action_root.addWidget(self.selection_summary)

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

        graph_section = Section("그래프 기본값")
        graph_section.body.addLayout(font_controls)
        self.node_label_mode_combo = labeled_combo("노드 라벨", NODE_LABEL_MODE_ITEMS)
        self.edge_label_mode_combo = labeled_combo("간선 라벨", EDGE_LABEL_MODE_ITEMS)
        set_combo_value(self.node_label_mode_combo.combo, "hover")
        set_combo_value(self.edge_label_mode_combo.combo, "hover")
        graph_section.body.addLayout(self.node_label_mode_combo.row)
        graph_section.body.addLayout(self.edge_label_mode_combo.row)
        settings_root.addWidget(graph_section)

        visual_section = Section("색상과 아이콘")
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self.file_node_color_input = QLineEdit()
        self.file_node_color_input.setPlaceholderText("#2563EB")
        self.folder_node_color_input = QLineEdit()
        self.folder_node_color_input.setPlaceholderText("#059669")
        color_row.addWidget(QLabel("파일"))
        color_row.addWidget(self.file_node_color_input)
        color_row.addWidget(QLabel("폴더"))
        color_row.addWidget(self.folder_node_color_input)
        self.highlight_colors_input = QLineEdit()
        self.highlight_colors_input.setPlaceholderText("#F97316, #EAB308, #22C55E, #06B6D4, #A855F7")
        self.extension_icon_overrides_input = QLineEdit()
        self.extension_icon_overrides_input.setPlaceholderText("log=doc, proto=code, bak=archive")
        visual_section.body.addLayout(color_row)
        visual_section.body.addWidget(self.highlight_colors_input)
        visual_section.body.addWidget(self.extension_icon_overrides_input)
        settings_root.addWidget(visual_section)

        ignore_section = Section("무시 폴더")
        self.ignored_folders_input = QLineEdit()
        self.ignored_folders_input.setPlaceholderText(".git, .venv, node_modules")
        ignore_section.body.addWidget(self.ignored_folders_input)
        settings_root.addWidget(ignore_section)

        self.apply_settings_button = QPushButton("설정 저장")
        set_button_variant(self.apply_settings_button, "primary")
        settings_root.addWidget(self.apply_settings_button)
        settings_root.addStretch(1)

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
        focus_actions.addWidget(self.focus_depth_input)
        self.focus_view_button = QPushButton("보기")
        set_button_variant(self.focus_view_button, "secondary")
        focus_actions.addWidget(self.focus_view_button)
        self.node_section.body.addLayout(focus_actions)
        node_actions = QHBoxLayout()
        self.delete_node_button = QPushButton("선택 노드 삭제")
        set_button_variant(self.delete_node_button, "danger")
        node_actions.addWidget(self.delete_node_button)
        self.node_section.body.addLayout(node_actions)
        action_root.addWidget(self.node_section)

        self.relation_section = Section("관계")
        self.relation_list = QListWidget()
        self.relation_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.relation_section.body.addWidget(self.relation_list)
        self.relation_action_hint = QLabel("관계를 선택하면 수정/삭제 대상이 표시됩니다.")
        self.relation_action_hint.setObjectName("metaText")
        self.relation_action_hint.setWordWrap(True)
        self.relation_section.body.addWidget(self.relation_action_hint)
        relation_actions = QHBoxLayout()
        relation_actions.setSpacing(8)
        self.edit_relation_button = QPushButton("선택 관계 수정")
        self.delete_relation_button = QPushButton("선택 관계 삭제")
        set_button_variant(self.edit_relation_button, "secondary")
        set_button_variant(self.delete_relation_button, "danger")
        relation_actions.addWidget(self.edit_relation_button)
        relation_actions.addWidget(self.delete_relation_button)
        self.relation_section.body.addLayout(relation_actions)
        action_root.addWidget(self.relation_section, 1)

        self.summary = QLabel("노드 0개 / 관계 0개")
        self.summary.setObjectName("summary")
        root.addWidget(self.summary)

        self.add_file_button.clicked.connect(self.addFileRequested.emit)
        self.add_folder_button.clicked.connect(self.addFolderRequested.emit)
        self.settings_button.clicked.connect(self.settingsRequested.emit)
        self.search_button.clicked.connect(self._emit_search)
        self.search_input.returnPressed.connect(self._emit_search)
        self.search_input.textChanged.connect(self.searchTextChanged.emit)
        self.search_suggestions.itemClicked.connect(self._emit_search_suggestion)
        self.search_suggestions.itemDoubleClicked.connect(self._emit_search_suggestion)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.check_files_button.clicked.connect(self.checkFilesRequested.emit)
        self.locate_missing_button.clicked.connect(self.locateMissingRequested.emit)
        self.relation_button.clicked.connect(self.addRelationRequested.emit)
        self.sample_button.clicked.connect(self.sampleDataRequested.emit)
        self.reset_button.clicked.connect(self.resetLayoutRequested.emit)
        self.font_size_input.valueChanged.connect(self.graphFontSizeChanged.emit)
        self.delete_node_button.clicked.connect(self._emit_delete_node)
        self.focus_depth_input.valueChanged.connect(self._emit_focus_depth)
        self.focus_view_button.clicked.connect(self._emit_current_focus_depth)
        self.full_view_button.clicked.connect(self.fullViewRequested.emit)
        self.edit_relation_button.clicked.connect(self._emit_edit_relation)
        self.delete_relation_button.clicked.connect(self._emit_delete_relation)
        self.relation_list.itemDoubleClicked.connect(lambda _item: self._emit_edit_relation())
        self.relation_list.itemSelectionChanged.connect(self._sync_relation_buttons)
        self.apply_settings_button.clicked.connect(self._emit_settings)
        self._sync_node_buttons()
        self._sync_relation_buttons()

    def set_summary(self, node_count: int, relation_count: int) -> None:
        self.summary.setText(f"노드 {node_count}개 / 관계 {relation_count}개")

    def set_graph_font_size(self, point_size: int) -> None:
        self.font_size_input.blockSignals(True)
        self.font_size_input.setValue(point_size)
        self.font_size_input.blockSignals(False)

    def set_settings(
        self,
        *,
        ignored_dir_names: list[str],
        node_label_mode: str,
        edge_label_mode: str,
        visual_settings: dict[str, Any] | None = None,
    ) -> None:
        self.ignored_folders_input.setText(", ".join(ignored_dir_names))
        set_combo_value(self.node_label_mode_combo.combo, node_label_mode)
        set_combo_value(self.edge_label_mode_combo.combo, edge_label_mode)
        self.set_visual_settings(visual_settings or {})

    def set_selected_node_count(self, count: int) -> None:
        self._selected_node_count = max(0, int(count))
        self.selection_summary.setText(f"선택 노드 {self._selected_node_count}개")
        self._sync_node_buttons()

    def set_search_suggestions(self, nodes: list[dict[str, Any]]) -> None:
        self.search_suggestions.clear()
        for node in nodes:
            item = QListWidgetItem(search_suggestion_label(node))
            item.setData(Qt.UserRole, int(node["node_id"]))
            item.setToolTip(node.get("path", ""))
            self.search_suggestions.addItem(item)
        self.search_suggestions.setVisible(bool(nodes))

    def set_visual_settings(self, settings: dict[str, Any]) -> None:
        node_colors = settings.get("node_type_colors") or {}
        self.file_node_color_input.setText(str(node_colors.get("FILE", "")))
        self.folder_node_color_input.setText(str(node_colors.get("FOLDER", "")))
        self.highlight_colors_input.setText(", ".join(settings.get("highlight_color_slots") or []))
        self.extension_icon_overrides_input.setText(
            format_extension_icon_overrides(settings.get("extension_icon_overrides") or {})
        )

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
        self.node_meta.setText(node_detail_text(node))
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
            item = QListWidgetItem(relation_list_label(relation))
            item.setData(Qt.UserRole, relation.get("relation_id"))
            item.setToolTip(relation_tooltip(relation))
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

    def search_text(self) -> str:
        return self.search_input.text().strip()

    def clear_search(self) -> None:
        self.search_input.clear()
        self.set_search_suggestions([])

    def _emit_search(self) -> None:
        self.searchRequested.emit(self.search_text())

    def _emit_search_suggestion(self, item: QListWidgetItem) -> None:
        node_id = item.data(Qt.UserRole)
        if node_id is not None:
            self.searchSuggestionActivated.emit(int(node_id))

    def _emit_edit_relation(self) -> None:
        relation_id = self.selected_relation_id()
        if relation_id is not None:
            self.editRelationRequested.emit(relation_id)

    def _emit_delete_relation(self) -> None:
        relation_id = self.selected_relation_id()
        if relation_id is not None:
            self.deleteRelationRequested.emit(relation_id)

    def _emit_delete_node(self) -> None:
        if self._selected_node_count > 1 or (self._selected_node_count == 1 and self.selected_node_id() is None):
            self.deleteSelectedNodesRequested.emit()
            return

        node_id = self.selected_node_id()
        if node_id is not None:
            self.deleteNodeRequested.emit(node_id)

    def _emit_focus_depth(self, depth: int) -> None:
        if self.selected_node_id() is not None:
            self.focusDepthRequested.emit(depth)

    def _emit_current_focus_depth(self) -> None:
        self._emit_focus_depth(self.focus_depth_input.value())

    def _emit_settings(self) -> None:
        ignored_dir_names = parse_ignored_dir_names(self.ignored_folders_input.text())
        node_label_mode = self.node_label_mode_combo.combo.currentData()
        edge_label_mode = self.edge_label_mode_combo.combo.currentData()
        visual_settings = {
            "node_type_colors": {
                "FILE": self.file_node_color_input.text().strip(),
                "FOLDER": self.folder_node_color_input.text().strip(),
            },
            "highlight_color_slots": parse_csv_values(self.highlight_colors_input.text()),
            "extension_icon_overrides": parse_extension_icon_overrides(
                self.extension_icon_overrides_input.text()
            ),
        }

        self.nodeLabelModeChanged.emit(node_label_mode)
        self.edgeLabelModeChanged.emit(edge_label_mode)
        self.ignoredFoldersChanged.emit(ignored_dir_names)
        self.visualSettingsChanged.emit(visual_settings)

    def _sync_node_buttons(self) -> None:
        has_node = self.selected_node_id() is not None
        has_selection = self._selected_node_count > 0
        self.delete_node_button.setEnabled(has_node or has_selection)
        self.focus_depth_input.setEnabled(has_node)
        self.focus_view_button.setEnabled(has_node)
        self.full_view_button.setEnabled(True)
        if self._selected_node_count > 1:
            self.delete_node_button.setText(f"선택 노드 {self._selected_node_count}개 삭제")
        else:
            self.delete_node_button.setText("선택 노드 삭제")

    def _sync_relation_buttons(self) -> None:
        relation_id = self.selected_relation_id()
        has_relation = relation_id is not None
        self.edit_relation_button.setEnabled(has_relation)
        self.delete_relation_button.setEnabled(has_relation)
        if has_relation:
            self.relation_action_hint.setText(f"수정/삭제 대상: 관계 #{relation_id}")
        else:
            self.relation_action_hint.setText("관계를 선택하면 수정/삭제 대상이 표시됩니다.")


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


class LabeledCombo:
    def __init__(self, row: QHBoxLayout, combo: QComboBox) -> None:
        self.row = row
        self.combo = combo


def labeled_combo(label_text: str, items: tuple[tuple[str, str], ...]) -> LabeledCombo:
    row = QHBoxLayout()
    row.setSpacing(8)
    label = QLabel(label_text)
    label.setObjectName("fieldLabel")
    combo = QComboBox()
    for text, value in items:
        combo.addItem(text, value)
    row.addWidget(label)
    row.addWidget(combo)
    return LabeledCombo(row, combo)


def set_combo_value(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index < 0 and value == "always":
        index = combo.findData("all")
    combo.setCurrentIndex(index if index >= 0 else 0)


def parse_ignored_dir_names(value: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for chunk in value.replace("\n", ",").split(","):
        name = chunk.strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return names


def parse_csv_values(value: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for chunk in value.replace("\n", ",").split(","):
        item = chunk.strip()
        if not item or item in seen:
            continue
        values.append(item)
        seen.add(item)
    return values


def parse_extension_icon_overrides(value: str) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for chunk in value.replace("\n", ",").split(","):
        if "=" not in chunk:
            continue
        extension, icon_name = chunk.split("=", 1)
        extension_key = extension.strip().lower().removeprefix(".")
        icon_key = icon_name.strip().lower()
        if extension_key and icon_key:
            overrides[extension_key] = icon_key
    return overrides


def format_extension_icon_overrides(overrides: dict[str, str]) -> str:
    return ", ".join(
        f"{extension}={icon_name}"
        for extension, icon_name in sorted(overrides.items())
    )


def search_suggestion_label(node: dict[str, Any]) -> str:
    name = node.get("name", "")
    path = node.get("path", "")
    return f"{name}\n{path}" if path else str(name)


def node_detail_text(node: dict[str, Any]) -> str:
    parts = [
        str(node.get("node_type", "")),
        str(node.get("status", "")),
    ]
    if node.get("highlight_color"):
        parts.append(f"강조 {node.get('highlight_color')}")
    note = str(node.get("note") or "").strip().splitlines()
    if note:
        summary = note[0][:48]
        parts.append(f"메모 {summary}")
    return " · ".join(part for part in parts if part)


def relation_list_label(relation: dict[str, Any]) -> str:
    direction = "->" if relation.get("is_directional") else "--"
    return (
        f"출발: {relation.get('source_name', '')}\n"
        f"도착: {relation.get('target_name', '')}\n"
        f"유형: {relation.get('relation_type_name', '')}  방향: {direction}  강도: {relation.get('strength', '')}"
    )


def relation_tooltip(relation: dict[str, Any]) -> str:
    direction_label = "방향 있음" if relation.get("is_directional") else "방향 없음"
    return (
        f"{relation.get('source_name', '')} -> {relation.get('target_name', '')}\n"
        f"{relation.get('relation_type_name', '')} / {direction_label} / {relation.get('strength', '')}"
    )


def set_button_variant(button: QPushButton, variant: str) -> None:
    button.setProperty("variant", variant)
    button.setMinimumHeight(34)
