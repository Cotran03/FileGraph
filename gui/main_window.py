from __future__ import annotations

import os
import csv
from datetime import datetime
import json
import random
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QPoint, QThread, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QSplitter,
)

from core.database_manager import DatabaseManager, DuplicateNodeError, DuplicateRelationError
from core.file_integrity import (
    IntegrityScanResult,
    RediscoveryResult,
    rediscover_missing_nodes,
    scan_file_statuses as scan_database_file_statuses,
)
from core.graph_manager import GraphManager
from core.relationship_detection import analyze_registered_files
from gui.control_panel import ControlPanel
from gui.graph_viewer import (
    DEFAULT_LABEL_FONT_SIZE,
    GraphViewer,
    clamp_label_font_size,
    normalize_edge_label_visibility_mode,
    normalize_extension_icon_overrides,
    normalize_node_label_visibility_mode,
)
from gui.relation_dialog import RelationDialog
from gui.settings_dialog import SettingsDialog


DEFAULT_IGNORED_DIR_NAMES = (
    ".git",
    ".venv",
    "venv",
    "ENV",
    "node_modules",
    "__pycache__",
)
SKIPPED_RECURSIVE_DIR_NAMES = set(DEFAULT_IGNORED_DIR_NAMES)

DUPLICATE_NODE_FOCUS = "focus"
DUPLICATE_NODE_RELATION = "relation"
DUPLICATE_NODE_CANCEL = "cancel"
GRAPH_LABEL_FONT_SIZE_SETTING = "graph_label_font_size"
NODE_LABEL_MODE_SETTING = "graph_node_label_mode"
NODE_LABEL_MODE_USER_SET_SETTING = "graph_node_label_mode_user_set"
EDGE_LABEL_MODE_SETTING = "graph_edge_label_mode"
IGNORED_DIR_NAMES_SETTING = "ignored_dir_names"
EXTENSION_ICON_OVERRIDES_SETTING = "extension_icon_overrides"
NODE_TYPE_COLORS_SETTING = "node_type_colors"
HIGHLIGHT_COLOR_SLOTS_SETTING = "highlight_color_slots"
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
SEARCH_LAYOUT_SCALE = 420.0
BACKGROUND_IMPORT_THRESHOLD = 500
MAX_LAYOUT_SEED = 2_147_483_647
NODE_CONTEXT_ADD_RELATION = "node_context_add_relation"
NODE_CONTEXT_EDIT_RELATIONS = "node_context_edit_relations"
NODE_CONTEXT_DELETE_NODE = "node_context_delete_node"
NODE_CONTEXT_TOGGLE_CONTAINS = "node_context_toggle_contains"
NODE_CONTEXT_OPEN_NODE = "node_context_open_node"
NODE_CONTEXT_EDIT_NOTE = "node_context_edit_note"
NODE_CONTEXT_HIGHLIGHT_NODE = "node_context_highlight_node"
NODE_CONTEXT_CLEAR_HIGHLIGHT = "node_context_clear_highlight"
VIEW_PRESET_ALL = "all"
VIEW_PRESET_MISSING = "missing"
VIEW_PRESET_HIGHLIGHTED = "highlighted"
VIEW_PRESET_RECENT = "recent"
VIEW_PRESET_FOLDER = "folder"
VIEW_PRESET_ORPHAN = "orphan"
RECENT_VIEW_NODE_LIMIT = 30


@dataclass(frozen=True)
class ImportPlan:
    entries: list[tuple[str, str]]
    contains_pairs: list[tuple[str, str]]


class ImportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, db_path: str | os.PathLike[str], import_plan: ImportPlan, action_label: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.import_plan = import_plan
        self.action_label = action_label
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        database = DatabaseManager(self.db_path)
        try:
            database.init_db()
            result = execute_import_plan(
                database,
                self.import_plan,
                progress_callback=self.report_progress,
                should_cancel=lambda: self._cancel_requested,
            )
            result["action_label"] = self.action_label
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - depends on filesystem/database state.
            self.failed.emit(str(exc))
        finally:
            database.close()

    def report_progress(self, completed: int, total: int, label: str) -> bool:
        self.progress.emit(completed, total, label)
        return not self._cancel_requested


class MainWindow(QMainWindow):
    def __init__(self, db_path: str | os.PathLike[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FileGraph")
        self.resize(1280, 820)

        self.database = DatabaseManager(db_path)
        self.database.init_db()
        self.graph_manager = GraphManager(self.database)
        self.selected_node: dict[str, Any] | None = None
        self.collapsed_folder_node_ids: set[int] = set()
        self.current_graph_data: dict[str, list[dict[str, Any]]] = {"nodes": [], "relations": []}
        self.graph_font_size = self._load_graph_font_size()
        self.node_label_mode = self._load_node_label_mode()
        self.edge_label_mode = self._load_edge_label_mode()
        self.ignored_dir_names = self._load_ignored_dir_names()
        self.extension_icon_overrides = self._load_json_setting(EXTENSION_ICON_OVERRIDES_SETTING, {})
        self.node_type_colors = self._load_node_type_colors()
        self.highlight_color_slots = self._load_highlight_color_slots()
        self.undo_stack: list[dict[str, Any]] = []
        self.import_worker_thread: QThread | None = None
        self.import_worker: ImportWorker | None = None
        self.import_progress_dialog: QProgressDialog | None = None

        self.graph_viewer = GraphViewer()
        self.graph_viewer.set_label_font_size(self.graph_font_size)
        self.graph_viewer.set_label_visibility_modes(
            node_mode=self.node_label_mode,
            edge_mode=self.edge_label_mode,
        )
        self.graph_viewer.set_extension_icon_overrides(self.extension_icon_overrides)
        self.control_panel = ControlPanel()
        self.search_input = self.control_panel.search_input

        self._build_layout()
        self._connect_signals()
        self._connect_shortcuts()
        self._apply_style()

        self.reload_graph()

    def closeEvent(self, event) -> None:
        self.database.close()
        super().closeEvent(event)

    def _load_graph_font_size(self) -> int:
        value = self.database.get_setting(
            GRAPH_LABEL_FONT_SIZE_SETTING,
            str(DEFAULT_LABEL_FONT_SIZE),
        )
        try:
            return clamp_label_font_size(int(value or DEFAULT_LABEL_FONT_SIZE))
        except ValueError:
            return DEFAULT_LABEL_FONT_SIZE

    def _load_node_label_mode(self) -> str:
        raw_value = self.database.get_setting(NODE_LABEL_MODE_SETTING, "hover") or "hover"
        mode = normalize_node_label_visibility_mode(raw_value)
        user_set = self._load_bool_setting(NODE_LABEL_MODE_USER_SET_SETTING, default=False)
        if not user_set and mode in {"folders", "files"}:
            return "hover"
        return mode

    def _load_edge_label_mode(self) -> str:
        return normalize_edge_label_visibility_mode(self.database.get_setting(EDGE_LABEL_MODE_SETTING, "hover") or "hover")

    def _load_ignored_dir_names(self) -> set[str]:
        value = self.database.get_setting(IGNORED_DIR_NAMES_SETTING)
        if value is None:
            return set(DEFAULT_IGNORED_DIR_NAMES)
        parsed = normalize_ignored_dir_names(value.split(","))
        return parsed or set(DEFAULT_IGNORED_DIR_NAMES)

    def _load_json_setting(self, setting_key: str, default: Any) -> Any:
        value = self.database.get_setting(setting_key)
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _load_node_type_colors(self) -> dict[str, str]:
        saved = self._load_json_setting(NODE_TYPE_COLORS_SETTING, {})
        colors = dict(DEFAULT_NODE_TYPE_COLORS)
        if isinstance(saved, dict):
            for node_type, color in saved.items():
                node_type_key = str(node_type).upper()
                color_value = str(color).strip()
                if node_type_key in colors and is_valid_color(color_value):
                    colors[node_type_key] = color_value
        return colors

    def _load_highlight_color_slots(self) -> list[str]:
        saved = self._load_json_setting(HIGHLIGHT_COLOR_SLOTS_SETTING, [])
        colors = [str(color).strip() for color in saved if is_valid_color(str(color).strip())] if isinstance(saved, list) else []
        return (colors or list(DEFAULT_HIGHLIGHT_COLOR_SLOTS))[:5]

    def _load_bool_setting(self, setting_key: str, *, default: bool) -> bool:
        value = self.database.get_setting(setting_key, "1" if default else "0")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def visual_settings(self) -> dict[str, Any]:
        return {
            "extension_icon_overrides": self.extension_icon_overrides,
            "node_type_colors": self.node_type_colors,
            "highlight_color_slots": self.highlight_color_slots,
        }

    def set_graph_font_size(self, point_size: int) -> None:
        self.graph_font_size = clamp_label_font_size(point_size)
        self.graph_viewer.set_label_font_size(self.graph_font_size)
        self.database.set_setting(GRAPH_LABEL_FONT_SIZE_SETTING, str(self.graph_font_size))
        self.statusBar().showMessage(f"그래프 글자 크기 {self.graph_font_size}pt", 1200)

    def set_node_label_mode(self, mode: str) -> None:
        self.node_label_mode = normalize_node_label_visibility_mode(mode)
        self.graph_viewer.set_label_visibility_modes(node_mode=self.node_label_mode)
        self.database.set_setting(NODE_LABEL_MODE_SETTING, self.node_label_mode)
        self.database.set_setting(NODE_LABEL_MODE_USER_SET_SETTING, "1")
        self.statusBar().showMessage("노드 라벨 표시 방식을 저장했습니다.", 1500)

    def set_edge_label_mode(self, mode: str) -> None:
        self.edge_label_mode = normalize_edge_label_visibility_mode(mode)
        self.graph_viewer.set_label_visibility_modes(edge_mode=self.edge_label_mode)
        self.database.set_setting(EDGE_LABEL_MODE_SETTING, self.edge_label_mode)
        self.statusBar().showMessage("간선 라벨 표시 방식을 저장했습니다.", 1500)

    def set_ignored_dir_names(self, ignored_dir_names: list[str]) -> None:
        self.ignored_dir_names = normalize_ignored_dir_names(ignored_dir_names) or set(DEFAULT_IGNORED_DIR_NAMES)
        self.database.set_setting(IGNORED_DIR_NAMES_SETTING, ",".join(sorted(self.ignored_dir_names)))
        self.statusBar().showMessage("무시 폴더 목록을 저장했습니다.", 1500)

    def set_visual_settings(self, settings: dict[str, Any]) -> None:
        node_colors = settings.get("node_type_colors") or {}
        updated_node_colors = dict(DEFAULT_NODE_TYPE_COLORS)
        for node_type, color in node_colors.items():
            node_type_key = str(node_type).upper()
            color_value = str(color).strip()
            if node_type_key in updated_node_colors and is_valid_color(color_value):
                updated_node_colors[node_type_key] = color_value

        highlight_slots = [
            str(color).strip()
            for color in settings.get("highlight_color_slots", [])
            if is_valid_color(str(color).strip())
        ][:5]

        icon_overrides = self.extension_icon_overrides
        if "extension_icon_overrides" in settings:
            icon_overrides = normalize_extension_icon_overrides(settings.get("extension_icon_overrides") or {})

        self.node_type_colors = updated_node_colors
        self.highlight_color_slots = highlight_slots or list(DEFAULT_HIGHLIGHT_COLOR_SLOTS)
        self.extension_icon_overrides = icon_overrides
        self.graph_viewer.set_extension_icon_overrides(self.extension_icon_overrides)
        self.database.set_setting(NODE_TYPE_COLORS_SETTING, json.dumps(self.node_type_colors, ensure_ascii=False))
        self.database.set_setting(HIGHLIGHT_COLOR_SLOTS_SETTING, json.dumps(self.highlight_color_slots, ensure_ascii=False))
        self.database.set_setting(
            EXTENSION_ICON_OVERRIDES_SETTING,
            json.dumps(self.extension_icon_overrides, ensure_ascii=False),
        )
        self.reload_graph()
        self.statusBar().showMessage("색상과 아이콘 설정을 저장했습니다.", 1500)

    def settings_dialog_payload(self) -> dict[str, Any]:
        return {
            "graph_font_size": self.graph_font_size,
            "node_label_mode": self.node_label_mode,
            "edge_label_mode": self.edge_label_mode,
            "ignored_dir_names": sorted(self.ignored_dir_names),
            **self.visual_settings(),
        }

    def show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings_dialog_payload(), self)
        if dialog.exec() != QDialog.Accepted:
            return

        values = dialog.values()
        self.set_graph_font_size(values["graph_font_size"])
        self.set_node_label_mode(values["node_label_mode"])
        self.set_edge_label_mode(values["edge_label_mode"])
        self.set_ignored_dir_names(values["ignored_dir_names"])
        self.set_visual_settings(values["visual_settings"])
        self.statusBar().showMessage("설정을 저장했습니다.", 1800)

    def next_layout_seed(self) -> int:
        # Layout seed is not security-sensitive.
        return random.randint(1, MAX_LAYOUT_SEED)  # nosec B311

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.graph_viewer)
        splitter.addWidget(self.control_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    def _connect_signals(self) -> None:
        self.graph_viewer.nodeSelected.connect(self.on_node_selected)
        self.graph_viewer.nodeActivated.connect(self.open_node)
        self.graph_viewer.nodeContextMenuRequested.connect(self.show_node_context_menu)
        self.graph_viewer.nodeMoved.connect(self.on_node_moved)
        self.graph_viewer.pathsDropped.connect(self.add_dropped_paths)
        self.graph_viewer.selectedNodesChanged.connect(self.on_selected_nodes_changed)
        self.control_panel.addFileRequested.connect(self.add_file_node)
        self.control_panel.addFolderRequested.connect(self.add_folder_node)
        self.control_panel.settingsRequested.connect(self.show_settings_dialog)
        self.control_panel.searchRequested.connect(self.search_nodes)
        self.control_panel.searchTextChanged.connect(self.update_search_suggestions)
        self.control_panel.searchSuggestionActivated.connect(self.focus_search_suggestion)
        self.control_panel.refreshRequested.connect(self.reload_graph)
        self.control_panel.checkFilesRequested.connect(self.refresh_file_statuses)
        self.control_panel.locateMissingRequested.connect(self.locate_missing_files)
        self.control_panel.importDatabaseRequested.connect(self.import_database_file)
        self.control_panel.exportJsonRequested.connect(self.export_graph_json)
        self.control_panel.exportCsvRequested.connect(self.export_graph_csv)
        self.control_panel.addRelationRequested.connect(self.add_relation)
        self.control_panel.deleteNodeRequested.connect(self.delete_node_or_selection)
        self.control_panel.deleteSelectedNodesRequested.connect(self.delete_selected_nodes_from_panel)
        self.control_panel.focusDepthRequested.connect(self.show_focus_graph)
        self.control_panel.fullViewRequested.connect(self.show_full_graph)
        self.control_panel.viewPresetRequested.connect(self.apply_view_preset)
        self.control_panel.editRelationRequested.connect(self.edit_relation)
        self.control_panel.deleteRelationRequested.connect(self.delete_relation)
        self.control_panel.resetLayoutRequested.connect(self.reset_layout)
        self.control_panel.analyzeRelationshipsRequested.connect(self.analyze_relationship_candidates)
        self.control_panel.approveCandidateRequested.connect(self.approve_relationship_candidate)
        self.control_panel.rejectCandidateRequested.connect(self.reject_relationship_candidate)
        self.control_panel.impactViewRequested.connect(self.show_impact_view)

    def _connect_shortcuts(self) -> None:
        self.shortcuts: list[QShortcut] = []
        shortcut_map = {
            "Ctrl+F": self.focus_search_input,
            "Esc": self.clear_search_or_selection,
            "Delete": self.delete_selected_nodes_from_panel,
            "Return": self.open_selected_node,
            "Enter": self.open_selected_node,
            "Ctrl+L": self.reset_layout,
            "Ctrl+R": self.reload_graph,
            "Ctrl+Shift+R": self.refresh_file_statuses,
            "F": lambda: self.show_focus_graph(self.control_panel.focus_depth_input.value()),
            "Shift+F": self.show_full_graph,
            "Ctrl+N": self.add_file_node,
            "Ctrl+Shift+N": self.add_folder_node,
            "Ctrl+Z": self.undo_last_action,
            "F1": self.show_shortcut_help,
            "Ctrl+Shift+L": self.show_legend,
            "Ctrl+Shift+O": self.show_orphan_nodes,
            "Ctrl+Shift+D": self.show_duplicate_candidates,
            "Ctrl+Shift+B": self.backup_database_file,
            "Ctrl+Shift+I": self.import_database_file,
            "Ctrl+Shift+E": self.export_graph_json,
            "Ctrl+Shift+C": self.export_graph_csv,
        }
        for sequence, callback in shortcut_map.items():
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def show_full_graph(self) -> None:
        self.control_panel.clear_search()
        self.reload_graph()
        self.statusBar().showMessage("전체 그래프를 표시합니다.", 2500)

    def apply_view_preset(self, preset: str) -> None:
        preset = str(preset or VIEW_PRESET_ALL)
        if preset == VIEW_PRESET_ALL:
            self.show_full_graph()
            return
        if preset == VIEW_PRESET_MISSING:
            nodes = [
                node
                for node in self.database.list_nodes()
                if str(node.get("status") or "").upper() == "MISSING"
            ]
            self.render_node_subset_view(
                nodes,
                title="누락 파일만",
                empty_message="누락 상태의 노드가 없습니다.",
            )
            return
        if preset == VIEW_PRESET_HIGHLIGHTED:
            nodes, relations = self.highlighted_neighborhood()
            self.render_node_subset_view(
                nodes,
                relations=relations,
                title="강조 노드 주변",
                empty_message="강조 색상이 지정된 노드가 없습니다.",
            )
            return
        if preset == VIEW_PRESET_RECENT:
            nodes = sorted(
                self.database.list_nodes(),
                key=lambda node: str(node.get("created_at") or ""),
                reverse=True,
            )[:RECENT_VIEW_NODE_LIMIT]
            self.render_node_subset_view(
                nodes,
                title="최근 추가",
                empty_message="최근 추가한 노드가 없습니다.",
            )
            return
        if preset == VIEW_PRESET_FOLDER:
            self.show_selected_folder_subtree()
            return
        if preset == VIEW_PRESET_ORPHAN:
            self.show_orphan_nodes()
            return
        self.statusBar().showMessage("알 수 없는 보기 프리셋입니다.", 1800)

    def render_node_subset_view(
        self,
        nodes: list[dict[str, Any]],
        *,
        title: str,
        empty_message: str,
        relations: list[dict[str, Any]] | None = None,
    ) -> None:
        if not nodes:
            data = self.graph_manager.get_graph_data(nodes=[], relations=[], use_saved_layout=False)
            data = self.prepare_graph_data(data)
            self.current_graph_data = data
            self.graph_viewer.render_graph(data)
            self.control_panel.set_selected_node_count(0)
            self.control_panel.set_summary(0, 0)
            self.selected_node = None
            self.control_panel.show_node(None)
            self.control_panel.show_relations([])
            self.statusBar().showMessage(empty_message, 2500)
            return

        node_ids = {int(node["node_id"]) for node in nodes}
        visible_relations = relations if relations is not None else self.relations_between_node_ids(node_ids)
        data = self.graph_manager.get_graph_data(
            nodes=nodes,
            relations=visible_relations,
            scale=SEARCH_LAYOUT_SCALE,
            use_saved_layout=False,
        )
        data = self.prepare_graph_data(data)
        self.current_graph_data = data
        self.graph_viewer.render_graph(data)
        self.control_panel.set_selected_node_count(len(self.graph_viewer.selected_node_ids()))
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        if self.selected_node and int(self.selected_node["node_id"]) in node_ids:
            refreshed = self.database.get_node(int(self.selected_node["node_id"]))
            self.selected_node = refreshed
            self.control_panel.show_node(refreshed)
            if refreshed:
                self.control_panel.show_relations(relations_for_node_in_graph_data(data, refreshed["node_id"]))
            else:
                self.control_panel.show_relations(data["relations"])
        else:
            self.selected_node = None
            self.control_panel.show_node(None)
            self.control_panel.show_relations(data["relations"])
        self.statusBar().showMessage(f"{title}: 노드 {len(data['nodes'])}개, 관계 {len(data['relations'])}개", 2500)

    def relations_between_node_ids(self, node_ids: set[int]) -> list[dict[str, Any]]:
        return [
            relation
            for relation in self.database.list_relations()
            if int(relation["source_id"]) in node_ids
            and int(relation["target_id"]) in node_ids
        ]

    def highlighted_neighborhood(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        all_nodes = self.database.list_nodes()
        nodes_by_id = {int(node["node_id"]): node for node in all_nodes}
        highlighted_ids = {
            int(node["node_id"])
            for node in all_nodes
            if str(node.get("highlight_color") or "").strip()
        }
        if not highlighted_ids:
            return [], []

        visible_ids = set(highlighted_ids)
        visible_relations: list[dict[str, Any]] = []
        for relation in self.database.list_relations():
            source_id = int(relation["source_id"])
            target_id = int(relation["target_id"])
            if source_id in highlighted_ids or target_id in highlighted_ids:
                visible_ids.add(source_id)
                visible_ids.add(target_id)
                visible_relations.append(relation)

        return [nodes_by_id[node_id] for node_id in visible_ids if node_id in nodes_by_id], visible_relations

    def show_selected_folder_subtree(self) -> None:
        if not self.selected_node or self.selected_node.get("node_type") != "FOLDER":
            QMessageBox.information(self, "선택 폴더 아래", "먼저 폴더 노드를 선택해 주세요.")
            return

        folder_id = int(self.selected_node["node_id"])
        visible_ids = self.folder_subtree_node_ids(folder_id)
        nodes_by_id = {int(node["node_id"]): node for node in self.database.list_nodes()}
        nodes = [nodes_by_id[node_id] for node_id in visible_ids if node_id in nodes_by_id]
        self.render_node_subset_view(
            nodes,
            title="선택 폴더 아래",
            empty_message="선택한 폴더 아래에 표시할 노드가 없습니다.",
        )
        if folder_id in self.graph_viewer.node_items:
            self.graph_viewer.focus_node(folder_id)

    def folder_subtree_node_ids(self, folder_id: int) -> set[int]:
        children_by_folder: dict[int, set[int]] = {}
        for relation in self.database.list_relations():
            if relation.get("relation_type_code") != "CONTAINS":
                continue
            children_by_folder.setdefault(int(relation["source_id"]), set()).add(int(relation["target_id"]))

        visible_ids = {folder_id}
        pending = list(children_by_folder.get(folder_id, set()))
        while pending:
            node_id = pending.pop()
            if node_id in visible_ids:
                continue
            visible_ids.add(node_id)
            pending.extend(children_by_folder.get(node_id, set()))
        return visible_ids

    def focus_search_input(self) -> None:
        self.search_input.setFocus(Qt.ShortcutFocusReason)
        self.search_input.selectAll()

    def clear_search_or_selection(self) -> None:
        if self.control_panel.search_text():
            self.control_panel.clear_search()
            self.reload_graph()
            return
        self.graph_viewer.scene.clearSelection()
        self.selected_node = None
        self.control_panel.show_node(None)
        self.control_panel.set_selected_node_count(0)

    def open_selected_node(self) -> None:
        node = self.selected_node
        selected_ids = self.graph_viewer.selected_node_ids()
        if selected_ids:
            node = self.database.get_node(selected_ids[0])
        if node is not None:
            self.open_node(node)

    def show_shortcut_help(self) -> None:
        QMessageBox.information(
            self,
            "단축키",
            "\n".join(
                [
                    "Ctrl+F: 검색창으로 이동",
                    "Esc: 검색/선택 해제",
                    "Delete: 선택 노드 삭제",
                    "Enter: 선택 노드 열기",
                    "Ctrl+L: 자동 정렬",
                    "Ctrl+R: 그래프 새로고침",
                    "Ctrl+Shift+R: 파일 위치 갱신",
                    "F: 선택 노드 포커스 보기",
                    "Shift+F: 전체 보기",
                    "Ctrl+N: 파일 추가",
                    "Ctrl+Shift+N: 폴더 추가",
                    "Ctrl+Z: 되돌리기",
                    "Ctrl+Shift+L: 범례 보기",
                    "Ctrl+Shift+O: 고립 노드 보기",
                    "Ctrl+Shift+D: 중복 후보 보기",
                    "Ctrl+Shift+B: DB 백업",
                    "Ctrl+Shift+I: DB 가져오기",
                    "Ctrl+Shift+E: JSON 내보내기",
                    "Ctrl+Shift+C: CSV 내보내기",
                ]
            ),
        )

    def show_legend(self) -> None:
        QMessageBox.information(
            self,
            "범례",
            "\n".join(
                [
                    "회색: 누락 파일",
                    "빨강: 접근 거부",
                    "초록 점선: 접힌 폴더",
                    "주황 테두리: 상위 폴더가 없는 루트 폴더",
                    "파랑: 파일",
                    "초록: 폴더",
                    "간선 색상: 관계 타입 색상",
                    "노드 우상단 점: 메모 있음",
                ]
            ),
        )

    def show_orphan_nodes(self) -> None:
        nodes = self.database.list_orphan_nodes()
        data = self.graph_manager.get_graph_data(
            nodes=nodes,
            relations=[],
            scale=SEARCH_LAYOUT_SCALE,
            use_saved_layout=False,
        )
        data = self.prepare_graph_data(data)
        self.current_graph_data = data
        self.graph_viewer.render_graph(data)
        self.control_panel.set_summary(len(data["nodes"]), 0)
        self.control_panel.show_node(None)
        self.control_panel.show_relations([])
        self.statusBar().showMessage(f"고립 노드 {len(nodes)}개를 표시합니다.", 2500)

    def show_duplicate_candidates(self) -> None:
        groups = self.database.list_duplicate_candidate_groups()
        if not groups:
            QMessageBox.information(self, "중복 후보", "중복 후보가 없습니다.")
            return
        lines = []
        for group in groups[:20]:
            nodes = group.get("nodes", [])
            names = ", ".join(str(node.get("name", "")) for node in nodes[:4])
            if len(nodes) > 4:
                names += f" 외 {len(nodes) - 4}개"
            lines.append(f"{group.get('kind')} · {group.get('value')} · {len(nodes)}개: {names}")
        QMessageBox.information(self, "중복 후보", "\n".join(lines))

    def backup_database_file(self) -> None:
        if str(self.database.db_path) == ":memory:":
            QMessageBox.information(self, "DB 백업", "메모리 DB는 백업할 수 없습니다.")
            return
        default_path = Path(self.database.db_path).with_suffix(".backup.db")
        target_path, _filter = QFileDialog.getSaveFileName(self, "DB 백업", str(default_path), "SQLite DB (*.db)")
        if not target_path:
            return
        self.database.conn.commit()
        shutil.copy2(self.database.db_path, target_path)
        self.statusBar().showMessage(f"DB를 백업했습니다: {target_path}", 3500)

    def import_database_file(self) -> None:
        if str(self.database.db_path) == ":memory:":
            QMessageBox.information(self, "DB 가져오기", "메모리 DB는 가져오기로 교체할 수 없습니다.")
            return

        source_path, _filter = QFileDialog.getOpenFileName(
            self,
            "DB 가져오기",
            "",
            "SQLite DB (*.db *.sqlite *.sqlite3)",
        )
        if not source_path:
            return

        source = Path(source_path)
        is_valid, message = validate_filegraph_database(source)
        if not is_valid:
            QMessageBox.warning(self, "DB 가져오기 실패", message)
            return

        target = Path(self.database.db_path)
        if source.resolve(strict=False) == target.resolve(strict=False):
            QMessageBox.information(self, "DB 가져오기", "현재 사용 중인 DB와 같은 파일입니다.")
            return

        answer = QMessageBox.question(
            self,
            "DB 가져오기",
            (
                "현재 DB를 선택한 DB로 교체할까요?\n"
                "교체 전에 현재 DB는 같은 폴더에 자동 백업됩니다."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            backup_path = self.replace_database_file(source)
        except OSError as exc:
            QMessageBox.warning(self, "DB 가져오기 실패", str(exc))
            return

        self.statusBar().showMessage(f"DB를 가져왔습니다. 이전 DB 백업: {backup_path}", 5000)

    def replace_database_file(self, source_path: str | os.PathLike[str]) -> Path:
        source = Path(source_path)
        target = Path(self.database.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.database.conn.commit()
        backup_path = database_preimport_backup_path(target)
        importing_path = database_importing_path(target)
        shutil.copy2(target, backup_path)
        try:
            shutil.copy2(source, importing_path)
        except OSError:
            try:
                importing_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        self.database.close()
        try:
            os.replace(importing_path, target)
        except OSError:
            self.database.connect()
            try:
                importing_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        self.database.init_db()
        self.graph_manager = GraphManager(self.database)
        self.selected_node = None
        self.collapsed_folder_node_ids.clear()
        self.reload_runtime_settings()
        self.reload_graph()
        return backup_path

    def reload_runtime_settings(self) -> None:
        self.graph_font_size = self._load_graph_font_size()
        self.node_label_mode = self._load_node_label_mode()
        self.edge_label_mode = self._load_edge_label_mode()
        self.ignored_dir_names = self._load_ignored_dir_names()
        self.extension_icon_overrides = self._load_json_setting(EXTENSION_ICON_OVERRIDES_SETTING, {})
        self.node_type_colors = self._load_node_type_colors()
        self.highlight_color_slots = self._load_highlight_color_slots()
        self.graph_viewer.set_label_font_size(self.graph_font_size)
        self.graph_viewer.set_label_visibility_modes(
            node_mode=self.node_label_mode,
            edge_mode=self.edge_label_mode,
        )
        self.graph_viewer.set_extension_icon_overrides(self.extension_icon_overrides)

    def create_progress_dialog(self, title: str, label: str, *, maximum: int) -> QProgressDialog:
        progress = QProgressDialog(label, "취소", 0, maximum, self)
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        return progress

    def export_graph_json(self) -> None:
        target_path, _filter = QFileDialog.getSaveFileName(self, "JSON 내보내기", "filegraph_export.json", "JSON (*.json)")
        if not target_path:
            return
        payload = {
            "nodes": self.database.list_nodes(include_deleted=True),
            "relations": self.database.list_relations(include_deleted=True),
            "relation_types": self.database.list_relation_types(include_inactive=True),
        }
        Path(target_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.statusBar().showMessage(f"JSON으로 내보냈습니다: {target_path}", 3500)

    def export_graph_csv(self) -> None:
        target_dir = QFileDialog.getExistingDirectory(self, "CSV 내보내기 폴더")
        if not target_dir:
            return
        write_csv(Path(target_dir) / "nodes.csv", self.database.list_nodes(include_deleted=True))
        write_csv(Path(target_dir) / "relations.csv", self.database.list_relations(include_deleted=True))
        self.statusBar().showMessage(f"CSV로 내보냈습니다: {target_dir}", 3500)

    def push_undo(self, action: dict[str, Any]) -> None:
        self.undo_stack.append(action)
        del self.undo_stack[:-30]

    def undo_last_action(self) -> None:
        if not self.undo_stack:
            self.statusBar().showMessage("되돌릴 작업이 없습니다.", 1500)
            return

        action = self.undo_stack.pop()
        kind = action.get("kind")
        if kind == "node_delete":
            for node_id, status in action.get("nodes", {}).items():
                self.database.update_node_status(int(node_id), str(status or "ACTIVE"))
            self.reload_graph()
            self.statusBar().showMessage("노드 삭제를 되돌렸습니다.", 1800)
            return
        if kind == "relation_delete":
            relation = action.get("relation") or {}
            try:
                self.database.add_relation(
                    int(relation["source_id"]),
                    int(relation["target_id"]),
                    relation_type_id=int(relation["relation_type_id"]),
                    is_directional=bool(relation.get("is_directional")),
                    strength=relation.get("strength") or "MEDIUM",
                    description=relation.get("description"),
                )
            except (DuplicateRelationError, KeyError, ValueError):
                pass
            self.reload_graph()
            self.statusBar().showMessage("관계 삭제를 되돌렸습니다.", 1800)
            return
        if kind == "layout":
            for node_id, position in action.get("positions", {}).items():
                x, y = position
                self.database.update_node_layout(int(node_id), x, y)
            self.reload_graph()
            self.statusBar().showMessage("자동 정렬을 되돌렸습니다.", 1800)
            return

        self.statusBar().showMessage("되돌릴 수 없는 작업입니다.", 1800)

    def reload_graph(self) -> None:
        data = self.graph_manager.get_graph_data()
        data = self.prepare_graph_data(data)
        self.current_graph_data = data
        self.graph_viewer.render_graph(data)
        self.control_panel.set_selected_node_count(len(self.graph_viewer.selected_node_ids()))
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        if self.selected_node:
            refreshed = self.database.get_node(self.selected_node["node_id"])
            if refreshed and refreshed.get("status") != "DELETED":
                self.selected_node = refreshed
                self.control_panel.show_node(refreshed)
                self.control_panel.show_relations(
                    relations_for_node_in_graph_data(data, refreshed["node_id"])
                )
                self.control_panel.show_file_context(
                    relations_for_node_in_graph_data(data, refreshed["node_id"]),
                    int(refreshed["node_id"]),
                )
            else:
                self.selected_node = None
                self.control_panel.show_node(None)
                self.control_panel.show_relations(data["relations"])
                self.control_panel.show_file_context([], None)
        else:
            self.control_panel.show_node(None)
            self.control_panel.show_relations(data["relations"])
            self.control_panel.show_file_context([], None)
        self.refresh_candidate_panel()
        self.statusBar().showMessage("그래프를 불러왔습니다.", 2500)

    def refresh_candidate_panel(self) -> None:
        candidates = self.database.list_relationship_candidates()
        self.control_panel.show_candidates(candidates)

    def analyze_relationship_candidates(self) -> None:
        result = analyze_registered_files(self.database)
        self.refresh_candidate_panel()
        if result["created"]:
            self.control_panel.detail_tabs.setCurrentIndex(2)
        self.statusBar().showMessage(
            f"관계 후보 분석 완료: 감지 {result['detected']}개, 새 후보 {result['created']}개",
            4000,
        )

    def approve_relationship_candidate(self, candidate_id: int) -> None:
        try:
            self.database.approve_relationship_candidate(candidate_id)
        except (ValueError, DuplicateRelationError) as exc:
            QMessageBox.warning(self, "후보 승인 실패", str(exc))
            return
        self.reload_graph()
        self.statusBar().showMessage("관계 후보를 승인했습니다.", 2500)

    def reject_relationship_candidate(self, candidate_id: int) -> None:
        self.database.reject_relationship_candidate(candidate_id)
        self.refresh_candidate_panel()
        self.statusBar().showMessage("관계 후보를 거절했습니다.", 2500)

    def show_impact_view(self, node_id: int) -> None:
        impact_ids = self.graph_manager.get_downstream_impact_node_ids(node_id)
        nodes = [node for node in self.database.list_nodes() if int(node["node_id"]) in impact_ids]
        relations = [
            relation
            for relation in self.database.list_relations()
            if int(relation["source_id"]) in impact_ids and int(relation["target_id"]) in impact_ids
        ]
        self.render_node_subset_view(
            nodes,
            relations=relations,
            title="잠재 영향 파일",
            empty_message="관계 기준으로 영향을 받을 파일이 없습니다.",
        )

    def apply_collapsed_folders(self, data: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        if not self.collapsed_folder_node_ids:
            return data

        collapsed_file_counts = {
            folder_id: len(self.contained_file_node_ids(folder_id))
            for folder_id in self.collapsed_folder_node_ids
        }
        collapsed_file_counts = {
            folder_id: count
            for folder_id, count in collapsed_file_counts.items()
            if count > 0
        }
        if not collapsed_file_counts:
            return data

        hidden_node_ids = collapsed_contained_file_node_ids(data, self.collapsed_folder_node_ids)
        visible_nodes = []
        for node in data.get("nodes", []):
            node_id = int(node["node_id"])
            if node_id in hidden_node_ids:
                continue
            visible_node = dict(node)
            if node_id in collapsed_file_counts:
                visible_node["is_collapsed"] = True
                visible_node["collapsed_file_count"] = collapsed_file_counts[node_id]
            visible_nodes.append(visible_node)

        visible_node_ids = {int(node["node_id"]) for node in visible_nodes}
        visible_relations = [
            relation
            for relation in data.get("relations", [])
            if int(relation["source_id"]) in visible_node_ids
            and int(relation["target_id"]) in visible_node_ids
        ]
        return {"nodes": visible_nodes, "relations": visible_relations}

    def prepare_graph_data(self, data: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        prepared = self.apply_collapsed_folders(data)
        nodes = []
        for node in prepared.get("nodes", []):
            rendered = dict(node)
            rendered["type_color"] = self.node_type_colors.get(str(rendered.get("node_type") or "").upper())
            nodes.append(rendered)
        return {"nodes": nodes, "relations": prepared.get("relations", [])}

    def nodes_with_parent_folder_names(self) -> list[dict[str, Any]]:
        nodes = self.database.list_nodes()
        nodes_by_id = {int(node["node_id"]): node for node in nodes}
        parent_names: dict[int, str] = {}
        for relation in self.database.list_relations():
            if relation.get("relation_type_code") != "CONTAINS":
                continue
            source = nodes_by_id.get(int(relation["source_id"]))
            target = nodes_by_id.get(int(relation["target_id"]))
            if source is None or target is None:
                continue
            if source.get("node_type") != "FOLDER":
                continue
            parent_names.setdefault(int(target["node_id"]), str(source.get("name") or ""))
        return [
            {**node, "parent_folder_name": parent_names.get(int(node["node_id"]), "")}
            for node in nodes
        ]

    def scan_file_statuses(
        self,
        *,
        progress_callback=None,
        should_cancel=None,
    ) -> IntegrityScanResult:
        return scan_database_file_statuses(
            self.database,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )

    def refresh_file_statuses(self) -> None:
        total_nodes = len(self.database.list_nodes())
        progress = self.create_progress_dialog(
            "파일 위치 갱신",
            "파일 위치와 해시를 확인하는 중...",
            maximum=max(1, total_nodes),
        )

        def report_progress(completed: int, total: int | None, label: str) -> bool:
            total_count = total or total_nodes or 1
            progress.setRange(0, max(1, total_count))
            progress.setValue(min(completed, max(1, total_count)))
            detail = f"\n{label}" if label else ""
            progress.setLabelText(f"파일 위치와 해시를 확인하는 중... {completed}/{total_count}{detail}")
            QApplication.processEvents()
            return not progress.wasCanceled()

        result = self.scan_file_statuses(
            progress_callback=report_progress,
            should_cancel=progress.wasCanceled,
        )
        progress.close()
        self.reload_graph()
        self.statusBar().showMessage(integrity_scan_status_message(result), 3500)

    def locate_missing_files(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "누락 파일을 찾을 폴더 선택")
        if not folder_path:
            return
        self.rediscover_missing_files([folder_path])

    def rediscover_missing_files(self, search_roots: list[str | os.PathLike[str]]) -> RediscoveryResult:
        progress = self.create_progress_dialog(
            "누락 파일 찾기",
            "해시가 같은 파일을 찾는 중...",
            maximum=0,
        )

        def report_progress(scanned: int, _total: int | None, label: str) -> bool:
            progress.setRange(0, 0)
            detail = f"\n{label}" if label else ""
            progress.setLabelText(f"해시가 같은 파일을 찾는 중... 검사 {scanned}개{detail}")
            QApplication.processEvents()
            return not progress.wasCanceled()

        result = rediscover_missing_nodes(
            self.database,
            search_roots,
            ignored_dir_names=self.ignored_dir_names,
            progress_callback=report_progress,
            should_cancel=progress.wasCanceled,
        )
        progress.close()
        self.reload_graph()
        self.statusBar().showMessage(rediscovery_status_message(result), 3500)
        return result

    def show_focus_graph(self, depth: int) -> None:
        depth = max(0, int(depth))
        if not self.selected_node:
            QMessageBox.information(self, "포커스 보기", "먼저 노드를 선택해 주세요.")
            return

        node = self.database.get_node(self.selected_node["node_id"])
        if node is None or node.get("status") == "DELETED":
            QMessageBox.warning(self, "포커스 보기 실패", "선택한 노드를 찾을 수 없습니다.")
            self.selected_node = None
            self.reload_graph()
            return

        self.selected_node = node
        data = self.graph_manager.get_focus_graph_data(node["node_id"], depth=depth)
        data = self.prepare_graph_data(data)
        self.current_graph_data = data
        self.graph_viewer.render_graph(data)
        self.graph_viewer.focus_node(node["node_id"])
        self.control_panel.set_selected_node_count(len(self.graph_viewer.selected_node_ids()))
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        self.control_panel.show_node(node)
        self.control_panel.show_relations(relations_for_node_in_graph_data(data, node["node_id"]))
        self.statusBar().showMessage(f"{node['name']} 기준 {depth}단계 포커스 보기", 2500)

    def search_nodes(self, query: str | None = None) -> None:
        query = self.control_panel.search_text() if query is None else query.strip()
        if not query:
            self.reload_graph()
            return

        nodes = self.database.search_nodes(query)
        node_ids = {node["node_id"] for node in nodes}
        relations = [
            relation
            for relation in self.database.list_relations()
            if relation["source_id"] in node_ids and relation["target_id"] in node_ids
        ]
        data = self.graph_manager.get_graph_data(
            nodes=nodes,
            relations=relations,
            scale=SEARCH_LAYOUT_SCALE,
            use_saved_layout=False,
        )
        data = self.prepare_graph_data(data)
        self.current_graph_data = data
        self.graph_viewer.render_graph(data)
        self.control_panel.set_selected_node_count(len(self.graph_viewer.selected_node_ids()))
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        self.control_panel.show_relations(data["relations"])
        visible_nodes = data["nodes"]
        self.statusBar().showMessage(f"검색 결과 {len(visible_nodes)}개", 2500)
        if len(visible_nodes) == 1:
            node = self.database.get_node(visible_nodes[0]["node_id"]) or visible_nodes[0]
            self.selected_node = node
            self.control_panel.show_node(node)
            self.control_panel.show_relations(relations_for_node_in_graph_data(data, node["node_id"]))
            self.graph_viewer.focus_node(node["node_id"])
            self.control_panel.set_selected_node_count(len(self.graph_viewer.selected_node_ids()))
        else:
            self.selected_node = None
            self.control_panel.show_node(None)

    def update_search_suggestions(self, query: str) -> None:
        query = query.strip()
        if len(query) < 2:
            self.control_panel.set_search_suggestions([])
            return
        self.control_panel.set_search_suggestions(self.database.search_nodes(query, limit=8))

    def focus_search_suggestion(self, node_id: int) -> None:
        node = self.database.get_node(node_id)
        if node is None or node.get("status") == "DELETED":
            self.control_panel.set_search_suggestions([])
            return
        self.selected_node = node
        self.control_panel.search_input.setText(node.get("name", ""))
        self.control_panel.set_search_suggestions([])
        self.search_nodes(node.get("name", ""))
        self.graph_viewer.focus_node(node_id)

    def add_file_node(self) -> None:
        file_path, _filter = QFileDialog.getOpenFileName(self, "파일 추가")
        if file_path:
            self._add_node(file_path, node_type="FILE")

    def add_folder_node(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "폴더 추가")
        if folder_path:
            if should_ignore_directory(Path(folder_path), self.ignored_dir_names):
                self.statusBar().showMessage("무시 폴더로 설정된 경로는 추가하지 않습니다.", 3000)
                return
            include_folder_contents = self.ask_folder_import_options_for_paths([folder_path], folder_count=1)
            if include_folder_contents is None:
                return
            self._add_import_paths(
                [folder_path],
                include_folder_contents=include_folder_contents,
                action_label="폴더",
            )

    def add_dropped_paths(self, paths: list[str]) -> None:
        folder_count = count_folder_paths(paths, ignored_dir_names=self.ignored_dir_names)
        include_folder_contents = False
        if folder_count:
            selected = self.ask_folder_import_options_for_paths(paths, folder_count=folder_count)
            if selected is None:
                self.statusBar().showMessage("드롭한 경로 추가를 취소했습니다.", 2500)
                return
            include_folder_contents = selected

        self._add_import_paths(
            paths,
            include_folder_contents=include_folder_contents,
            action_label="드롭한 경로",
        )

    def ask_folder_import_options_for_paths(self, paths: list[str], *, folder_count: int) -> bool | None:
        try:
            return self.ask_folder_import_options(folder_count=folder_count, paths=paths)
        except TypeError:
            return self.ask_folder_import_options(folder_count=folder_count)

    def ask_folder_import_options(self, *, folder_count: int, paths: list[str] | None = None) -> bool | None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("폴더 추가")
        message_box.setIcon(QMessageBox.Question)
        message_box.setText(f"폴더 {folder_count}개를 노드로 추가합니다.")
        informative_text = "하위 파일 자동 등록이 기본으로 켜져 있습니다. 원하지 않으면 옵션을 끄세요."
        if paths:
            preview_plan = build_import_plan(
                paths,
                include_folder_contents=True,
                ignored_dir_names=self.ignored_dir_names,
            )
            file_count = sum(1 for _path, node_type in preview_plan.entries if node_type == "FILE")
            folder_node_count = sum(1 for _path, node_type in preview_plan.entries if node_type == "FOLDER")
            informative_text += (
                f"\n미리보기: 폴더 {folder_node_count}개, 파일 {file_count}개, "
                f"포함 관계 {len(preview_plan.contains_pairs)}개"
            )
        message_box.setInformativeText(informative_text)
        include_files_check = QCheckBox("내부 파일도 등록")
        include_files_check.setChecked(True)
        message_box.setCheckBox(include_files_check)
        message_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        message_box.setDefaultButton(QMessageBox.Ok)

        if message_box.exec() != QMessageBox.Ok:
            return None
        return include_files_check.isChecked()

    def _add_import_paths(
        self,
        paths: list[str],
        *,
        include_folder_contents: bool,
        action_label: str,
    ) -> None:
        added_ids: list[int] = []
        node_ids_by_path: dict[str, int] = {}
        duplicate_count = 0
        first_duplicate: dict[str, Any] | None = None
        import_plan = build_import_plan(
            paths,
            include_folder_contents=include_folder_contents,
            ignored_dir_names=self.ignored_dir_names,
        )
        if not import_plan.entries:
            self.statusBar().showMessage("무시 폴더 정책으로 추가할 경로가 없습니다.", 3000)
            return
        if self.should_import_in_background(import_plan):
            self.start_background_import(import_plan, action_label=action_label)
            return

        result = execute_import_plan(self.database, import_plan)
        added_ids = result["added_ids"]
        node_ids_by_path = result["node_ids_by_path"]
        duplicate_count = result["duplicate_count"]
        first_duplicate = result["first_duplicate"]
        contains_relation_count = result["contains_relation_count"]

        if not added_ids and contains_relation_count == 0:
            if duplicate_count:
                if duplicate_count == len(import_plan.entries) and first_duplicate:
                    self.handle_duplicate_node(first_duplicate)
                else:
                    self.statusBar().showMessage(f"이미 등록된 경로 {duplicate_count}개를 건너뛰었습니다.", 3000)
            return

        self.reload_graph()
        if import_plan.contains_pairs:
            selected_id = self._first_contains_folder_id(import_plan, node_ids_by_path)
        else:
            selected_id = added_ids[-1]
        self.graph_viewer.focus_node(selected_id)
        self.selected_node = self.database.get_node(selected_id)
        self.control_panel.show_node(self.selected_node)
        self.control_panel.show_relations(self.database.list_relations(node_id=selected_id))

        if added_ids:
            message = f"{action_label} {len(added_ids)}개를 노드로 추가했습니다."
        else:
            message = "새 노드 없이 포함 관계를 추가했습니다."
        if contains_relation_count:
            message += f" 포함 관계 {contains_relation_count}개를 추가했습니다."
        if duplicate_count:
            message += f" 중복 {duplicate_count}개는 건너뛰었습니다."
        analysis = analyze_registered_files(self.database, changed_node_ids=set(added_ids))
        if analysis["created"]:
            self.refresh_candidate_panel()
            self.control_panel.detail_tabs.setCurrentIndex(2)
            message += f" 관계 후보 {analysis['created']}개를 찾았습니다."
        self.statusBar().showMessage(message, 3500)

    def should_import_in_background(self, import_plan: ImportPlan) -> bool:
        return (
            len(import_plan.entries) >= BACKGROUND_IMPORT_THRESHOLD
            and str(self.database.db_path) != ":memory:"
            and self.import_worker_thread is None
        )

    def start_background_import(self, import_plan: ImportPlan, *, action_label: str) -> None:
        self.import_worker_thread = QThread(self)
        self.import_worker = ImportWorker(self.database.db_path, import_plan, action_label)
        self.import_worker.moveToThread(self.import_worker_thread)
        self.import_worker_thread.started.connect(self.import_worker.run)
        self.import_worker.progress.connect(self.on_background_import_progress)
        self.import_worker.finished.connect(self.on_background_import_finished)
        self.import_worker.failed.connect(self.on_background_import_failed)
        self.import_worker.finished.connect(self.import_worker_thread.quit)
        self.import_worker.failed.connect(self.import_worker_thread.quit)
        self.import_worker_thread.finished.connect(self.clear_background_import_worker)
        total_steps = import_plan_step_count(import_plan)
        self.import_progress_dialog = self.create_progress_dialog(
            f"{action_label} 추가",
            f"{action_label} {len(import_plan.entries)}개를 백그라운드에서 추가하는 중...",
            maximum=max(1, total_steps),
        )
        self.import_progress_dialog.canceled.connect(self.request_background_import_cancel)
        self.import_worker_thread.start()
        self.statusBar().showMessage(f"{action_label} {len(import_plan.entries)}개를 백그라운드에서 추가합니다.", 3500)

    def request_background_import_cancel(self) -> None:
        if self.import_worker is not None:
            self.import_worker.request_cancel()
        if self.import_progress_dialog is not None:
            self.import_progress_dialog.setLabelText("취소 요청을 처리하는 중...")

    def on_background_import_progress(self, completed: int, total: int, label: str) -> None:
        if self.import_progress_dialog is None:
            return
        total_count = max(1, int(total))
        self.import_progress_dialog.setRange(0, total_count)
        self.import_progress_dialog.setValue(min(int(completed), total_count))
        detail = f"\n{label}" if label else ""
        self.import_progress_dialog.setLabelText(
            f"경로를 등록하는 중... {completed}/{total_count}{detail}"
        )

    def on_background_import_finished(self, result: dict[str, Any]) -> None:
        self.close_import_progress_dialog()
        self.reload_graph()
        selected_id = result.get("selected_id")
        if selected_id is not None:
            self.graph_viewer.focus_node(int(selected_id))
            self.selected_node = self.database.get_node(int(selected_id))
            self.control_panel.show_node(self.selected_node)
            self.control_panel.show_relations(self.database.list_relations(node_id=int(selected_id)))
        action_label = result.get("action_label", "경로")
        if result.get("cancelled"):
            message = f"{action_label} 추가 취소됨: {len(result.get('added_ids', []))}개 추가"
        else:
            message = f"{action_label} {len(result.get('added_ids', []))}개 추가 완료"
        contains_relation_count = int(result.get("contains_relation_count") or 0)
        duplicate_count = int(result.get("duplicate_count") or 0)
        if contains_relation_count:
            message += f", 포함 관계 {contains_relation_count}개"
        if duplicate_count:
            message += f", 중복 {duplicate_count}개 건너뜀"
        added_ids = {int(node_id) for node_id in result.get("added_ids", [])}
        analysis = analyze_registered_files(self.database, changed_node_ids=added_ids)
        if analysis["created"]:
            self.refresh_candidate_panel()
            self.control_panel.detail_tabs.setCurrentIndex(2)
            message += f", 관계 후보 {analysis['created']}개"
        self.statusBar().showMessage(message, 4500)

    def on_background_import_failed(self, message: str) -> None:
        self.close_import_progress_dialog()
        QMessageBox.warning(self, "백그라운드 추가 실패", message)

    def close_import_progress_dialog(self) -> None:
        if self.import_progress_dialog is not None:
            self.import_progress_dialog.close()
            self.import_progress_dialog.deleteLater()
            self.import_progress_dialog = None

    def clear_background_import_worker(self) -> None:
        self.import_worker = None
        if self.import_worker_thread is not None:
            self.import_worker_thread.deleteLater()
        self.import_worker_thread = None

    def _add_default_contains_relations(
        self,
        contains_pairs: list[tuple[str, str]],
        node_ids_by_path: dict[str, int],
    ) -> int:
        created_count = 0
        for folder_path, file_path in contains_pairs:
            source_id = node_ids_by_path.get(folder_path)
            target_id = node_ids_by_path.get(file_path)
            if source_id is None or target_id is None:
                continue
            try:
                self.database.add_relation(
                    source_id,
                    target_id,
                    relation_type_code="CONTAINS",
                    strength="HIGH",
                )
            except DuplicateRelationError:
                continue
            created_count += 1
        return created_count

    def _first_contains_folder_id(self, import_plan: ImportPlan, node_ids_by_path: dict[str, int]) -> int:
        if import_plan.contains_pairs:
            folder_id = node_ids_by_path.get(import_plan.contains_pairs[0][0])
            if folder_id is not None:
                return folder_id
        return next(iter(node_ids_by_path.values()))

    def ask_duplicate_node_action(self, existing_node: dict[str, Any]) -> str | None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("이미 등록된 노드")
        message_box.setIcon(QMessageBox.Information)
        message_box.setText(f"{existing_node['name']} 노드는 이미 등록되어 있습니다.")
        message_box.setInformativeText(existing_node.get("path") or "")

        focus_button = message_box.addButton("기존 노드로 이동", QMessageBox.AcceptRole)
        relation_button = message_box.addButton("관계 추가하기", QMessageBox.ActionRole)
        cancel_button = message_box.addButton("취소", QMessageBox.RejectRole)
        message_box.setDefaultButton(focus_button)
        message_box.exec()

        clicked_button = message_box.clickedButton()
        if clicked_button == focus_button:
            return DUPLICATE_NODE_FOCUS
        if clicked_button == relation_button:
            return DUPLICATE_NODE_RELATION
        if clicked_button == cancel_button:
            return DUPLICATE_NODE_CANCEL
        return None

    def handle_duplicate_node(self, existing_node: dict[str, Any]) -> str | None:
        action = self.ask_duplicate_node_action(existing_node)
        if action == DUPLICATE_NODE_FOCUS:
            self.focus_existing_node(existing_node)
            self.statusBar().showMessage("이미 등록된 노드로 이동했습니다.", 2500)
        elif action == DUPLICATE_NODE_RELATION:
            self.focus_existing_node(existing_node)
            self.add_relation()
        elif action == DUPLICATE_NODE_CANCEL:
            self.statusBar().showMessage("중복 노드 추가를 취소했습니다.", 2500)
        return action

    def focus_existing_node(self, node: dict[str, Any]) -> None:
        refreshed = self.database.get_node(node["node_id"]) or node
        self.selected_node = refreshed
        self.reload_graph()
        self.graph_viewer.focus_node(refreshed["node_id"])
        self.control_panel.show_node(refreshed)
        self.control_panel.show_relations(
            relations_for_node_in_graph_data(self.current_graph_data, refreshed["node_id"])
        )

    def reset_layout(self) -> None:
        previous_positions = {
            int(node["node_id"]): (node.get("layout_x"), node.get("layout_y"))
            for node in self.database.list_nodes()
        }
        for node in self.database.list_nodes():
            self.database.update_node_layout(node["node_id"], None, None)
        data = self.graph_manager.get_graph_data(seed=self.next_layout_seed())
        for node in data["nodes"]:
            self.database.update_node_layout(node["node_id"], node["x"], node["y"])
        self.push_undo({"kind": "layout", "positions": previous_positions})
        self.reload_graph()
        self.statusBar().showMessage("수동 좌표를 초기화했습니다.", 2500)

    def add_relation(self) -> None:
        nodes = self.nodes_with_parent_folder_names()
        if len(nodes) < 2:
            QMessageBox.information(self, "관계 추가", "관계를 만들려면 노드가 2개 이상 필요합니다.")
            return

        dialog = RelationDialog(
            nodes,
            self.database.list_relation_types(),
            selected_node_id=self.selected_node["node_id"] if self.selected_node else None,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        try:
            relation_id = self._create_relation(dialog.values())
        except ValueError as exc:
            QMessageBox.warning(self, "관계 추가 실패", str(exc))
            return
        except DuplicateRelationError as exc:
            self.reload_graph()
            QMessageBox.information(
                self,
                "이미 있는 관계",
                f"이미 같은 관계가 있습니다. 관계 ID: {exc.existing_relation['relation_id']}",
            )
            return

        self.reload_graph()
        self.statusBar().showMessage(f"관계 {relation_id}번을 추가했습니다.", 2500)

    def edit_relation(self, relation_id: int) -> None:
        relation = self.database.get_relation(relation_id)
        if relation is None:
            QMessageBox.warning(self, "관계 수정 실패", "선택한 관계를 찾을 수 없습니다.")
            self.reload_graph()
            return

        dialog = RelationDialog(
            self.nodes_with_parent_folder_names(),
            self.database.list_relation_types(),
            initial_values=relation,
            lock_nodes=True,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        values = dialog.values()
        try:
            relation_type_id = self._resolve_relation_type_id(values)
        except ValueError as exc:
            QMessageBox.warning(self, "관계 수정 실패", str(exc))
            return

        existing = self.database.find_duplicate_relation(
            relation["source_id"],
            relation["target_id"],
            relation_type_id,
            values["is_directional"],
        )
        if existing and existing["relation_id"] != relation_id:
            QMessageBox.information(
                self,
                "이미 있는 관계",
                f"이미 같은 관계가 있습니다. 관계 ID: {existing['relation_id']}",
            )
            return

        self.database.update_relation(
            relation_id,
            relation_type_id=relation_type_id,
            is_directional=values["is_directional"],
            strength=values["strength"],
            description=values["description"],
        )
        self.reload_graph()
        self.statusBar().showMessage(f"관계 {relation_id}번을 수정했습니다.", 2500)

    def delete_relation(self, relation_id: int) -> None:
        relation = self.database.get_relation(relation_id)
        if relation is None:
            QMessageBox.warning(self, "관계 삭제 실패", "선택한 관계를 찾을 수 없습니다.")
            self.reload_graph()
            return

        answer = QMessageBox.question(
            self,
            "관계 삭제",
            (
                f"{relation['source_name']} - {relation['target_name']}\n"
                f"{relation['relation_type_name']} 관계를 삭제할까요?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.push_undo({"kind": "relation_delete", "relation": dict(relation)})
        self.database.delete_relation(relation_id)
        self.reload_graph()
        self.statusBar().showMessage(f"관계 {relation_id}번을 삭제했습니다.", 2500)

    def delete_node(self, node_id: int) -> None:
        node = self.database.get_node(node_id)
        if node is None or node.get("status") == "DELETED":
            QMessageBox.warning(self, "노드 삭제 실패", "선택한 노드를 찾을 수 없습니다.")
            self.selected_node = None
            self.reload_graph()
            return

        relation_count = len(self.database.list_relations(node_id=node_id, include_deleted=True))
        relation_note = (
            f"\n연결된 관계 {relation_count}개는 기록으로 보존되지만 그래프에서는 숨겨집니다."
            if relation_count
            else ""
        )
        answer = QMessageBox.question(
            self,
            "노드 삭제",
            (
                f"{node['name']} 노드를 삭제할까요?\n"
                "원본 파일이나 폴더는 삭제하지 않고 FileGraph에서만 숨깁니다."
                f"{relation_note}"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.push_undo({"kind": "node_delete", "nodes": {node_id: node.get("status", "ACTIVE")}})
        self.database.update_node_status(node_id, "DELETED")
        self.selected_node = None
        self.reload_graph()
        self.statusBar().showMessage(f"{node['name']} 노드를 삭제 처리했습니다.", 2500)

    def delete_node_or_selection(self, node_id: int) -> None:
        node_ids = self.context_delete_node_ids(node_id)
        if len(node_ids) > 1:
            self.delete_nodes(node_ids)
            return
        self.delete_node(node_id)

    def delete_selected_nodes_from_panel(self) -> None:
        selected_node_ids = self.graph_viewer.selected_node_ids()
        if selected_node_ids:
            if len(selected_node_ids) > 1:
                self.delete_nodes(selected_node_ids)
            else:
                self.delete_node(selected_node_ids[0])
            return

        if self.selected_node:
            self.delete_node(int(self.selected_node["node_id"]))

    def context_delete_node_ids(self, node_id: int) -> list[int]:
        selected_node_ids = self.graph_viewer.selected_node_ids()
        if node_id in selected_node_ids and len(selected_node_ids) > 1:
            return selected_node_ids
        return [node_id]

    def delete_nodes(self, node_ids: list[int]) -> None:
        nodes = [
            node
            for node_id in node_ids
            if (node := self.database.get_node(node_id)) is not None and node.get("status") != "DELETED"
        ]
        if not nodes:
            QMessageBox.warning(self, "노드 삭제 실패", "삭제할 노드를 찾을 수 없습니다.")
            self.reload_graph()
            return

        relation_ids = {
            relation["relation_id"]
            for node in nodes
            for relation in self.database.list_relations(node_id=node["node_id"], include_deleted=True)
        }
        answer = QMessageBox.question(
            self,
            "선택 노드 삭제",
            (
                f"선택한 노드 {len(nodes)}개를 삭제할까요?\n"
                "원본 파일이나 폴더는 삭제하지 않고 FileGraph에서만 숨깁니다.\n"
                f"연결된 관계 {len(relation_ids)}개는 기록으로 보존되지만 그래프에서는 숨겨집니다."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        deleted_node_ids = {node["node_id"] for node in nodes}
        self.push_undo(
            {
                "kind": "node_delete",
                "nodes": {int(node["node_id"]): node.get("status", "ACTIVE") for node in nodes},
            }
        )
        for node_id in deleted_node_ids:
            self.database.update_node_status(node_id, "DELETED")
        if self.selected_node and self.selected_node["node_id"] in deleted_node_ids:
            self.selected_node = None
        self.reload_graph()
        self.statusBar().showMessage(f"선택한 노드 {len(deleted_node_ids)}개를 삭제 처리했습니다.", 2500)

    def show_node_context_menu(self, node: dict[str, Any], global_position: QPoint) -> None:
        refreshed = self.database.get_node(int(node["node_id"]))
        if refreshed is None or refreshed.get("status") == "DELETED":
            self.reload_graph()
            return

        self.on_node_selected(refreshed)
        menu = self.build_node_context_menu(refreshed)
        self.exec_context_menu(menu, global_position)

    def exec_context_menu(self, menu: QMenu, global_position: QPoint) -> None:
        menu.exec(global_position)

    def build_node_context_menu(self, node: dict[str, Any]) -> QMenu:
        node_id = int(node["node_id"])
        menu = QMenu(self)

        open_action = menu.addAction("열기")
        open_action.setData(NODE_CONTEXT_OPEN_NODE)
        open_action.triggered.connect(lambda _checked=False, node=dict(node): self.open_node(node))
        menu.addSeparator()

        if node.get("node_type") == "FOLDER":
            contained_file_count = len(self.contained_file_node_ids(node_id))
            if contained_file_count:
                label = (
                    f"내부 파일 펼치기 ({contained_file_count}개)"
                    if node_id in self.collapsed_folder_node_ids
                    else f"내부 파일 접기 ({contained_file_count}개)"
                )
            else:
                label = "내부 파일 없음"
            toggle_contains_action = menu.addAction(label)
            toggle_contains_action.setData(NODE_CONTEXT_TOGGLE_CONTAINS)
            toggle_contains_action.setEnabled(contained_file_count > 0)
            toggle_contains_action.triggered.connect(
                lambda _checked=False, node_id=node_id: self.toggle_folder_contents(node_id)
            )
            menu.addSeparator()

        add_relation_action = menu.addAction("관계 추가")
        add_relation_action.setData(NODE_CONTEXT_ADD_RELATION)
        add_relation_action.triggered.connect(lambda _checked=False: self.add_relation())

        relations = self.database.list_relations(node_id=node_id)
        edit_menu = menu.addMenu("관계 수정")
        edit_menu.menuAction().setData(NODE_CONTEXT_EDIT_RELATIONS)
        if relations:
            for relation in relations:
                relation_id = int(relation["relation_id"])
                edit_action = edit_menu.addAction(relation_context_label(relation))
                edit_action.setData(relation_id)
                edit_action.triggered.connect(
                    lambda _checked=False, relation_id=relation_id: self.edit_relation(relation_id)
                )
        else:
            empty_action = edit_menu.addAction("연결된 관계 없음")
            empty_action.setEnabled(False)
            edit_menu.setEnabled(False)

        color_menu = menu.addMenu("관계 색상")
        if relations:
            seen_relation_type_ids: set[int] = set()
            for relation in relations:
                relation_type_id = int(relation["relation_type_id"])
                if relation_type_id in seen_relation_type_ids:
                    continue
                seen_relation_type_ids.add(relation_type_id)
                color_action = color_menu.addAction(str(relation.get("relation_type_name") or relation_type_id))
                color_action.triggered.connect(
                    lambda _checked=False, relation_type_id=relation_type_id: self.choose_relation_type_color(
                        relation_type_id
                    )
                )
        else:
            empty_color_action = color_menu.addAction("연결된 관계 없음")
            empty_color_action.setEnabled(False)
            color_menu.setEnabled(False)

        menu.addSeparator()

        note_action = menu.addAction("메모 보기/수정")
        note_action.setData(NODE_CONTEXT_EDIT_NOTE)
        note_action.triggered.connect(lambda _checked=False, node_id=node_id: self.edit_node_note(node_id))

        highlight_menu = menu.addMenu("강조 색상")
        highlight_menu.menuAction().setData(NODE_CONTEXT_HIGHLIGHT_NODE)
        for color in self.highlight_color_slots:
            highlight_action = highlight_menu.addAction(color)
            highlight_action.setData(color)
            highlight_action.triggered.connect(
                lambda _checked=False, node_id=node_id, color=color: self.set_node_highlight(node_id, color)
            )
        custom_highlight_action = highlight_menu.addAction("직접 선택...")
        custom_highlight_action.triggered.connect(
            lambda _checked=False, node_id=node_id: self.choose_node_highlight(node_id)
        )
        clear_highlight_action = highlight_menu.addAction("강조 지우기")
        clear_highlight_action.setData(NODE_CONTEXT_CLEAR_HIGHLIGHT)
        clear_highlight_action.triggered.connect(
            lambda _checked=False, node_id=node_id: self.set_node_highlight(node_id, None)
        )

        menu.addSeparator()

        delete_label = "선택 노드 삭제" if len(self.context_delete_node_ids(node_id)) > 1 else "노드 삭제"
        delete_node_action = menu.addAction(delete_label)
        delete_node_action.setData(NODE_CONTEXT_DELETE_NODE)
        delete_node_action.triggered.connect(
            lambda _checked=False, node_id=node_id: self.delete_node_or_selection(node_id)
        )

        return menu

    def contained_file_node_ids(self, folder_node_id: int) -> set[int]:
        contained_ids: set[int] = set()
        for relation in self.database.list_relations(node_id=folder_node_id):
            if relation.get("relation_type_code") != "CONTAINS":
                continue
            if int(relation["source_id"]) != folder_node_id:
                continue
            target = self.database.get_node(int(relation["target_id"]))
            if target is not None and target.get("node_type") == "FILE":
                contained_ids.add(int(target["node_id"]))
        return contained_ids

    def toggle_folder_contents(self, folder_node_id: int) -> None:
        contained_file_count = len(self.contained_file_node_ids(folder_node_id))
        if contained_file_count == 0:
            self.statusBar().showMessage("접거나 펼칠 내부 파일이 없습니다.", 2000)
            return

        if folder_node_id in self.collapsed_folder_node_ids:
            self.collapsed_folder_node_ids.remove(folder_node_id)
            action_label = "펼쳤습니다"
        else:
            self.collapsed_folder_node_ids.add(folder_node_id)
            action_label = "접었습니다"

        self.reload_graph()
        self.graph_viewer.focus_node(folder_node_id)
        self.statusBar().showMessage(f"내부 파일 {contained_file_count}개를 {action_label}.", 2500)

    def edit_node_note(self, node_id: int) -> None:
        node = self.database.get_node(node_id)
        if node is None or node.get("status") == "DELETED":
            self.reload_graph()
            return
        text, accepted = QInputDialog.getMultiLineText(
            self,
            "노드 메모",
            "메모",
            node.get("note") or "",
        )
        if not accepted:
            return
        self.database.update_node_note(node_id, text)
        self.reload_graph()
        refreshed = self.database.get_node(node_id)
        if refreshed is not None:
            self.on_node_selected(refreshed)
            self.graph_viewer.focus_node(node_id)
        self.statusBar().showMessage("노드 메모를 저장했습니다.", 1800)

    def set_node_highlight(self, node_id: int, color: str | None) -> None:
        if color is not None and not is_valid_color(color):
            QMessageBox.warning(self, "강조 색상", "올바른 색상 값이 아닙니다.")
            return
        self.database.update_node_highlight_color(node_id, color)
        self.reload_graph()
        node = self.database.get_node(node_id)
        if node is not None:
            self.selected_node = node
            self.control_panel.show_node(node)
            self.graph_viewer.focus_node(node_id)
        self.statusBar().showMessage("강조 색상을 저장했습니다.", 1500)

    def choose_node_highlight(self, node_id: int) -> None:
        color = QColorDialog.getColor(QColor("#F97316"), self, "강조 색상 선택")
        if color.isValid():
            self.set_node_highlight(node_id, color.name())

    def choose_relation_type_color(self, relation_type_id: int) -> None:
        color = QColorDialog.getColor(QColor("#64748B"), self, "관계 색상 선택")
        if not color.isValid():
            return
        self.database.update_relation_type_color(relation_type_id, color.name())
        self.reload_graph()
        self.statusBar().showMessage("관계 색상을 저장했습니다.", 1500)

    def on_node_selected(self, node: dict[str, Any]) -> None:
        self.selected_node = node
        self.control_panel.show_node(node)
        relations = relations_for_node_in_graph_data(self.current_graph_data, node["node_id"])
        self.control_panel.show_relations(relations)
        self.control_panel.show_file_context(relations, int(node["node_id"]))
        self.refresh_candidate_panel()
        self.control_panel.set_selected_node_count(len(self.graph_viewer.selected_node_ids()))

    def on_selected_nodes_changed(self, node_ids: list[int]) -> None:
        self.control_panel.set_selected_node_count(len(node_ids))

    def on_node_moved(self, node_id: int, x: float, y: float) -> None:
        self.database.update_node_layout(node_id, x, y)
        self.statusBar().showMessage("노드 위치를 저장했습니다.", 1200)

    def open_node(self, node: dict[str, Any]) -> None:
        path = node.get("path")
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "파일 없음", "현재 경로에서 파일 또는 폴더를 찾을 수 없습니다.")
            return
        # Opens the registered file or folder selected by the user.
        os.startfile(path)  # nosec B606

    def _add_node(self, path: str, *, node_type: str) -> None:
        try:
            node_id = self.database.add_node(path, node_type=node_type)
        except DuplicateNodeError as exc:
            self.handle_duplicate_node(exc.existing_node)
            return

        self.reload_graph()
        self.graph_viewer.focus_node(node_id)
        self.selected_node = self.database.get_node(node_id)
        self.control_panel.show_node(self.selected_node)
        self.control_panel.show_relations(self.database.list_relations(node_id=node_id))

    def _create_relation(self, values: dict[str, Any]) -> int:
        if values["source_id"] == values["target_id"]:
            raise ValueError("서로 다른 두 노드를 선택해 주세요.")

        relation_type_id = self._resolve_relation_type_id(values)
        return self.database.add_relation(
            values["source_id"],
            values["target_id"],
            relation_type_id=relation_type_id,
            is_directional=values["is_directional"],
            strength=values["strength"],
            description=values["description"],
        )

    def _resolve_relation_type_id(self, values: dict[str, Any]) -> int:
        relation_type_id = values.get("relation_type_id")
        if relation_type_id is not None:
            return int(relation_type_id)

        raise ValueError("관계 타입을 선택해 주세요.")

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #F8FAFC;
            }
            #sidePanel {
                background: #F8FAFC;
            }
            #panelScrollArea,
            #panelScrollContent {
                border: 0;
                background: #F8FAFC;
            }
            QLineEdit {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 7px 10px;
                background: #FFFFFF;
                color: #0F172A;
            }
            QComboBox {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 8px;
                background: #FFFFFF;
                color: #0F172A;
                min-height: 28px;
            }
            QCheckBox {
                color: #334155;
                spacing: 8px;
            }
            QSpinBox {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 8px;
                background: #FFFFFF;
                color: #0F172A;
                min-height: 28px;
            }
            QPushButton {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 7px 11px;
                background: #FFFFFF;
                color: #0F172A;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #F1F5F9;
            }
            QPushButton:disabled {
                color: #94A3B8;
                border-color: #E2E8F0;
                background: #F8FAFC;
            }
            QPushButton[variant="primary"] {
                border-color: #1D4ED8;
                background: #2563EB;
                color: #FFFFFF;
                font-weight: 700;
            }
            QPushButton[variant="primary"]:hover {
                background: #1D4ED8;
            }
            QPushButton[variant="secondary"] {
                background: #FFFFFF;
            }
            QPushButton[variant="segmented"] {
                background: #EEF2FF;
                border-color: #C7D2FE;
                color: #1E3A8A;
            }
            QPushButton[variant="segmented"]:hover {
                background: #E0E7FF;
            }
            QPushButton[variant="danger"] {
                border-color: #FCA5A5;
                color: #B91C1C;
                background: #FFFFFF;
            }
            QPushButton[variant="danger"]:hover {
                background: #FEF2F2;
            }
            QPushButton[variant="danger"]:disabled {
                color: #FCA5A5;
                border-color: #FEE2E2;
                background: #FFFFFF;
            }
            QListWidget {
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                background: #FFFFFF;
                padding: 4px;
            }
            QLabel {
                color: #334155;
            }
            #panelTitle {
                color: #0F172A;
                font-size: 21px;
                font-weight: 700;
            }
            #sectionTitle {
                color: #0F172A;
                font-size: 13px;
                font-weight: 700;
            }
            #fieldLabel {
                color: #475569;
                font-size: 12px;
                font-weight: 700;
            }
            #nodeName {
                color: #0F172A;
                font-size: 16px;
                font-weight: 700;
            }
            #pathText {
                color: #475569;
                font-size: 12px;
            }
            #metaText {
                color: #64748B;
                font-size: 12px;
            }
            #summary {
                color: #64748B;
                padding-top: 4px;
            }
            #separator {
                color: #E2E8F0;
                background: #E2E8F0;
                max-height: 1px;
            }
            """
        )


def relation_context_label(relation: dict[str, Any]) -> str:
    direction = "->" if relation.get("is_directional") else "--"
    return (
        f"{relation.get('source_name', '')} {direction} {relation.get('target_name', '')} / "
        f"{relation.get('relation_type_name', '')}"
    )


def collapsed_contained_file_node_ids(
    data: dict[str, list[dict[str, Any]]],
    collapsed_folder_node_ids: set[int],
) -> set[int]:
    node_types = {
        int(node["node_id"]): node.get("node_type")
        for node in data.get("nodes", [])
    }
    return {
        int(relation["target_id"])
        for relation in data.get("relations", [])
        if int(relation["source_id"]) in collapsed_folder_node_ids
        and relation.get("relation_type_code") == "CONTAINS"
        and node_types.get(int(relation["target_id"])) == "FILE"
    }


def relations_for_node_in_graph_data(
    data: dict[str, list[dict[str, Any]]],
    node_id: int,
) -> list[dict[str, Any]]:
    target_node_id = int(node_id)
    return [
        relation
        for relation in data.get("relations", [])
        if int(relation["source_id"]) == target_node_id
        or int(relation["target_id"]) == target_node_id
    ]


def integrity_scan_status_message(result: IntegrityScanResult) -> str:
    if result.total == 0:
        return "확인할 노드가 없습니다."
    prefix = "파일 위치 갱신 취소됨" if result.cancelled else "파일 위치 갱신"
    message = (
        f"{prefix}: {result.total}개 중 {result.processed_count}개 확인, 변경 {result.changed_count}개 "
        f"(정상 {result.active}, 누락 {result.missing}, 접근 거부 {result.access_denied})"
    )
    if result.hashes_updated:
        message += f", 변경 감지 정보 갱신 {result.hashes_updated}개"
    if result.hashes_skipped:
        message += f", 해시 건너뜀 {result.hashes_skipped}개"
    return message


def rediscovery_status_message(result: RediscoveryResult) -> str:
    if result.total_missing == 0:
        return "복구할 누락 노드가 없습니다."
    if result.eligible_missing == 0:
        return "해시가 저장된 누락 파일이 없습니다."
    skipped = result.total_missing - result.eligible_missing
    prefix = "누락 파일 찾기 취소됨" if result.cancelled else "누락 파일 찾기"
    message = f"{prefix}: 후보 {result.eligible_missing}개, 검사 {result.scanned_files}개, 복구 {result.restored_count}개"
    if skipped:
        message += f", 해시 없음 {skipped}개"
    return message


def count_folder_paths(paths: list[str], *, ignored_dir_names: set[str] | None = None) -> int:
    ignored_names = normalize_ignored_dir_names(ignored_dir_names or [])
    return sum(
        1
        for path in paths
        if Path(path).is_dir() and not should_ignore_directory(Path(path), ignored_names)
    )


def expand_import_paths(
    paths: list[str],
    *,
    include_folder_contents: bool,
    ignored_dir_names: set[str] | None = None,
) -> list[tuple[str, str]]:
    return build_import_plan(
        paths,
        include_folder_contents=include_folder_contents,
        ignored_dir_names=ignored_dir_names,
    ).entries


def execute_import_plan(
    database: DatabaseManager,
    import_plan: ImportPlan,
    *,
    progress_callback=None,
    should_cancel=None,
) -> dict[str, Any]:
    added_ids: list[int] = []
    node_ids_by_path: dict[str, int] = {}
    duplicate_count = 0
    first_duplicate: dict[str, Any] | None = None
    completed_steps = 0
    total_steps = import_plan_step_count(import_plan)
    cancelled = False

    for path, node_type in import_plan.entries:
        if should_cancel and should_cancel():
            cancelled = True
            break
        try:
            node_id = database.add_node(path, node_type=node_type)
            added_ids.append(node_id)
        except DuplicateNodeError as exc:
            duplicate_count += 1
            if first_duplicate is None:
                first_duplicate = exc.existing_node
            node_id = int(exc.existing_node["node_id"])
        node_ids_by_path[path] = node_id
        completed_steps += 1
        if progress_callback and progress_callback(completed_steps, total_steps, Path(path).name) is False:
            cancelled = True
            break

    contains_relation_count = 0
    if not cancelled:
        for folder_path, file_path in import_plan.contains_pairs:
            if should_cancel and should_cancel():
                cancelled = True
                break
            source_id = node_ids_by_path.get(folder_path)
            target_id = node_ids_by_path.get(file_path)
            if source_id is not None and target_id is not None:
                try:
                    database.add_relation(
                        source_id,
                        target_id,
                        relation_type_code="CONTAINS",
                        strength="HIGH",
                        source="SYSTEM",
                    )
                except DuplicateRelationError:
                    pass
                else:
                    contains_relation_count += 1
            completed_steps += 1
            if progress_callback and progress_callback(completed_steps, total_steps, Path(file_path).name) is False:
                cancelled = True
                break

    selected_id: int | None = None
    if import_plan.contains_pairs:
        selected_id = node_ids_by_path.get(import_plan.contains_pairs[0][0])
    if selected_id is None and added_ids:
        selected_id = added_ids[-1]

    return {
        "added_ids": added_ids,
        "node_ids_by_path": node_ids_by_path,
        "duplicate_count": duplicate_count,
        "first_duplicate": first_duplicate,
        "contains_relation_count": contains_relation_count,
        "selected_id": selected_id,
        "processed_count": completed_steps,
        "total_count": total_steps,
        "cancelled": cancelled,
    }


def import_plan_step_count(import_plan: ImportPlan) -> int:
    return len(import_plan.entries) + len(import_plan.contains_pairs)


def add_default_contains_relations(
    database: DatabaseManager,
    contains_pairs: list[tuple[str, str]],
    node_ids_by_path: dict[str, int],
) -> int:
    created_count = 0
    for folder_path, file_path in contains_pairs:
        source_id = node_ids_by_path.get(folder_path)
        target_id = node_ids_by_path.get(file_path)
        if source_id is None or target_id is None:
            continue
        try:
            database.add_relation(
                source_id,
                target_id,
                relation_type_code="CONTAINS",
                strength="HIGH",
                source="SYSTEM",
            )
        except DuplicateRelationError:
            continue
        created_count += 1
    return created_count


def build_import_plan(
    paths: list[str],
    *,
    include_folder_contents: bool,
    ignored_dir_names: set[str] | None = None,
) -> ImportPlan:
    entries: list[tuple[str, str]] = []
    contains_pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    seen_contains_pairs: set[tuple[str, str]] = set()
    ignored_names = normalize_ignored_dir_names(ignored_dir_names or DEFAULT_IGNORED_DIR_NAMES)

    def normalize_path(path: Path) -> str:
        return str(path.expanduser().resolve(strict=False))

    def add_entry(path: Path, node_type: str) -> None:
        normalized = normalize_path(path)
        if normalized in seen:
            return
        entries.append((normalized, node_type))
        seen.add(normalized)

    def add_contains_pair(folder_path: Path, file_path: Path) -> None:
        pair = (normalize_path(folder_path), normalize_path(file_path))
        if pair in seen_contains_pairs:
            return
        contains_pairs.append(pair)
        seen_contains_pairs.add(pair)

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            if should_ignore_directory(path, ignored_names):
                continue
            add_entry(path, "FOLDER")
            if include_folder_contents:
                for child_path, node_type, parent_path in iter_folder_entries(path, ignored_dir_names=ignored_names):
                    add_entry(child_path, node_type)
                    add_contains_pair(parent_path, child_path)
        else:
            add_entry(path, "FILE")

    return ImportPlan(entries=entries, contains_pairs=contains_pairs)


def iter_folder_entries(folder_path: Path, *, ignored_dir_names: set[str]):
    for root, dirnames, filenames in os.walk(folder_path):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not should_ignore_directory(Path(root) / dirname, ignored_dir_names)
        ]
        current_folder = Path(root)
        for dirname in dirnames:
            child_folder = current_folder / dirname
            yield child_folder, "FOLDER", current_folder
        for filename in filenames:
            yield current_folder / filename, "FILE", current_folder


def iter_folder_files(folder_path: Path):
    for child_path, node_type, _parent_path in iter_folder_entries(
        folder_path,
        ignored_dir_names=set(DEFAULT_IGNORED_DIR_NAMES),
    ):
        if node_type == "FILE":
            yield child_path


def normalize_ignored_dir_names(names) -> set[str]:
    return {str(name).strip() for name in names if str(name).strip()}


def should_ignore_directory(path: Path, ignored_dir_names: set[str]) -> bool:
    path_name = path.name.casefold()
    return any(path_name == ignored_name.casefold() for ignored_name in ignored_dir_names)


def is_valid_color(value: str) -> bool:
    return QColor(value).isValid()


def validate_filegraph_database(path: str | os.PathLike[str]) -> tuple[bool, str]:
    database_path = Path(path)
    if not database_path.is_file():
        return False, "선택한 DB 파일을 찾을 수 없습니다."

    required_tables = {"nodes", "relations", "relation_types", "settings"}
    try:
        connection = sqlite3.connect(database_path)
        try:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        return False, "SQLite DB 파일이 아니거나 파일이 손상되었습니다."
    except OSError as exc:
        return False, str(exc)

    table_names = {str(row[0]) for row in rows}
    missing_tables = sorted(required_tables - table_names)
    if missing_tables:
        return False, f"FileGraph DB에 필요한 테이블이 없습니다: {', '.join(missing_tables)}"
    return True, ""


def database_preimport_backup_path(target_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = target_path.with_name(f"{target_path.stem}.preimport-{timestamp}{target_path.suffix}")
    suffix_index = 1
    while candidate.exists():
        candidate = target_path.with_name(
            f"{target_path.stem}.preimport-{timestamp}-{suffix_index}{target_path.suffix}"
        )
        suffix_index += 1
    return candidate


def database_importing_path(target_path: Path) -> Path:
    return target_path.with_name(f"{target_path.name}.importing")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
