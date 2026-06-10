"""Export workflow previews from .ows files."""

from __future__ import annotations

import io
from pathlib import Path

from .qt import ensure_qapplication
from .registry import RegistryCatalog


def load_scheme(path: str | Path, catalog: RegistryCatalog | None = None):
    from orangecanvas.scheme import Scheme
    from orangecanvas.scheme.readwrite import scheme_load

    catalog = catalog or RegistryCatalog()
    scheme = Scheme()
    with Path(path).expanduser().open("rb") as stream:
        scheme_load(scheme, stream, registry=catalog.registry)
    return scheme


def export_png(workflow_path: str | Path, png_path: str | Path, scale: float = 1.5) -> Path:
    ensure_qapplication()
    from AnyQt.QtCore import QRectF
    from AnyQt.QtGui import QColor, QImage, QPainter
    from orangecanvas.canvas.scene import CanvasScene

    output = Path(png_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    catalog = RegistryCatalog()
    scheme = load_scheme(workflow_path, catalog)
    scene = CanvasScene()
    scene.set_registry(catalog.registry)
    scene.set_channel_names_visible(True)
    scene.set_node_animation_enabled(False)
    scene.set_scheme(scheme)
    scene.anchor_layout().activate()
    scene.clearSelection()

    rect = scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
    if rect.isNull():
        rect = QRectF(0, 0, 800, 480)

    width = max(1, int(rect.width() * scale))
    height = max(1, int(rect.height() * scale))
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor("white"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), rect)
    painter.end()

    if not image.save(str(output), "PNG"):
        raise RuntimeError(f"Could not save PNG: {output}")
    scene.clear()
    scene.deleteLater()
    return output


def export_svg(workflow_path: str | Path) -> str:
    ensure_qapplication()
    from orangecanvas.canvas.scene import CanvasScene, grab_svg

    catalog = RegistryCatalog()
    scheme = load_scheme(workflow_path, catalog)
    scene = CanvasScene()
    scene.set_registry(catalog.registry)
    scene.set_channel_names_visible(True)
    scene.set_node_animation_enabled(False)
    scene.set_scheme(scheme)
    scene.anchor_layout().activate()
    scene.clearSelection()
    svg = grab_svg(scene)
    scene.clear()
    scene.deleteLater()
    return svg
