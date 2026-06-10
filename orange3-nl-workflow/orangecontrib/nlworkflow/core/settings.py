"""Build node properties using Orange widget settings where it matters."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from Orange.data import Table, Variable

from .qt import ensure_qapplication


def _close_widget(widget) -> None:
    widget.close()
    widget.deleteLater()


def _pack_widget(widget) -> dict:
    try:
        return widget.settingsHandler.pack_data(widget)
    finally:
        _close_widget(widget)


def file_properties(path: str | None) -> dict:
    ensure_qapplication()
    from Orange.data.io import FileFormat
    from Orange.widgets.data.owfile import OWFile
    from Orange.widgets.utils.filedialogs import RecentPath

    if not path:
        return {"source": OWFile.LOCAL_FILE}

    abs_path = os.path.abspath(os.path.expanduser(path))
    file_format = None
    try:
        file_format = FileFormat.get_reader(abs_path).qualified_name()
    except Exception:
        file_format = None
    recent_path = RecentPath(
        abs_path,
        None,
        None,
        title=os.path.basename(abs_path),
        file_format=file_format,
    )
    return {
        "recent_paths": [recent_path],
        "source": OWFile.LOCAL_FILE,
        "sheet_names": {},
        "url": "",
        "recent_urls": [],
        "__version__": OWFile.settings_version,
    }


def csv_import_properties(path: str | None) -> dict:
    ensure_qapplication()
    from AnyQt.QtCore import QMimeDatabase
    from Orange.widgets.data.owcsvimport import (
        OWCSVFileImport,
        default_options_for_mime_type,
    )

    widget = OWCSVFileImport()
    if path:
        abs_path = os.path.abspath(os.path.expanduser(path))
        if os.path.exists(abs_path):
            mime_type = QMimeDatabase().mimeTypeForFile(abs_path).name()
            options = default_options_for_mime_type(abs_path, mime_type)
            widget.set_selected_file(abs_path, options)
    return _pack_widget(widget)


def _all_domain_vars(table: Table) -> list[Variable]:
    return list(table.domain.attributes) + list(table.domain.class_vars) + list(
        table.domain.metas
    )


def _find_var(table: Table, name: str | None) -> Variable | None:
    if not name:
        return None
    lowered = name.casefold()
    for var in _all_domain_vars(table):
        if var.name.casefold() == lowered:
            return var
    return None


def select_columns_properties(
    table: Table | None,
    *,
    target_column: str | None,
    ignored_columns: Iterable[str] = (),
) -> dict:
    ensure_qapplication()
    from Orange.widgets.data.owselectcolumns import OWSelectAttributes

    widget = OWSelectAttributes()
    if table is None:
        return _pack_widget(widget)

    widget.set_data(table)
    widget.handleNewSignals()

    ignored = {name.casefold() for name in ignored_columns}
    target_var = _find_var(table, target_column) or table.domain.class_var
    features = []
    metas = []
    available = []
    class_vars = [target_var] if target_var is not None else []

    for var in _all_domain_vars(table):
        if var in class_vars:
            continue
        if var.name.casefold() in ignored:
            available.append(var)
        elif var.is_primitive():
            features.append(var)
        else:
            metas.append(var)

    widget.available_attrs[:] = available
    widget.used_attrs[:] = features
    widget.class_attrs[:] = class_vars
    widget.meta_attrs[:] = metas
    widget.update_domain_role_hints()
    widget.commit.now()
    return _pack_widget(widget)


def impute_properties(method: str = "average") -> dict:
    ensure_qapplication()
    from Orange.widgets.data.owimpute import Method, OWImpute

    widget = OWImpute()
    method_map = {
        "average": Method.Average,
        "mean": Method.Average,
        "model": Method.Model,
        "random": Method.Random,
        "drop": Method.Drop,
        "leave": Method.Leave,
    }
    widget._default_method_index = int(method_map.get(method.casefold(), Method.Average))
    return _pack_widget(widget)


def continuize_properties(method: str = "normalize01") -> dict:
    ensure_qapplication()
    from Orange.widgets.data.owcontinuize import (
        Continuize,
        DefaultKey,
        Normalize,
        OWContinuize,
    )

    widget = OWContinuize()
    method_map = {
        "standardize": Normalize.Standardize,
        "zscore": Normalize.Standardize,
        "normalize": Normalize.Normalize01,
        "normalize01": Normalize.Normalize01,
        "minmax": Normalize.Normalize01,
        "normalize11": Normalize.Normalize11,
        "leave": Normalize.Leave,
    }
    widget.disc_var_hints[DefaultKey] = Continuize.FirstAsBase
    widget.cont_var_hints[DefaultKey] = method_map.get(
        method.casefold(), Normalize.Normalize01
    )
    return _pack_widget(widget)


def test_and_score_properties() -> dict:
    ensure_qapplication()
    from Orange.widgets.evaluate.owtestandscore import OWTestAndScore

    widget = OWTestAndScore()
    widget.resampling = OWTestAndScore.KFold
    widget.n_folds = 2
    widget.cv_stratified = True
    return _pack_widget(widget)


def simple_widget_properties(widget_class) -> dict:
    ensure_qapplication()
    widget = widget_class()
    return _pack_widget(widget)


def load_table(path: str | None) -> Table | None:
    if not path:
        return None
    expanded = Path(path).expanduser()
    if not expanded.exists():
        return None
    return Table(str(expanded))
