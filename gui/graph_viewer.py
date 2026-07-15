from __future__ import annotations

import math
import re
import sys
from pathlib import Path, PurePath
from typing import Any

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
)
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QApplication,
    QRubberBand,
)
from shiboken6 import isValid


NODE_COLORS = {
    "FILE": QColor("#2563EB"),
    "FOLDER": QColor("#059669"),
}

NODE_BACKGROUNDS = {
    "FILE": QColor("#EFF6FF"),
    "FOLDER": QColor("#ECFDF5"),
}

STATUS_COLORS = {
    "ACTIVE": None,
    "MISSING": QColor("#9CA3AF"),
    "DELETED": QColor("#6B7280"),
    "ACCESS_DENIED": QColor("#DC2626"),
}

STATUS_BACKGROUNDS = {
    "MISSING": QColor("#F3F4F6"),
    "DELETED": QColor("#E5E7EB"),
    "ACCESS_DENIED": QColor("#FEF2F2"),
}

STATUS_ICON_NAMES = {
    "MISSING": "missing",
    "ACCESS_DENIED": "access_denied",
}

EXTENSION_ICON_NAMES = {
    "pdf": "pdf",
    "doc": "doc",
    "docx": "doc",
    "hwp": "doc",
    "hwpx": "doc",
    "md": "doc",
    "odt": "doc",
    "rtf": "doc",
    "txt": "doc",
    "csv": "sheet",
    "ods": "sheet",
    "tsv": "sheet",
    "xls": "sheet",
    "xlsx": "sheet",
    "odp": "slide",
    "ppt": "slide",
    "pptx": "slide",
    "bmp": "image",
    "gif": "image",
    "heic": "image",
    "ico": "image",
    "jpeg": "image",
    "jpg": "image",
    "png": "image",
    "svg": "image",
    "tif": "image",
    "tiff": "image",
    "webp": "image",
    "aac": "audio",
    "flac": "audio",
    "m4a": "audio",
    "mp3": "audio",
    "ogg": "audio",
    "wav": "audio",
    "wma": "audio",
    "avi": "video",
    "flv": "video",
    "mkv": "video",
    "mov": "video",
    "mp4": "video",
    "mpeg": "video",
    "mpg": "video",
    "webm": "video",
    "wmv": "video",
    "7z": "archive",
    "bz2": "archive",
    "gz": "archive",
    "iso": "archive",
    "rar": "archive",
    "tar": "archive",
    "xz": "archive",
    "zip": "archive",
    "c": "code",
    "cc": "code",
    "cpp": "code",
    "cs": "code",
    "css": "code",
    "go": "code",
    "h": "code",
    "hpp": "code",
    "html": "code",
    "ipynb": "code",
    "java": "code",
    "js": "code",
    "jsx": "code",
    "kt": "code",
    "kts": "code",
    "php": "code",
    "py": "code",
    "rb": "code",
    "rs": "code",
    "scss": "code",
    "sh": "code",
    "swift": "code",
    "ts": "code",
    "tsx": "code",
    "vue": "code",
    "ini": "data",
    "json": "data",
    "log": "data",
    "toml": "data",
    "xml": "data",
    "yaml": "data",
    "yml": "data",
    "db": "db",
    "mdb": "db",
    "sql": "db",
    "sqlite": "db",
    "sqlite3": "db",
    "ai": "design",
    "blend": "design",
    "fig": "design",
    "indd": "design",
    "psd": "design",
    "sketch": "design",
    "xd": "design",
    "apk": "app",
    "app": "app",
    "appimage": "app",
    "bat": "app",
    "cmd": "app",
    "com": "app",
    "deb": "app",
    "dmg": "app",
    "exe": "app",
    "msi": "app",
    "pkg": "app",
    "ps1": "app",
    "rpm": "app",
}

STRENGTH_WIDTHS = {
    "HIGH": 3.0,
    "MEDIUM": 2.0,
    "LOW": 1.0,
}

DEFAULT_LABEL_FONT_SIZE = 11
MIN_LABEL_FONT_SIZE = 8
MAX_LABEL_FONT_SIZE = 24
LABEL_VISIBILITY_ALWAYS = "always"
LABEL_VISIBILITY_HOVER = "hover"
LABEL_VISIBILITY_MODES = {LABEL_VISIBILITY_ALWAYS, LABEL_VISIBILITY_HOVER}
NODE_LABEL_MODE_FOLDERS = "folders"
NODE_LABEL_MODE_FILES = "files"
NODE_LABEL_MODE_ALL = "all"
NODE_LABEL_MODE_HOVER = LABEL_VISIBILITY_HOVER
NODE_LABEL_VISIBILITY_MODES = {
    NODE_LABEL_MODE_FOLDERS,
    NODE_LABEL_MODE_FILES,
    NODE_LABEL_MODE_ALL,
    NODE_LABEL_MODE_HOVER,
}

ROOT_FOLDER_COLOR = QColor("#B45309")
ROOT_FOLDER_BACKGROUND = QColor("#FEF3C7")
HIGHLIGHT_BACKGROUND_LIGHTNESS = 185
GRAPH_FIT_PADDING_RATIO = 0.08
MIN_GRAPH_FIT_PADDING = 64.0
MAX_GRAPH_FIT_PADDING = 96.0
MIN_GRAPH_FIT_SIZE = 420.0
MIN_GRAPH_FIT_SCALE = 0.58
ICON_SIZE_RATIO = 0.62
LABEL_NODE_GAP = 8.0
EDGE_LABEL_OFFSET = 18.0
COLLAPSED_BADGE_DIAMETER = 20.0
NOTE_BADGE_DIAMETER = 9.0
MANUAL_NODE_GAP = 20.0
MANUAL_OVERLAP_ITERATIONS = 20
NODE_LABEL_MAX_LINE_LENGTH = 18
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets"


class GraphViewer(QGraphicsView):
    nodeSelected = Signal(dict)
    nodeActivated = Signal(dict)
    nodeContextMenuRequested = Signal(dict, QPoint)
    nodeMoved = Signal(int, float, float)
    pathsDropped = Signal(list)
    selectedNodesChanged = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.node_items: dict[int, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []
        self.label_font_size = DEFAULT_LABEL_FONT_SIZE
        self.node_label_visibility = LABEL_VISIBILITY_HOVER
        self.edge_label_visibility = LABEL_VISIBILITY_HOVER
        self.extension_icon_overrides: dict[str, str] = {}
        self.right_drag_origin: QPoint | None = None
        self.right_drag_selecting = False
        self.selection_rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())

        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor("#F8FAFC")))
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.scene.selectionChanged.connect(self._emit_selected_nodes_changed)

    def set_label_font_size(self, point_size: int) -> None:
        self.label_font_size = clamp_label_font_size(point_size)
        for node_item in self.node_items.values():
            node_item.set_label_font_size(self.label_font_size)
        for edge_item in self.edge_items:
            edge_item.set_label_font_size(self.label_font_size)

    def set_label_visibility_modes(self, *, node_mode: str | None = None, edge_mode: str | None = None) -> None:
        if node_mode is not None:
            self.node_label_visibility = normalize_node_label_visibility_mode(node_mode)
        if edge_mode is not None:
            self.edge_label_visibility = normalize_edge_label_visibility_mode(edge_mode)
        for node_item in self.node_items.values():
            node_item.sync_label_visibility()
        for edge_item in self.edge_items:
            edge_item.sync_label_visibility()

    def set_extension_icon_overrides(self, overrides: dict[str, str] | None) -> None:
        self.extension_icon_overrides = normalize_extension_icon_overrides(overrides or {})
        for node_item in self.node_items.values():
            node_item.icon_name = node_icon_name(node_item.node, self.extension_icon_overrides)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.SelectAll):
            self.select_all_nodes()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self.right_drag_origin = event.position().toPoint()
            self.right_drag_selecting = False
            self.selection_rubber_band.setGeometry(QRect(self.right_drag_origin, QSize()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.right_drag_origin is not None and event.buttons() & Qt.RightButton:
            current_position = event.position().toPoint()
            drag_distance = (current_position - self.right_drag_origin).manhattanLength()
            if self.right_drag_selecting or drag_distance >= QApplication.startDragDistance():
                self.right_drag_selecting = True
                self.selection_rubber_band.setGeometry(
                    QRect(self.right_drag_origin, current_position).normalized()
                )
                self.selection_rubber_band.show()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.RightButton and self.right_drag_origin is not None:
            release_position = event.position().toPoint()
            if self.right_drag_selecting:
                viewport_rect = QRect(self.right_drag_origin, release_position).normalized()
                scene_rect = self.mapToScene(viewport_rect).boundingRect()
                self.select_nodes_in_scene_rect(scene_rect)
                self.selection_rubber_band.hide()
            else:
                node_item = self.node_item_at(release_position)
                if node_item is not None:
                    self.nodeSelected.emit(dict(node_item.node))
                    self.nodeContextMenuRequested.emit(dict(node_item.node), mouse_event_global_position(event))
            self.right_drag_origin = None
            self.right_drag_selecting = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        event.accept()

    def dragEnterEvent(self, event) -> None:
        if local_paths_from_mime_data(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if local_paths_from_mime_data(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = local_paths_from_mime_data(event.mimeData())
        if paths:
            self.pathsDropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def render_graph(
        self,
        graph_data: dict[str, list[dict[str, Any]]],
        *,
        preserve_view: bool = False,
    ) -> None:
        previous_center = self.mapToScene(self.viewport().rect().center())
        previous_transform = self.transform()
        can_preserve_view = preserve_view and bool(self.node_items)
        signals_were_blocked = self.scene.blockSignals(True)
        try:
            self.node_items.clear()
            self.edge_items.clear()
            self.scene.clear()
        finally:
            self.scene.blockSignals(signals_were_blocked)

        nodes = graph_data.get("nodes", [])
        relations = graph_data.get("relations", [])

        for node in nodes:
            item = NodeItem(node, self)
            item.setPos(float(node.get("x", 0.0)), float(node.get("y", 0.0)))
            self.scene.addItem(item)
            self.node_items[node["node_id"]] = item

        parallel_offsets = relation_parallel_offsets(relations)
        for relation in relations:
            source_item = self.node_items.get(relation["source_id"])
            target_item = self.node_items.get(relation["target_id"])
            if not source_item or not target_item:
                continue
            self._add_edge(
                source_item,
                target_item,
                relation,
                parallel_offset=parallel_offsets.get(int(relation.get("relation_id") or 0), 0.0),
            )

        if nodes:
            self.position_node_labels()
            if can_preserve_view:
                graph_rect = self.graph_items_bounding_rect()
                padding = graph_fit_padding(graph_rect)
                scene_rect = graph_rect.adjusted(-padding, -padding, padding, padding)
                self.scene.setSceneRect(expand_rect_to_minimum_size(scene_rect, MIN_GRAPH_FIT_SIZE))
                self.setTransform(previous_transform)
                self.centerOn(previous_center)
            else:
                self.fit_graph_to_view()
        else:
            self.scene.setSceneRect(-400, -300, 800, 600)
            self.resetTransform()
            empty_item = QGraphicsTextItem("파일 추가 / 폴더 추가")
            empty_item.setDefaultTextColor(QColor("#64748B"))
            apply_label_font_size(empty_item, 13)
            rect = empty_item.boundingRect()
            empty_item.setPos(-rect.width() / 2, -rect.height() / 2)
            self.scene.addItem(empty_item)

    def focus_node(self, node_id: int) -> None:
        item = self.node_items.get(node_id)
        if item is None:
            return
        self.centerOn(item)
        item.setSelected(True)

    def focus_nodes(self, node_ids: list[int] | tuple[int, ...]) -> None:
        items = [self.node_items[node_id] for node_id in node_ids if node_id in self.node_items]
        if not items:
            return
        focus_rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            focus_rect = focus_rect.united(item.sceneBoundingRect())
        self.centerOn(focus_rect.center())

    def fit_graph_to_view(self) -> None:
        graph_rect = self.graph_items_bounding_rect()
        if graph_rect.isNull():
            return

        padding = graph_fit_padding(graph_rect)
        fit_rect = graph_rect.adjusted(-padding, -padding, padding, padding)
        fit_rect = expand_rect_to_minimum_size(fit_rect, MIN_GRAPH_FIT_SIZE)
        self.scene.setSceneRect(fit_rect)
        self.resetTransform()
        self.fitInView(fit_rect, Qt.KeepAspectRatio)
        if self.transform().m11() < MIN_GRAPH_FIT_SCALE:
            self.resetTransform()
            self.scale(MIN_GRAPH_FIT_SCALE, MIN_GRAPH_FIT_SCALE)
            self.centerOn(graph_rect.center())

    def graph_items_bounding_rect(self) -> QRectF:
        graph_items: list[QGraphicsItem] = [*self.node_items.values(), *self.edge_items]
        graph_items.extend(edge.arrow_item for edge in self.edge_items if edge.arrow_item is not None)
        if not graph_items:
            return QRectF()

        rect = QRectF(graph_items[0].sceneBoundingRect())
        for item in graph_items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        return rect

    def node_item_at(self, viewport_position: QPoint) -> "NodeItem | None":
        item = self.itemAt(viewport_position)
        while item is not None:
            if isinstance(item, NodeItem):
                return item
            item = item.parentItem()
        return None

    def select_nodes_in_scene_rect(self, scene_rect: QRectF) -> list[int]:
        selected_node_ids = []
        for node_id, node_item in self.node_items.items():
            is_selected = scene_rect.intersects(node_item.sceneBoundingRect())
            node_item.setSelected(is_selected)
            if is_selected:
                selected_node_ids.append(node_id)
        return selected_node_ids

    def select_all_nodes(self) -> list[int]:
        for node_item in self.node_items.values():
            node_item.setSelected(True)
        return self.selected_node_ids()

    def selected_node_ids(self) -> list[int]:
        selected_ids: list[int] = []
        deleted_ids: list[int] = []
        for node_id, node_item in self.node_items.items():
            if not isValid(node_item):
                deleted_ids.append(node_id)
                continue
            if node_item.isSelected():
                selected_ids.append(node_id)
        for node_id in deleted_ids:
            self.node_items.pop(node_id, None)
        return selected_ids

    def _emit_selected_nodes_changed(self) -> None:
        self.selectedNodesChanged.emit(self.selected_node_ids())

    def _add_edge(
        self,
        source_item: "NodeItem",
        target_item: "NodeItem",
        relation: dict[str, Any],
        *,
        parallel_offset: float = 0.0,
    ) -> None:
        edge_item = EdgeItem(source_item, target_item, relation, parallel_offset=parallel_offset)
        self.scene.addItem(edge_item)
        self.scene.addItem(edge_item.label_item)
        if edge_item.arrow_item is not None:
            self.scene.addItem(edge_item.arrow_item)
        source_item.add_edge(edge_item)
        target_item.add_edge(edge_item)
        self.edge_items.append(edge_item)
        edge_item.update_position()

    def position_node_labels(self) -> None:
        node_items = list(self.node_items.values())
        for node_item in node_items:
            node_item.position_label_best_effort(node_items, self.edge_items)

    def adjust_moved_nodes_after_drop(self, moved_nodes: list["NodeItem"]) -> None:
        if not moved_nodes:
            return
        if len(moved_nodes) == 1:
            self.resolve_single_node_overlap(moved_nodes[0])
            return
        self.resolve_group_overlap(moved_nodes)

    def resolve_single_node_overlap(self, moved_node: "NodeItem") -> None:
        for _iteration in range(MANUAL_OVERLAP_ITERATIONS):
            shifted = False
            for other_node in self.node_items.values():
                if other_node is moved_node:
                    continue
                shift = overlap_shift(moved_node, other_node)
                if shift is None:
                    continue
                moved_node.setPos(moved_node.pos() + shift)
                shifted = True
            if not shifted:
                break

    def resolve_group_overlap(self, moved_nodes: list["NodeItem"]) -> None:
        moved_set = set(moved_nodes)
        stationary_nodes = [node for node in self.node_items.values() if node not in moved_set]
        for _iteration in range(MANUAL_OVERLAP_ITERATIONS):
            total_shift = QPointF(0.0, 0.0)
            for moved_node in moved_nodes:
                for stationary_node in stationary_nodes:
                    shift = overlap_shift(moved_node, stationary_node)
                    if shift is not None:
                        total_shift += shift
            if manhattan_length(total_shift) < 1e-6:
                break
            for moved_node in moved_nodes:
                moved_node.setPos(moved_node.pos() + total_shift)


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, node: dict[str, Any], viewer: GraphViewer) -> None:
        self.node = node
        self.viewer = viewer
        radius = 34 if node.get("node_type") == "FOLDER" else 28
        self.radius = radius
        self.connected_edges: list[EdgeItem] = []
        super().__init__(-radius, -radius, radius * 2, radius * 2)

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(node_background_color(node)))
        self.setPen(node_pen(node))
        self.setZValue(10)

        self.icon_name = node_icon_name(node, viewer.extension_icon_overrides)
        self.icon_item: QGraphicsSvgItem | None = None
        icon_path = node_icon_path(node, viewer.extension_icon_overrides)
        if icon_path.exists():
            self.icon_item = QGraphicsSvgItem(str(icon_path), self)
            self.icon_item.setAcceptedMouseButtons(Qt.NoButton)
            self.icon_item.setZValue(1)
            self._position_icon()

        self.collapsed_badge_item: QGraphicsEllipseItem | None = None
        self.collapsed_badge_text: QGraphicsTextItem | None = None
        if node.get("is_collapsed"):
            self._create_collapsed_badge()

        self.note_badge_item: QGraphicsEllipseItem | None = None
        if node.get("note"):
            self._create_note_badge()

        self.label_item = QGraphicsTextItem(format_node_label(node.get("name", "")), self)
        self.label_item.setDefaultTextColor(QColor("#0F172A"))
        self.label_item.setTextWidth(-1)
        self.set_label_font_size(viewer.label_font_size)
        self.sync_label_visibility()

    def add_edge(self, edge: "EdgeItem") -> None:
        self.connected_edges.append(edge)

    def set_label_font_size(self, point_size: int) -> None:
        apply_label_font_size(self.label_item, point_size)
        self._position_label()

    def sync_label_visibility(self) -> None:
        self.label_item.setVisible(node_label_visible_without_hover(self.node, self.viewer.node_label_visibility))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.connected_edges:
                edge.update_position()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:
        if not node_label_visible_without_hover(self.node, self.viewer.node_label_visibility):
            self.label_item.setVisible(True)
        if event is not None:
            super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if not node_label_visible_without_hover(self.node, self.viewer.node_label_visibility):
            self.label_item.setVisible(False)
        if event is not None:
            super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.viewer.nodeSelected.emit(dict(self.node))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.viewer.nodeActivated.emit(dict(self.node))
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.viewer.nodeSelected.emit(dict(self.node))
        self.viewer.nodeContextMenuRequested.emit(dict(self.node), event.screenPos())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.viewer.adjust_moved_nodes_after_drop(self.moved_node_items())
        self.emit_moved_nodes()

    def moved_node_items(self) -> list["NodeItem"]:
        if self.isSelected():
            scene = self.scene()
            if scene is not None:
                selected_nodes = [item for item in scene.selectedItems() if isinstance(item, NodeItem)]
                if selected_nodes:
                    return selected_nodes
        return [self]

    def emit_moved_nodes(self) -> None:
        moved_nodes = self.moved_node_items()

        for node_item in moved_nodes:
            position = node_item.scenePos()
            self.viewer.nodeMoved.emit(node_item.node["node_id"], position.x(), position.y())

    def position_label_best_effort(self, node_items: list["NodeItem"], edge_items: list["EdgeItem"]) -> None:
        best_position = min(
            label_candidate_positions(self),
            key=lambda position: label_collision_score(self, position, node_items, edge_items),
        )
        self.label_item.setPos(best_position)

    def _position_label(self) -> None:
        label_rect = self.label_item.boundingRect()
        self.label_item.setPos(-label_rect.width() / 2, self.radius + LABEL_NODE_GAP)

    def _position_icon(self) -> None:
        if self.icon_item is None:
            return

        icon_rect = self.icon_item.boundingRect()
        if icon_rect.isNull():
            return

        icon_size = self.radius * 2 * ICON_SIZE_RATIO
        scale = icon_size / max(icon_rect.width(), icon_rect.height())
        self.icon_item.setScale(scale)
        self.icon_item.setPos(
            -icon_rect.width() * scale / 2,
            -icon_rect.height() * scale / 2,
        )

    def _create_collapsed_badge(self) -> None:
        count = max(1, int(self.node.get("collapsed_file_count") or 1))
        label = str(count) if count < 100 else "99+"
        diameter = COLLAPSED_BADGE_DIAMETER if count < 100 else COLLAPSED_BADGE_DIAMETER + 8.0
        x = self.radius - diameter * 0.55
        y = -self.radius - diameter * 0.05

        self.collapsed_badge_item = QGraphicsEllipseItem(x, y, diameter, COLLAPSED_BADGE_DIAMETER, self)
        self.collapsed_badge_item.setBrush(QBrush(QColor("#0F766E")))
        self.collapsed_badge_item.setPen(QPen(QColor("#FFFFFF"), 1.4))
        self.collapsed_badge_item.setAcceptedMouseButtons(Qt.NoButton)
        self.collapsed_badge_item.setZValue(3)

        self.collapsed_badge_text = QGraphicsTextItem(label, self)
        self.collapsed_badge_text.setDefaultTextColor(QColor("#FFFFFF"))
        self.collapsed_badge_text.setAcceptedMouseButtons(Qt.NoButton)
        self.collapsed_badge_text.setZValue(4)
        apply_label_font_size(self.collapsed_badge_text, 8)
        text_rect = self.collapsed_badge_text.boundingRect()
        self.collapsed_badge_text.setPos(
            x + (diameter - text_rect.width()) / 2,
            y + (COLLAPSED_BADGE_DIAMETER - text_rect.height()) / 2 - 1.0,
        )

    def _create_note_badge(self) -> None:
        diameter = NOTE_BADGE_DIAMETER
        x = self.radius - diameter * 0.7
        y = -self.radius + diameter * 0.15
        self.note_badge_item = QGraphicsEllipseItem(x, y, diameter, diameter, self)
        self.note_badge_item.setBrush(QBrush(QColor("#F97316")))
        self.note_badge_item.setPen(QPen(QColor("#FFFFFF"), 1.2))
        self.note_badge_item.setAcceptedMouseButtons(Qt.NoButton)
        self.note_badge_item.setZValue(5)


class EdgeItem(QGraphicsLineItem):
    def __init__(
        self,
        source_item: NodeItem,
        target_item: NodeItem,
        relation: dict[str, Any],
        *,
        parallel_offset: float = 0.0,
    ) -> None:
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.relation = relation
        self.parallel_offset = float(parallel_offset)
        self.color = QColor(relation.get("relation_type_color") or "#64748B")
        self.setPen(QPen(self.color, edge_width(relation)))
        self.setAcceptHoverEvents(True)
        self.setZValue(-10)

        self.label_item = QGraphicsTextItem(relation.get("relation_type_name") or "")
        self.label_item.setDefaultTextColor(QColor("#334155"))
        self.label_item.setZValue(-3)

        self.arrow_item: QGraphicsPolygonItem | None = None
        if relation.get("is_directional"):
            self.arrow_item = QGraphicsPolygonItem()
            self.arrow_item.setBrush(QBrush(self.color))
            self.arrow_item.setPen(QPen(self.color, 1))
            self.arrow_item.setZValue(-4)
        self.set_label_font_size(source_item.viewer.label_font_size)
        self.sync_label_visibility()

    def set_label_font_size(self, point_size: int) -> None:
        apply_label_font_size(self.label_item, point_size)
        self.update_position()

    def sync_label_visibility(self) -> None:
        self.label_item.setVisible(self.source_item.viewer.edge_label_visibility == LABEL_VISIBILITY_ALWAYS)

    def update_position(self) -> None:
        source_point = self.source_item.scenePos()
        target_point = self.target_item.scenePos()
        dx = target_point.x() - source_point.x()
        dy = target_point.y() - source_point.y()
        distance = math.hypot(dx, dy)
        if distance > 1e-6 and self.parallel_offset:
            offset_x = -dy / distance * self.parallel_offset
            offset_y = dx / distance * self.parallel_offset
            source_point += QPointF(offset_x, offset_y)
            target_point += QPointF(offset_x, offset_y)
        self.setLine(source_point.x(), source_point.y(), target_point.x(), target_point.y())

        midpoint = QPointF(
            (source_point.x() + target_point.x()) / 2,
            (source_point.y() + target_point.y()) / 2,
        )
        offset = edge_label_offset(source_point, target_point)
        label_rect = self.label_item.boundingRect()
        self.label_item.setPos(
            midpoint.x() + offset.x() - label_rect.width() / 2,
            midpoint.y() + offset.y() - label_rect.height() / 2,
        )

        if self.arrow_item is not None:
            self.arrow_item.setPolygon(make_arrow_polygon(source_point, target_point, self.target_item.radius))

    def hoverEnterEvent(self, event) -> None:
        if self.source_item.viewer.edge_label_visibility == LABEL_VISIBILITY_HOVER:
            self.label_item.setVisible(True)
        if event is not None:
            super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if self.source_item.viewer.edge_label_visibility == LABEL_VISIBILITY_HOVER:
            self.label_item.setVisible(False)
        if event is not None:
            super().hoverLeaveEvent(event)

    def shape(self) -> QPainterPath:
        path = super().shape()
        stroker = QPainterPathStroker()
        stroker.setWidth(max(12.0, edge_width(self.relation) + 8.0))
        return stroker.createStroke(path)


def relation_parallel_offsets(relations: list[dict[str, Any]], *, spacing: float = 16.0) -> dict[int, float]:
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for relation in relations:
        source_id = int(relation["source_id"])
        target_id = int(relation["target_id"])
        grouped.setdefault(tuple(sorted((source_id, target_id))), []).append(relation)

    offsets: dict[int, float] = {}
    for grouped_relations in grouped.values():
        ordered = sorted(grouped_relations, key=lambda relation: int(relation.get("relation_id") or 0))
        midpoint = (len(ordered) - 1) / 2.0
        for index, relation in enumerate(ordered):
            relation_id = int(relation.get("relation_id") or 0)
            offsets[relation_id] = (index - midpoint) * spacing
    return offsets


def node_color(node: dict[str, Any]) -> QColor:
    status_color = STATUS_COLORS.get(node.get("status"))
    if status_color is not None:
        return status_color
    highlight_color = normalized_color(node.get("highlight_color"))
    if highlight_color is not None:
        return highlight_color
    if node.get("is_collapsed"):
        return QColor("#0F766E")
    if node.get("is_root_folder"):
        return ROOT_FOLDER_COLOR
    override_color = normalized_color(node.get("type_color"))
    if override_color is not None:
        return override_color
    return NODE_COLORS.get(node.get("node_type"), QColor("#2563EB"))


def node_background_color(node: dict[str, Any]) -> QColor:
    status_background = STATUS_BACKGROUNDS.get(node.get("status"))
    if status_background is not None:
        return status_background
    highlight_color = normalized_color(node.get("highlight_color"))
    if highlight_color is not None:
        return highlight_color.lighter(HIGHLIGHT_BACKGROUND_LIGHTNESS)
    if node.get("is_collapsed"):
        return QColor("#D1FAE5")
    if node.get("is_root_folder"):
        return ROOT_FOLDER_BACKGROUND
    return NODE_BACKGROUNDS.get(node.get("node_type"), QColor("#F8FAFC"))


def node_pen(node: dict[str, Any]) -> QPen:
    pen = QPen(node_color(node), 3.0 if node.get("is_collapsed") else 2.0)
    if node.get("is_collapsed"):
        pen.setStyle(Qt.DashLine)
    return pen


def node_icon_name(node: dict[str, Any], overrides: dict[str, str] | None = None) -> str:
    status_icon = STATUS_ICON_NAMES.get(str(node.get("status") or "").upper())
    if status_icon is not None:
        return status_icon

    if str(node.get("node_type") or "").upper() == "FOLDER":
        return "folder"

    extension = node_extension(node)
    if overrides and extension in overrides:
        return overrides[extension]
    return EXTENSION_ICON_NAMES.get(extension, "file")


def node_icon_path(node: dict[str, Any], overrides: dict[str, str] | None = None) -> Path:
    icon_path = ASSETS_DIR / f"{node_icon_name(node, overrides)}.svg"
    if icon_path.exists():
        return icon_path
    return ASSETS_DIR / "file.svg"


def node_extension(node: dict[str, Any]) -> str:
    for key in ("path", "name"):
        value = str(node.get(key) or "")
        if not value:
            continue
        suffix = PurePath(value).suffix.lower()
        if suffix:
            return suffix.removeprefix(".")
    return ""


def normalized_color(value: Any) -> QColor | None:
    if not value:
        return None
    color = QColor(str(value))
    return color if color.isValid() else None


def normalize_extension_icon_overrides(overrides: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for extension, icon_name in overrides.items():
        extension_key = str(extension).strip().lower().removeprefix(".")
        icon_key = str(icon_name).strip().lower()
        if not extension_key or not icon_key:
            continue
        normalized[extension_key] = icon_key
    return normalized


def format_node_label(name: Any, *, max_line_length: int = NODE_LABEL_MAX_LINE_LENGTH) -> str:
    raw_name = str(name or "")
    if not raw_name:
        return ""

    suffix = PurePath(raw_name).suffix
    stem = raw_name[: -len(suffix)] if suffix else raw_name
    lines = natural_label_lines(stem, max_line_length=max_line_length)
    if suffix:
        if lines and len(lines[-1]) + len(suffix) <= max_line_length:
            lines[-1] += suffix
        else:
            lines.append(suffix)
    return "\n".join(line for line in lines if line) or raw_name


def natural_label_lines(value: str, *, max_line_length: int) -> list[str]:
    if not value:
        return []

    chunks = split_label_chunks(value)
    lines: list[str] = []
    current = ""
    for chunk in chunks:
        if not chunk:
            continue
        if current and len(current) + len(chunk) > max_line_length:
            lines.append(current.rstrip())
            current = chunk.lstrip()
        else:
            current += chunk
    if current:
        lines.append(current.rstrip())
    return lines or [value]


def split_label_chunks(value: str) -> list[str]:
    parts = re.split(r"([ _-]+)", value)
    chunks: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if index + 1 < len(parts) and re.fullmatch(r"[ _-]+", parts[index + 1] or ""):
            chunks.append(part + parts[index + 1])
            index += 2
        else:
            chunks.append(part)
            index += 1
    return chunks


def edge_width(relation: dict[str, Any]) -> float:
    return STRENGTH_WIDTHS.get(str(relation.get("strength", "MEDIUM")).upper(), 2.0)


def clamp_label_font_size(point_size: int) -> int:
    return max(MIN_LABEL_FONT_SIZE, min(MAX_LABEL_FONT_SIZE, int(point_size)))


def normalize_label_visibility_mode(mode: str) -> str:
    return normalize_edge_label_visibility_mode(mode)


def normalize_edge_label_visibility_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    return normalized if normalized in LABEL_VISIBILITY_MODES else LABEL_VISIBILITY_HOVER


def normalize_node_label_visibility_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized == LABEL_VISIBILITY_ALWAYS:
        return NODE_LABEL_MODE_ALL
    return normalized if normalized in NODE_LABEL_VISIBILITY_MODES else NODE_LABEL_MODE_HOVER


def node_label_visible_without_hover(node: dict[str, Any], mode: str) -> bool:
    normalized = normalize_node_label_visibility_mode(mode)
    node_type = str(node.get("node_type") or "").upper()
    if normalized == NODE_LABEL_MODE_ALL:
        return True
    if normalized == NODE_LABEL_MODE_FOLDERS:
        return node_type == "FOLDER"
    if normalized == NODE_LABEL_MODE_FILES:
        return node_type == "FILE"
    return False


def apply_label_font_size(text_item: QGraphicsTextItem, point_size: int) -> None:
    font = text_item.font()
    font.setPointSize(clamp_label_font_size(point_size))
    text_item.setFont(font)


def label_candidate_positions(node_item: NodeItem) -> list[QPointF]:
    label_rect = node_item.label_item.boundingRect()
    width = label_rect.width()
    height = label_rect.height()
    radius = node_item.radius
    gap = LABEL_NODE_GAP
    return [
        QPointF(-width / 2, radius + gap),
        QPointF(-width / 2, -radius - gap - height),
        QPointF(radius + gap, -height / 2),
        QPointF(-radius - gap - width, -height / 2),
    ]


def label_collision_score(
    node_item: NodeItem,
    label_position: QPointF,
    node_items: list[NodeItem],
    edge_items: list[EdgeItem],
) -> float:
    label_rect = node_item.label_item.boundingRect()
    local_rect = QRectF(label_position.x(), label_position.y(), label_rect.width(), label_rect.height())
    scene_rect = node_item.mapToScene(local_rect).boundingRect()
    score = 0.0

    for other_node in node_items:
        if other_node is node_item:
            continue
        score += rect_overlap_area(scene_rect, other_node.sceneBoundingRect()) * 4.0

    center = scene_rect.center()
    for edge_item in edge_items:
        line = edge_item.line()
        if point_to_segment_distance(center, line.x1(), line.y1(), line.x2(), line.y2()) < 12.0:
            score += 500.0

    return score


def rect_overlap_area(first: QRectF, second: QRectF) -> float:
    overlap = first.intersected(second)
    if overlap.isNull():
        return 0.0
    return max(0.0, overlap.width()) * max(0.0, overlap.height())


def point_to_segment_distance(point: QPointF, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-6:
        return math.hypot(point.x() - x1, point.y() - y1)

    t = ((point.x() - x1) * dx + (point.y() - y1) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy
    return math.hypot(point.x() - nearest_x, point.y() - nearest_y)


def edge_label_offset(source: QPointF, target: QPointF) -> QPointF:
    dx = target.x() - source.x()
    dy = target.y() - source.y()
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return QPointF(EDGE_LABEL_OFFSET, -EDGE_LABEL_OFFSET)

    px = -dy / length
    py = dx / length
    if py > 0 or (abs(py) < 1e-6 and px < 0):
        px = -px
        py = -py
    return QPointF(px * EDGE_LABEL_OFFSET, py * EDGE_LABEL_OFFSET)


def overlap_shift(moved_node: NodeItem, anchor_node: NodeItem) -> QPointF | None:
    moved_position = moved_node.scenePos()
    anchor_position = anchor_node.scenePos()
    dx = moved_position.x() - anchor_position.x()
    dy = moved_position.y() - anchor_position.y()
    distance = math.hypot(dx, dy)
    min_distance = moved_node.radius + anchor_node.radius + MANUAL_NODE_GAP
    overlap = min_distance - distance
    if overlap <= 0:
        return None

    if distance < 1e-6:
        ux, uy = deterministic_unit_vector(
            int(moved_node.node.get("node_id", 0)),
            int(anchor_node.node.get("node_id", 0)),
        )
    else:
        ux, uy = dx / distance, dy / distance
    return QPointF(ux * overlap, uy * overlap)


def deterministic_unit_vector(first_id: int, second_id: int) -> tuple[float, float]:
    angle = ((first_id * 31 + second_id * 17) % 360) * math.pi / 180.0
    return math.cos(angle), math.sin(angle)


def manhattan_length(point: QPointF) -> float:
    return abs(point.x()) + abs(point.y())


def graph_fit_padding(rect: QRectF) -> float:
    proportional_padding = max(rect.width(), rect.height()) * GRAPH_FIT_PADDING_RATIO
    return max(MIN_GRAPH_FIT_PADDING, min(MAX_GRAPH_FIT_PADDING, proportional_padding))


def expand_rect_to_minimum_size(rect: QRectF, minimum_size: float) -> QRectF:
    expanded = QRectF(rect)
    if expanded.width() < minimum_size:
        delta = (minimum_size - expanded.width()) / 2
        expanded.adjust(-delta, 0, delta, 0)
    if expanded.height() < minimum_size:
        delta = (minimum_size - expanded.height()) / 2
        expanded.adjust(0, -delta, 0, delta)
    return expanded


def mouse_event_global_position(event) -> QPoint:
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()


def local_paths_from_mime_data(mime_data: QMimeData) -> list[str]:
    if not mime_data.hasUrls():
        return []

    paths: list[str] = []
    seen: set[str] = set()
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        path = url.toLocalFile()
        if not path or path in seen:
            continue
        paths.append(path)
        seen.add(path)
    return paths


def make_arrow_polygon(source: QPointF, target: QPointF, target_radius: float) -> QPolygonF:
    dx = target.x() - source.x()
    dy = target.y() - source.y()
    length = math.hypot(dx, dy)
    if length < 1:
        return QPolygonF()

    ux = dx / length
    uy = dy / length
    arrow_tip = QPointF(target.x() - ux * target_radius, target.y() - uy * target_radius)
    left = QPointF(
        arrow_tip.x() - ux * 14 - uy * 6,
        arrow_tip.y() - uy * 14 + ux * 6,
    )
    right = QPointF(
        arrow_tip.x() - ux * 14 + uy * 6,
        arrow_tip.y() - uy * 14 - ux * 6,
    )
    return QPolygonF([arrow_tip, left, right])
