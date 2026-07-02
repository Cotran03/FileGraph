from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStyle,
    QToolBar,
)

from core.database_manager import DatabaseManager, DuplicateNodeError, DuplicateRelationError
from core.file_integrity import (
    IntegrityScanResult,
    RediscoveryResult,
    rediscover_missing_nodes,
    scan_file_statuses as scan_database_file_statuses,
)
from core.graph_manager import GraphManager
from gui.control_panel import ControlPanel
from gui.graph_viewer import DEFAULT_LABEL_FONT_SIZE, GraphViewer, clamp_label_font_size
from gui.relation_dialog import RelationDialog


SKIPPED_RECURSIVE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "ENV",
    "node_modules",
    "__pycache__",
}

DUPLICATE_NODE_FOCUS = "focus"
DUPLICATE_NODE_RELATION = "relation"
DUPLICATE_NODE_CANCEL = "cancel"
GRAPH_LABEL_FONT_SIZE_SETTING = "graph_label_font_size"
MAX_LAYOUT_SEED = 2_147_483_647
NODE_CONTEXT_ADD_RELATION = "node_context_add_relation"
NODE_CONTEXT_EDIT_RELATIONS = "node_context_edit_relations"
NODE_CONTEXT_DELETE_NODE = "node_context_delete_node"


@dataclass(frozen=True)
class ImportPlan:
    entries: list[tuple[str, str]]
    contains_pairs: list[tuple[str, str]]


class MainWindow(QMainWindow):
    def __init__(self, db_path: str | os.PathLike[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FileGraph")
        self.resize(1280, 820)

        self.database = DatabaseManager(db_path)
        self.database.init_db()
        self.graph_manager = GraphManager(self.database)
        self.selected_node: dict[str, Any] | None = None
        self.graph_font_size = self._load_graph_font_size()

        self.graph_viewer = GraphViewer()
        self.graph_viewer.set_label_font_size(self.graph_font_size)
        self.control_panel = ControlPanel()
        self.control_panel.set_graph_font_size(self.graph_font_size)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("파일명, 경로, 카테고리 검색")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(320)

        self._build_toolbar()
        self._build_layout()
        self._connect_signals()
        self._apply_style()

        self.scan_file_statuses()
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

    def set_graph_font_size(self, point_size: int) -> None:
        self.graph_font_size = clamp_label_font_size(point_size)
        self.graph_viewer.set_label_font_size(self.graph_font_size)
        self.control_panel.set_graph_font_size(self.graph_font_size)
        self.database.set_setting(GRAPH_LABEL_FONT_SIZE_SETTING, str(self.graph_font_size))
        self.statusBar().showMessage(f"그래프 글자 크기 {self.graph_font_size}pt", 1200)

    def next_layout_seed(self) -> int:
        return random.randint(1, MAX_LAYOUT_SEED)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(self.style().standardIcon(QStyle.SP_FileIcon).actualSize(toolbar.iconSize()))
        self.addToolBar(toolbar)

        add_file = QAction(self.style().standardIcon(QStyle.SP_FileIcon), "파일 추가", self)
        add_file.triggered.connect(self.add_file_node)
        toolbar.addAction(add_file)

        add_folder = QAction(self.style().standardIcon(QStyle.SP_DirIcon), "폴더 추가", self)
        add_folder.triggered.connect(self.add_folder_node)
        toolbar.addAction(add_folder)

        toolbar.addSeparator()

        add_relation = QAction(self.style().standardIcon(QStyle.SP_ArrowRight), "관계 추가", self)
        add_relation.triggered.connect(self.add_relation)
        toolbar.addAction(add_relation)

        toolbar.addSeparator()
        toolbar.addWidget(self.search_input)

        search_action = QAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView), "검색", self)
        search_action.triggered.connect(self.search_nodes)
        toolbar.addAction(search_action)

        clear_action = QAction(self.style().standardIcon(QStyle.SP_DialogResetButton), "전체 보기", self)
        clear_action.triggered.connect(self.show_full_graph)
        toolbar.addAction(clear_action)

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.graph_viewer)
        splitter.addWidget(self.control_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    def _connect_signals(self) -> None:
        self.search_input.returnPressed.connect(self.search_nodes)
        self.graph_viewer.nodeSelected.connect(self.on_node_selected)
        self.graph_viewer.nodeActivated.connect(self.open_node)
        self.graph_viewer.nodeContextMenuRequested.connect(self.show_node_context_menu)
        self.graph_viewer.nodeMoved.connect(self.on_node_moved)
        self.graph_viewer.pathsDropped.connect(self.add_dropped_paths)
        self.control_panel.refreshRequested.connect(self.reload_graph)
        self.control_panel.checkFilesRequested.connect(self.refresh_file_statuses)
        self.control_panel.locateMissingRequested.connect(self.locate_missing_files)
        self.control_panel.addRelationRequested.connect(self.add_relation)
        self.control_panel.deleteNodeRequested.connect(self.delete_node_or_selection)
        self.control_panel.focusDepthRequested.connect(self.show_focus_graph)
        self.control_panel.fullViewRequested.connect(self.show_full_graph)
        self.control_panel.editRelationRequested.connect(self.edit_relation)
        self.control_panel.deleteRelationRequested.connect(self.delete_relation)
        self.control_panel.graphFontSizeChanged.connect(self.set_graph_font_size)
        self.control_panel.sampleDataRequested.connect(self.create_sample_data)
        self.control_panel.resetLayoutRequested.connect(self.reset_layout)

    def show_full_graph(self) -> None:
        self.reload_graph()
        self.statusBar().showMessage("전체 그래프를 표시합니다.", 2500)

    def reload_graph(self) -> None:
        data = self.graph_manager.get_graph_data()
        self.graph_viewer.render_graph(data)
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        if self.selected_node:
            refreshed = self.database.get_node(self.selected_node["node_id"])
            if refreshed and refreshed.get("status") != "DELETED":
                self.selected_node = refreshed
                self.control_panel.show_node(refreshed)
                self.control_panel.show_relations(self.database.list_relations(node_id=refreshed["node_id"]))
            else:
                self.selected_node = None
                self.control_panel.show_node(None)
                self.control_panel.show_relations(self.database.list_relations())
        else:
            self.control_panel.show_node(None)
            self.control_panel.show_relations(self.database.list_relations())
        self.statusBar().showMessage("그래프를 불러왔습니다.", 2500)

    def scan_file_statuses(self) -> IntegrityScanResult:
        return scan_database_file_statuses(self.database)

    def refresh_file_statuses(self) -> None:
        result = self.scan_file_statuses()
        self.reload_graph()
        self.statusBar().showMessage(integrity_scan_status_message(result), 3500)

    def locate_missing_files(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "누락 파일을 찾을 폴더 선택")
        if not folder_path:
            return
        self.rediscover_missing_files([folder_path])

    def rediscover_missing_files(self, search_roots: list[str | os.PathLike[str]]) -> RediscoveryResult:
        result = rediscover_missing_nodes(self.database, search_roots)
        self.reload_graph()
        self.statusBar().showMessage(rediscovery_status_message(result), 3500)
        return result

    def show_focus_graph(self, depth: int) -> None:
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
        self.graph_viewer.render_graph(data)
        self.graph_viewer.focus_node(node["node_id"])
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        self.control_panel.show_node(node)
        self.control_panel.show_relations(self.database.list_relations(node_id=node["node_id"]))
        self.statusBar().showMessage(f"{node['name']} 기준 {depth}단계 포커스 보기", 2500)

    def search_nodes(self) -> None:
        query = self.search_input.text().strip()
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
        data = self.graph_manager.get_graph_data(nodes=nodes, relations=relations)
        self.graph_viewer.render_graph(data)
        self.control_panel.set_summary(len(data["nodes"]), len(data["relations"]))
        self.control_panel.show_relations(relations)
        self.statusBar().showMessage(f"검색 결과 {len(nodes)}개", 2500)
        if len(nodes) == 1:
            self.selected_node = nodes[0]
            self.control_panel.show_node(nodes[0])
            self.control_panel.show_relations(self.database.list_relations(node_id=nodes[0]["node_id"]))
            self.graph_viewer.focus_node(nodes[0]["node_id"])
        else:
            self.selected_node = None
            self.control_panel.show_node(None)

    def add_file_node(self) -> None:
        file_path, _filter = QFileDialog.getOpenFileName(self, "파일 추가")
        if file_path:
            self._add_node(file_path, node_type="FILE")

    def add_folder_node(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "폴더 추가")
        if folder_path:
            include_folder_contents = self.ask_folder_import_options(folder_count=1)
            if include_folder_contents is None:
                return
            self._add_import_paths(
                [folder_path],
                include_folder_contents=include_folder_contents,
                action_label="폴더",
            )

    def add_dropped_paths(self, paths: list[str]) -> None:
        folder_count = count_folder_paths(paths)
        include_folder_contents = False
        if folder_count:
            selected = self.ask_folder_import_options(folder_count=folder_count)
            if selected is None:
                self.statusBar().showMessage("드롭한 경로 추가를 취소했습니다.", 2500)
                return
            include_folder_contents = selected

        self._add_import_paths(
            paths,
            include_folder_contents=include_folder_contents,
            action_label="드롭한 경로",
        )

    def ask_folder_import_options(self, *, folder_count: int) -> bool | None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("폴더 추가")
        message_box.setIcon(QMessageBox.Question)
        message_box.setText(f"폴더 {folder_count}개를 노드로 추가합니다.")
        message_box.setInformativeText("내부 파일까지 함께 노드로 등록하려면 아래 옵션을 켜세요.")
        include_files_check = QCheckBox("내부 파일도 등록")
        include_files_check.setChecked(False)
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
        import_plan = build_import_plan(paths, include_folder_contents=include_folder_contents)

        for path, node_type in import_plan.entries:
            try:
                node_id = self.database.add_node(path, node_type=node_type)
                added_ids.append(node_id)
            except DuplicateNodeError as exc:
                duplicate_count += 1
                if first_duplicate is None:
                    first_duplicate = exc.existing_node
                node_id = int(exc.existing_node["node_id"])
            node_ids_by_path[path] = node_id

        contains_relation_count = self._add_default_contains_relations(import_plan.contains_pairs, node_ids_by_path)

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
        self.statusBar().showMessage(message, 3500)

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
        self.control_panel.show_relations(self.database.list_relations(node_id=refreshed["node_id"]))

    def create_sample_data(self) -> None:
        sample_root = Path.cwd() / "sample_workspace"
        paths = {
            "brief": sample_root / "campaign_brief.md",
            "deck": sample_root / "launch_deck.pptx",
            "assets": sample_root / "design_assets",
            "budget": sample_root / "budget.xlsx",
        }

        node_ids: dict[str, int] = {}
        for key, path in paths.items():
            node_type = "FOLDER" if key == "assets" else "FILE"
            node_ids[key] = self._ensure_sample_node(path, node_type=node_type)

        relation_specs = [
            ("deck", "brief", "REFERENCE", True, "HIGH", "발표 자료가 캠페인 기획서를 참고함"),
            ("deck", "assets", "GENERATED_FROM", True, "MEDIUM", "디자인 에셋을 사용해 발표 자료를 구성함"),
            ("brief", "budget", "RELATED", False, "MEDIUM", "기획서와 예산표가 같은 캠페인에 속함"),
        ]
        for source_key, target_key, relation_type, is_directional, strength, description in relation_specs:
            try:
                self.database.add_relation(
                    node_ids[source_key],
                    node_ids[target_key],
                    relation_type_code=relation_type,
                    is_directional=is_directional,
                    strength=strength,
                    description=description,
                )
            except DuplicateRelationError:
                pass

        self.reload_graph()
        self.statusBar().showMessage("샘플 그래프를 만들었습니다.", 3000)

    def reset_layout(self) -> None:
        for node in self.database.list_nodes():
            self.database.update_node_layout(node["node_id"], None, None)
        data = self.graph_manager.get_graph_data(seed=self.next_layout_seed())
        for node in data["nodes"]:
            self.database.update_node_layout(node["node_id"], node["x"], node["y"])
        self.reload_graph()
        self.statusBar().showMessage("수동 좌표를 초기화했습니다.", 2500)

    def add_relation(self) -> None:
        nodes = self.database.list_nodes()
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
            self.database.list_nodes(),
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

        menu.addSeparator()

        delete_label = "선택 노드 삭제" if len(self.context_delete_node_ids(node_id)) > 1 else "노드 삭제"
        delete_node_action = menu.addAction(delete_label)
        delete_node_action.setData(NODE_CONTEXT_DELETE_NODE)
        delete_node_action.triggered.connect(
            lambda _checked=False, node_id=node_id: self.delete_node_or_selection(node_id)
        )

        return menu

    def on_node_selected(self, node: dict[str, Any]) -> None:
        self.selected_node = node
        self.control_panel.show_node(node)
        self.control_panel.show_relations(self.database.list_relations(node_id=node["node_id"]))

    def on_node_moved(self, node_id: int, x: float, y: float) -> None:
        self.database.update_node_layout(node_id, x, y)
        self.statusBar().showMessage("노드 위치를 저장했습니다.", 1200)

    def open_node(self, node: dict[str, Any]) -> None:
        path = node.get("path")
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "파일 없음", "현재 경로에서 파일 또는 폴더를 찾을 수 없습니다.")
            return
        os.startfile(path)

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

    def _ensure_sample_node(self, path: Path, *, node_type: str) -> int:
        try:
            return self.database.add_node(path, node_type=node_type, name=path.name)
        except DuplicateNodeError as exc:
            return int(exc.existing_node["node_id"])

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
            QToolBar {
                background: #FFFFFF;
                border: 0;
                border-bottom: 1px solid #E2E8F0;
                padding: 6px;
                spacing: 8px;
            }
            QLineEdit {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 7px 10px;
                background: #FFFFFF;
                color: #0F172A;
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


def integrity_scan_status_message(result: IntegrityScanResult) -> str:
    if result.total == 0:
        return "확인할 노드가 없습니다."
    message = (
        f"파일 상태 확인: {result.total}개 확인, 변경 {result.changed_count}개 "
        f"(정상 {result.active}, 누락 {result.missing}, 접근 거부 {result.access_denied})"
    )
    if result.hashes_updated:
        message += f", 해시 갱신 {result.hashes_updated}개"
    return message


def rediscovery_status_message(result: RediscoveryResult) -> str:
    if result.total_missing == 0:
        return "복구할 누락 노드가 없습니다."
    if result.eligible_missing == 0:
        return "해시가 저장된 누락 파일이 없습니다."
    return (
        f"누락 파일 찾기: 후보 {result.eligible_missing}개, "
        f"검사 {result.scanned_files}개, 복구 {result.restored_count}개"
    )


def count_folder_paths(paths: list[str]) -> int:
    return sum(1 for path in paths if Path(path).is_dir())


def expand_import_paths(
    paths: list[str],
    *,
    include_folder_contents: bool,
) -> list[tuple[str, str]]:
    return build_import_plan(paths, include_folder_contents=include_folder_contents).entries


def build_import_plan(
    paths: list[str],
    *,
    include_folder_contents: bool,
) -> ImportPlan:
    entries: list[tuple[str, str]] = []
    contains_pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    seen_contains_pairs: set[tuple[str, str]] = set()

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
            add_entry(path, "FOLDER")
            if include_folder_contents:
                for file_path in iter_folder_files(path):
                    add_entry(file_path, "FILE")
                    add_contains_pair(path, file_path)
        else:
            add_entry(path, "FILE")

    return ImportPlan(entries=entries, contains_pairs=contains_pairs)


def iter_folder_files(folder_path: Path):
    for root, dirnames, filenames in os.walk(folder_path):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIPPED_RECURSIVE_DIR_NAMES
        ]
        for filename in filenames:
            yield Path(root) / filename
