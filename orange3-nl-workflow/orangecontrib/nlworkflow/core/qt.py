"""Qt helpers that work in both Canvas and headless tests."""

from __future__ import annotations

import os

_APP = None


def ensure_qapplication():
    """Return a QApplication, creating an offscreen one when needed."""
    global _APP
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from AnyQt.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app
