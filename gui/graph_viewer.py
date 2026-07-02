from __future__ import annotations

import math
import sys
from pathlib import Path, PurePath
from typing import Any

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
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
GRAPH_FIT_PADDING_RATIO = 0.08
MIN_GRAPH_FIT_PADDING = 64.0
MAX_GRAPH_FIT_PADDING = 96.0
MIN_GRAPH_FIT_SIZE = 420.0
ICON_SIZE_RATIO = 0.62
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "assets"


class GraphViewer(QGraphicsView):
    nodeSelected = Signal(dict)
    nodeActivated = Signal(dict)
    nodeContextMenuRequested = Signal(dict, QPoint)
    nodeMoved = Signal(int, float, float)
    pathsDropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.node_items: dict[int, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []
        self.label_font_size = DEFAULT_LABEL_FONT_SIZE
        self.right_drag_origin: QPoint | None = None
        self.right_drag_selecting = False
        self.selection_rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())

        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor("#F8FAFC")))
        self.setAcceptDrops(True)

    def set_label_font_size(self, point_size: int) -> None:
        self.label_font_size = clamp_label_font_size(point_size)
        for node_item in self.node_items.values():
            node_item.set_label_font_size(self.label_font_size)
        for edge_item in self.edge_items:
            edge_item.set_label_font_size(self.label_font_size)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

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

    def render_graph(self, graph_data: dict[str, list[dict[str, Any]]]) -> None:
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()

        nodes = graph_data.get("nodes", [])
        relations = graph_data.get("relations", [])

        for node in nodes:
            item = NodeItem(node, self)
            item.setPos(float(node.get("x", 0.0)), float(node.get("y", 0.0)))
            self.scene.addItem(item)
            self.node_items[node["node_id"]] = item

        for relation in relations:
            source_item = self.node_items.get(relation["source_id"])
            target_item = self.node_items.get(relation["target_id"])
            if not source_item or not target_item:
                continue
            self._add_edge(source_item, target_item, relation)

        if nodes:
            self.fit_graph_to_view()
        else:
            self.scene.setSceneRect(-400, -300, 800, 600)
            self.resetTransform()

    def focus_node(self, node_id: int) -> None:
        item = self.node_items.get(node_id)
        if item is None:
            return
        self.centerOn(item)
        item.setSelected(True)

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

    def selected_node_ids(self) -> list[int]:
        return [
            node_id
            for node_id, node_item in self.node_items.items()
            if node_item.isSelected()
        ]

    def _add_edge(self, source_item: "NodeItem", target_item: "NodeItem", relation: dict[str, Any]) -> None:
        edge_item = EdgeItem(source_item, target_item, relation)
        self.scene.addItem(edge_item)
        self.scene.addItem(edge_item.label_item)
        if edge_item.arrow_item is not None:
            self.scene.addItem(edge_item.arrow_item)
        source_item.add_edge(edge_item)
        target_item.add_edge(edge_item)
        self.edge_items.append(edge_item)
        edge_item.update_position()


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
        self.setPen(QPen(node_color(node), 2.0))
        self.setZValue(10)

        self.icon_name = node_icon_name(node)
        self.icon_item: QGraphicsSvgItem | None = None
        icon_path = node_icon_path(node)
        if icon_path.exists():
            self.icon_item = QGraphicsSvgItem(str(icon_path), self)
            self.icon_item.setAcceptedMouseButtons(Qt.NoButton)
            self.icon_item.setZValue(1)
            self._position_icon()

        self.label_item = QGraphicsTextItem(node.get("name", ""), self)
        self.label_item.setDefaultTextColor(QColor("#0F172A"))
        self.label_item.setTextWidth(130)
        self.label_item.setVisible(False)
        self.set_label_font_size(viewer.label_font_size)

    def add_edge(self, edge: "EdgeItem") -> None:
        self.connected_edges.append(edge)

    def set_label_font_size(self, point_size: int) -> None:
        apply_label_font_size(self.label_item, point_size)
        self._position_label()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.connected_edges:
                edge.update_position()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:
        self.label_item.setVisible(True)
        if event is not None:
            super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
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
        self.emit_moved_nodes()

    def emit_moved_nodes(self) -> None:
        moved_nodes = [self]
        scene = self.scene()
        if scene is not None and self.isSelected():
            selected_nodes = [item for item in scene.selectedItems() if isinstance(item, NodeItem)]
            if selected_nodes:
                moved_nodes = selected_nodes

        for node_item in moved_nodes:
            position = node_item.scenePos()
            self.viewer.nodeMoved.emit(node_item.node["node_id"], position.x(), position.y())

    def _position_label(self) -> None:
        label_rect = self.label_item.boundingRect()
        self.label_item.setPos(-label_rect.width() / 2, self.radius + 6)

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


class EdgeItem(QGraphicsLineItem):
    def __init__(self, source_item: NodeItem, target_item: NodeItem, relation: dict[str, Any]) -> None:
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.relation = relation
        self.color = QColor(relation.get("relation_type_color") or "#64748B")
        self.setPen(QPen(self.color, edge_width(relation)))
        self.setAcceptHoverEvents(True)
        self.setZValue(-10)

        self.label_item = QGraphicsTextItem(relation.get("relation_type_name") or "")
        self.label_item.setDefaultTextColor(QColor("#334155"))
        self.label_item.setVisible(False)
        self.label_item.setZValue(-3)

        self.arrow_item: QGraphicsPolygonItem | None = None
        if relation.get("is_directional"):
            self.arrow_item = QGraphicsPolygonItem()
            self.arrow_item.setBrush(QBrush(self.color))
            self.arrow_item.setPen(QPen(self.color, 1))
            self.arrow_item.setZValue(-4)
        self.set_label_font_size(source_item.viewer.label_font_size)

    def set_label_font_size(self, point_size: int) -> None:
        apply_label_font_size(self.label_item, point_size)
        self.update_position()

    def update_position(self) -> None:
        source_point = self.source_item.scenePos()
        target_point = self.target_item.scenePos()
        self.setLine(source_point.x(), source_point.y(), target_point.x(), target_point.y())

        midpoint = QPointF(
            (source_point.x() + target_point.x()) / 2,
            (source_point.y() + target_point.y()) / 2,
        )
        self.label_item.setPos(midpoint.x() + 6, midpoint.y() + 6)

        if self.arrow_item is not None:
            self.arrow_item.setPolygon(make_arrow_polygon(source_point, target_point, self.target_item.radius))

    def hoverEnterEvent(self, event) -> None:
        self.label_item.setVisible(True)
        if event is not None:
            super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.label_item.setVisible(False)
        if event is not None:
            super().hoverLeaveEvent(event)

    def shape(self) -> QPainterPath:
        path = super().shape()
        stroker = QPainterPathStroker()
        stroker.setWidth(max(12.0, edge_width(self.relation) + 8.0))
        return stroker.createStroke(path)


def node_color(node: dict[str, Any]) -> QColor:
    status_color = STATUS_COLORS.get(node.get("status"))
    if status_color is not None:
        return status_color
    return NODE_COLORS.get(node.get("node_type"), QColor("#2563EB"))


def node_background_color(node: dict[str, Any]) -> QColor:
    status_background = STATUS_BACKGROUNDS.get(node.get("status"))
    if status_background is not None:
        return status_background
    return NODE_BACKGROUNDS.get(node.get("node_type"), QColor("#F8FAFC"))


def node_icon_name(node: dict[str, Any]) -> str:
    status_icon = STATUS_ICON_NAMES.get(str(node.get("status") or "").upper())
    if status_icon is not None:
        return status_icon

    if str(node.get("node_type") or "").upper() == "FOLDER":
        return "folder"

    extension = node_extension(node)
    return EXTENSION_ICON_NAMES.get(extension, "file")


def node_icon_path(node: dict[str, Any]) -> Path:
    icon_path = ASSETS_DIR / f"{node_icon_name(node)}.svg"
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


def edge_width(relation: dict[str, Any]) -> float:
    return STRENGTH_WIDTHS.get(str(relation.get("strength", "MEDIUM")).upper(), 2.0)


def clamp_label_font_size(point_size: int) -> int:
    return max(MIN_LABEL_FONT_SIZE, min(MAX_LABEL_FONT_SIZE, int(point_size)))


def apply_label_font_size(text_item: QGraphicsTextItem, point_size: int) -> None:
    font = text_item.font()
    font.setPointSize(clamp_label_font_size(point_size))
    text_item.setFont(font)


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
