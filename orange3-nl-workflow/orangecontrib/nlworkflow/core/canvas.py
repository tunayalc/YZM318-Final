"""Open generated workflows in Orange Canvas and execute them headlessly."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _is_prompt_builder_node(node) -> bool:
    desc = getattr(node, "description", None)
    qualified_name = getattr(desc, "qualified_name", "")
    name = getattr(desc, "name", "")
    return (
        name == "Prompt Workflow Builder"
        or qualified_name.endswith(".OWPromptWorkflowBuilder")
    )


def _merge_generated_workflow(window, workflow_path: str) -> str:
    from orangecanvas.scheme import SchemeLink, SchemeNode

    from .exporter import load_scheme

    current = window.current_document().scheme()
    generated = load_scheme(workflow_path)
    preserved = [node for node in current.nodes if _is_prompt_builder_node(node)]

    for node in list(current.nodes):
        if not _is_prompt_builder_node(node):
            current.remove_node(node)

    offset_x = 0
    if preserved and generated.nodes:
        builder_right = max(node.position[0] for node in preserved) + 280
        generated_left = min(node.position[0] for node in generated.nodes)
        offset_x = max(0, builder_right - generated_left)

    node_map = {}
    for node in generated.nodes:
        position = (node.position[0] + offset_x, node.position[1])
        cloned = SchemeNode(
            node.description,
            title=node.title,
            position=position,
            properties=node.properties,
        )
        current.add_node(cloned)
        node_map[node] = cloned

    for link in generated.links:
        current.add_link(
            SchemeLink(
                node_map[link.source_node],
                link.source_channel,
                node_map[link.sink_node],
                link.sink_channel,
                enabled=link.enabled,
                properties=link.properties,
            )
        )

    window.raise_()
    window.activateWindow()
    return "Updated generated workflow on Canvas and kept Prompt Workflow Builder."


def open_in_canvas(
    workflow_path: str | Path,
    *,
    replace_current: bool = False,
    merge_current: bool = False,
) -> str:
    path = str(Path(workflow_path).expanduser().resolve())
    try:
        from AnyQt.QtWidgets import QApplication
        from orangecanvas.application.canvasmain import CanvasMainWindow

        app = QApplication.instance()
        if app is not None:
            windows = [
                widget
                for widget in app.topLevelWidgets()
                if isinstance(widget, CanvasMainWindow) and widget.isVisible()
            ]
            if replace_current and windows:
                window = app.activeWindow()
                if not isinstance(window, CanvasMainWindow):
                    window = windows[0]
                window.load_scheme(path)
                window.raise_()
                window.activateWindow()
                return "Opened generated workflow on the current Canvas."

            if merge_current and windows:
                window = app.activeWindow()
                if not isinstance(window, CanvasMainWindow):
                    window = windows[0]
                return _merge_generated_workflow(window, path)

            for widget in windows:
                if isinstance(widget, CanvasMainWindow):
                    widget.open_scheme_file(path)
                    return "Opened in the current Orange Canvas session."
    except Exception:
        pass

    subprocess.Popen([sys.executable, "-m", "Orange.canvas", path])
    return "Opened in a new Orange Canvas process."


def run_workflow(workflow_path: str | Path, *, timeout: int = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "Orange.canvas.run",
            "--log-level",
            "2",
            str(Path(workflow_path).expanduser().resolve()),
        ],
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
