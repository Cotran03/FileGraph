import os
import math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QMimeData, QPoint, QRectF, Qt, QUrl
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from gui.graph_viewer import (
    ASSETS_DIR,
    LABEL_VISIBILITY_ALWAYS,
    MANUAL_NODE_GAP,
    MAX_GRAPH_FIT_PADDING,
    MIN_GRAPH_FIT_PADDING,
    MIN_GRAPH_FIT_SIZE,
    NODE_LABEL_MODE_FILES,
    NODE_LABEL_MODE_FOLDERS,
    GraphViewer,
    expand_rect_to_minimum_size,
    format_node_label,
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


def test_node_icon_name_uses_extension_overrides():
    node = {"name": "schema.proto", "node_type": "FILE", "status": "ACTIVE"}

    assert node_icon_name(node, {"proto": "code"}) == "code"


def test_format_node_label_keeps_extension_unsplit():
    label = format_node_label("long_report-name_final.backup.tar", max_line_length=14)

    assert ".tar" in label.splitlines()
    assert all(line != ".t" for line in label.splitlines())


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


def test_label_visibility_modes_can_show_labels_without_hover(app):
    viewer = GraphViewer()
    viewer.set_label_visibility_modes(
        node_mode=LABEL_VISIBILITY_ALWAYS,
        edge_mode=LABEL_VISIBILITY_ALWAYS,
    )
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

    assert viewer.node_items[1].label_item.isVisible()
    assert viewer.edge_items[0].label_item.isVisible()


def test_node_label_visibility_can_target_file_or_folder_names(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "docs", "node_type": "FOLDER", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
            ],
            "relations": [],
        }
    )

    viewer.set_label_visibility_modes(node_mode=NODE_LABEL_MODE_FOLDERS)

    assert viewer.node_items[1].label_item.isVisible()
    assert not viewer.node_items[2].label_item.isVisible()

    viewer.set_label_visibility_modes(node_mode=NODE_LABEL_MODE_FILES)

    assert not viewer.node_items[1].label_item.isVisible()
    assert viewer.node_items[2].label_item.isVisible()


def test_selective_node_label_modes_still_show_hidden_names_on_hover(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "docs", "node_type": "FOLDER", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "brief.md", "node_type": "FILE", "status": "ACTIVE", "x": 100, "y": 0},
            ],
            "relations": [],
        }
    )

    folder_item = viewer.node_items[1]
    file_item = viewer.node_items[2]

    viewer.set_label_visibility_modes(node_mode=NODE_LABEL_MODE_FOLDERS)

    assert folder_item.label_item.isVisible()
    assert not file_item.label_item.isVisible()

    file_item.hoverEnterEvent(None)
    assert file_item.label_item.isVisible()
    file_item.hoverLeaveEvent(None)
    assert not file_item.label_item.isVisible()

    viewer.set_label_visibility_modes(node_mode=NODE_LABEL_MODE_FILES)

    assert not folder_item.label_item.isVisible()
    assert file_item.label_item.isVisible()

    folder_item.hoverEnterEvent(None)
    assert folder_item.label_item.isVisible()
    folder_item.hoverLeaveEvent(None)
    assert not folder_item.label_item.isVisible()


def test_collapsed_folder_node_gets_distinct_badge_and_pen(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {
                    "node_id": 1,
                    "name": "assets",
                    "node_type": "FOLDER",
                    "status": "ACTIVE",
                    "x": 0,
                    "y": 0,
                    "is_collapsed": True,
                    "collapsed_file_count": 3,
                },
            ],
            "relations": [],
        }
    )

    folder_item = viewer.node_items[1]

    assert folder_item.collapsed_badge_item is not None
    assert folder_item.collapsed_badge_text is not None
    assert folder_item.collapsed_badge_text.toPlainText() == "3"
    assert folder_item.pen().style() == Qt.DashLine


def test_note_and_highlight_render_node_indicators(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {
                    "node_id": 1,
                    "name": "brief.md",
                    "node_type": "FILE",
                    "status": "ACTIVE",
                    "x": 0,
                    "y": 0,
                    "note": "check this",
                    "highlight_color": "#F97316",
                },
            ],
            "relations": [],
        }
    )

    item = viewer.node_items[1]

    assert item.note_badge_item is not None
    assert item.pen().color().name().upper() == "#F97316"


def test_root_folder_gets_distinct_visual(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {
                    "node_id": 1,
                    "name": "workspace",
                    "node_type": "FOLDER",
                    "status": "ACTIVE",
                    "x": 0,
                    "y": 0,
                    "is_root_folder": True,
                },
            ],
            "relations": [],
        }
    )

    assert viewer.node_items[1].pen().color().name().upper() == "#B45309"


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


def test_ctrl_a_selects_all_visible_nodes(app):
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
    event = QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.ControlModifier)

    viewer.keyPressEvent(event)

    assert viewer.selected_node_ids() == [1, 2]
    assert event.isAccepted()


def test_selected_node_ids_ignores_deleted_node_items(app):
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
    stale_items = dict(viewer.node_items)
    viewer.node_items[1].setSelected(True)

    signals_were_blocked = viewer.scene.blockSignals(True)
    try:
        viewer.scene.clear()
    finally:
        viewer.scene.blockSignals(signals_were_blocked)
    viewer.node_items = stale_items

    assert not isValid(stale_items[1])
    assert viewer.selected_node_ids() == []
    assert viewer.node_items == {}


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


def test_manual_overlap_resolution_moves_single_node_to_non_overlapping_position(app):
    viewer = GraphViewer()
    viewer.render_graph(
        {
            "nodes": [
                {"node_id": 1, "name": "first.md", "node_type": "FILE", "status": "ACTIVE", "x": 0, "y": 0},
                {"node_id": 2, "name": "second.md", "node_type": "FILE", "status": "ACTIVE", "x": 10, "y": 0},
            ],
            "relations": [],
        }
    )

    moved_node = viewer.node_items[2]
    viewer.resolve_single_node_overlap(moved_node)

    first_position = viewer.node_items[1].scenePos()
    moved_position = moved_node.scenePos()
    distance = math.hypot(moved_position.x() - first_position.x(), moved_position.y() - first_position.y())
    assert distance >= viewer.node_items[1].radius + moved_node.radius + MANUAL_NODE_GAP - 1e-6


def test_render_graph_can_preserve_zoom_and_center(app):
    viewer = GraphViewer()
    viewer.resize(800, 600)
    viewer.show()
    data = {
        "nodes": [
            {"node_id": 1, "name": "first.md", "node_type": "FILE", "status": "ACTIVE", "x": -300, "y": 0},
            {"node_id": 2, "name": "second.md", "node_type": "FILE", "status": "ACTIVE", "x": 300, "y": 0},
        ],
        "relations": [],
    }
    viewer.render_graph(data)
    viewer.scale(1.4, 1.4)
    viewer.centerOn(180, 0)
    app.processEvents()
    previous_scale = viewer.transform().m11()
    previous_center = viewer.mapToScene(viewer.viewport().rect().center())

    viewer.render_graph(data, preserve_view=True)
    app.processEvents()
    restored_center = viewer.mapToScene(viewer.viewport().rect().center())

    assert viewer.transform().m11() == pytest.approx(previous_scale)
    assert restored_center.x() == pytest.approx(previous_center.x(), abs=2.0)
    assert restored_center.y() == pytest.approx(previous_center.y(), abs=2.0)
    viewer.close()


class FakeContextMenuEvent:
    def __init__(self, screen_position: QPoint) -> None:
        self.screen_position = screen_position
        self.accepted = False

    def screenPos(self) -> QPoint:
        return self.screen_position

    def accept(self) -> None:
        self.accepted = True
