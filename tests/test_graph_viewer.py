import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, QPoint, QRectF, QUrl
from PySide6.QtWidgets import QApplication

from gui.graph_viewer import (
    ASSETS_DIR,
    MAX_GRAPH_FIT_PADDING,
    MIN_GRAPH_FIT_PADDING,
    MIN_GRAPH_FIT_SIZE,
    GraphViewer,
    expand_rect_to_minimum_size,
    graph_fit_padding,
    local_paths_from_mime_data,
    node_icon_name,
    node_icon_path,
)


@pytest.fixture(scope="session")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_local_paths_from_mime_data_returns_unique_local_paths(app):
    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile("C:/workspace/brief.md"),
            QUrl.fromLocalFile("C:/workspace/brief.md"),
            QUrl("https://example.com/remote.md"),
            QUrl.fromLocalFile("C:/workspace/assets"),
        ]
    )

    assert local_paths_from_mime_data(mime_data) == [
        "C:/workspace/brief.md",
        "C:/workspace/assets",
    ]


def test_local_paths_from_mime_data_ignores_mime_without_urls(app):
    assert local_paths_from_mime_data(QMimeData()) == []


@pytest.mark.parametrize(
    ("node", "icon_name"),
    [
        ({"name": "folder", "node_type": "FOLDER", "status": "ACTIVE"}, "folder"),
        ({"name": "report.pdf", "node_type": "FILE", "status": "ACTIVE"}, "pdf"),
        ({"name": "notes.md", "node_type": "FILE", "status": "ACTIVE"}, "doc"),
        ({"name": "budget.xlsx", "node_type": "FILE", "status": "ACTIVE"}, "sheet"),
        ({"name": "deck.pptx", "node_type": "FILE", "status": "ACTIVE"}, "slide"),
        ({"name": "photo.webp", "node_type": "FILE", "status": "ACTIVE"}, "image"),
        ({"name": "song.flac", "node_type": "FILE", "status": "ACTIVE"}, "audio"),
        ({"name": "movie.mkv", "node_type": "FILE", "status": "ACTIVE"}, "video"),
        ({"name": "archive.7z", "node_type": "FILE", "status": "ACTIVE"}, "archive"),
        ({"name": "main.py", "node_type": "FILE", "status": "ACTIVE"}, "code"),
        ({"name": "config.json", "node_type": "FILE", "status": "ACTIVE"}, "data"),
        ({"name": "database.sqlite3", "node_type": "FILE", "status": "ACTIVE"}, "db"),
        ({"name": "mockup.fig", "node_type": "FILE", "status": "ACTIVE"}, "design"),
        ({"name": "setup.exe", "node_type": "FILE", "status": "ACTIVE"}, "app"),
        ({"name": "unknown.custom", "node_type": "FILE", "status": "ACTIVE"}, "file"),
        ({"name": "missing.pdf", "node_type": "FILE", "status": "MISSING"}, "missing"),
        ({"name": "private.pdf", "node_type": "FILE", "status": "ACCESS_DENIED"}, "access_denied"),
    ],
)
def test_node_icon_name_matches_type_status_and_extension(node, icon_name):
    assert node_icon_name(node) == icon_name
    assert node_icon_path(node) == ASSETS_DIR / f"{icon_name}.svg"


def test_graph_nodes_load_svg_icon_items(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {
                    "node_id": 1,
                    "name": "report.pdf",
                    "path": "C:/workspace/report.pdf",
                    "node_type": "FILE",
                    "status": "ACTIVE",
                    "x": 0,
                    "y": 0,
                },
                {
                    "node_id": 2,
                    "name": "assets",
                    "path": "C:/workspace/assets",
                    "node_type": "FOLDER",
                    "status": "ACTIVE",
                    "x": 100,
                    "y": 0,
                },
            ],
            "relations": [],
        }
    )

    file_item = viewer.node_items[1]
    folder_item = viewer.node_items[2]

    assert file_item.icon_name == "pdf"
    assert file_item.icon_item is not None
    assert file_item.icon_item.renderer().isValid()
    assert folder_item.icon_name == "folder"
    assert folder_item.icon_item is not None
    assert folder_item.icon_item.renderer().isValid()


def test_node_and_edge_labels_are_hidden_until_hover(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "deck.pptx", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
            ],
            "relations": [
                {
                    "relation_id": 1,
                    "source_id": 1,
                    "target_id": 2,
                    "relation_type_name": "참고자료",
                    "relation_type_color": "#2563EB",
                    "is_directional": True,
                    "strength": "HIGH",
                }
            ],
        }
    )

    node_item = viewer.node_items[1]
    edge_item = viewer.edge_items[0]

    assert not node_item.label_item.isVisible()
    assert not edge_item.label_item.isVisible()

    node_item.hoverEnterEvent(None)
    edge_item.hoverEnterEvent(None)

    assert node_item.label_item.isVisible()
    assert edge_item.label_item.isVisible()

    node_item.hoverLeaveEvent(None)
    edge_item.hoverLeaveEvent(None)

    assert not node_item.label_item.isVisible()
    assert not edge_item.label_item.isVisible()


def test_label_font_size_applies_to_current_and_future_labels(app):
    viewer = GraphViewer()
    viewer.set_label_font_size(16)
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "deck.pptx", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
            ],
            "relations": [
                {
                    "relation_id": 1,
                    "source_id": 1,
                    "target_id": 2,
                    "relation_type_name": "Reference",
                    "relation_type_color": "#2563EB",
                    "is_directional": True,
                    "strength": "HIGH",
                }
            ],
        }
    )

    node_item = viewer.node_items[1]
    edge_item = viewer.edge_items[0]

    assert node_item.label_item.font().pointSize() == 16
    assert edge_item.label_item.font().pointSize() == 16

    viewer.set_label_font_size(13)

    assert node_item.label_item.font().pointSize() == 13
    assert edge_item.label_item.font().pointSize() == 13


def test_node_context_menu_request_emits_node_and_screen_position(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
            ],
            "relations": [],
        }
    )
    selected_nodes = []
    context_requests = []
    viewer.nodeSelected.connect(selected_nodes.append)
    viewer.nodeContextMenuRequested.connect(lambda node, position: context_requests.append((node, position)))
    event = FakeContextMenuEvent(QPoint(24, 36))

    viewer.node_items[1].contextMenuEvent(event)

    assert selected_nodes[-1]["node_id"] == 1
    assert context_requests == [(selected_nodes[-1], QPoint(24, 36))]
    assert event.accepted


def test_graph_fit_padding_uses_tighter_dynamic_bounds():
    assert graph_fit_padding(QRectF(0, 0, 100, 100)) == MIN_GRAPH_FIT_PADDING
    assert graph_fit_padding(QRectF(0, 0, 2000, 100)) == MAX_GRAPH_FIT_PADDING
    assert graph_fit_padding(QRectF(0, 0, 800, 200)) == 64.0


def test_expand_rect_to_minimum_size_keeps_center():
    rect = QRectF(10, 20, 100, 200)

    expanded = expand_rect_to_minimum_size(rect, MIN_GRAPH_FIT_SIZE)

    assert expanded.center() == rect.center()
    assert expanded.width() == MIN_GRAPH_FIT_SIZE
    assert expanded.height() == MIN_GRAPH_FIT_SIZE


def test_select_nodes_in_scene_rect_selects_intersecting_nodes(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "first.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "second.md", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
                {"node_id": 3, "name": "third.md", "node_type": "FILE", "status": "ACTIVE", "x": 320, "y": 0},
            ],
            "relations": [],
        }
    )

    selected_node_ids = viewer.select_nodes_in_scene_rect(QRectF(-40, -40, 180, 80))

    assert selected_node_ids == [1, 2]
    assert viewer.selected_node_ids() == [1, 2]
    assert viewer.node_items[1].isSelected()
    assert viewer.node_items[2].isSelected()
    assert not viewer.node_items[3].isSelected()


def test_selected_node_move_emits_positions_for_all_selected_nodes(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "first.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "second.md", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
            ],
            "relations": [],
        }
    )
    moved = []
    viewer.nodeMoved.connect(lambda node_id, x, y: moved.append((node_id, x, y)))
    viewer.node_items[1].setSelected(True)
    viewer.node_items[2].setSelected(True)
    viewer.node_items[1].setPos(40, 30)
    viewer.node_items[2].setPos(140, 30)

    viewer.node_items[1].emit_moved_nodes()

    assert set(moved) == {
        (1, 40.0, 30.0),
        (2, 140.0, 30.0),
    }


def test_edges_follow_moved_nodes(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "deck.pptx", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
            ],
            "relations": [
                {
                    "relation_id": 1,
                    "source_id": 1,
                    "target_id": 2,
                    "relation_type_name": "참고자료",
                    "relation_type_color": "#2563EB",
                    "is_directional": True,
                    "strength": "HIGH",
                }
            ],
        }
    )

    node_item = viewer.node_items[1]
    edge_item = viewer.edge_items[0]
    node_item.setPos(40, 30)

    assert edge_item.line().x1() == 40
    assert edge_item.line().y1() == 30
    assert edge_item.line().x2() == 100
    assert edge_item.line().y2() == 0
    assert not edge_item.arrow_item.polygon().isEmpty()


class FakeContextMenuEvent:
    def __init__(self, screen_position: QPoint) -> None:
        self.screen_position = screen_position
        self.accepted = False

    def screenPos(self) -> QPoint:
        return self.screen_position

    def accept(self) -> None:
        self.accepted = True
