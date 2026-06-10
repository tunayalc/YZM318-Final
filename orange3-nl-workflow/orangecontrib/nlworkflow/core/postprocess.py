"""Plan enrichment for Orange widgets whose settings are known."""

from __future__ import annotations

from typing import Iterable

from .models import WorkflowPlan
from .settings import (
    continuize_properties,
    csv_import_properties,
    file_properties,
    impute_properties,
    load_table,
    select_columns_properties,
    test_and_score_properties,
)


def _apply_readable_layout(plan: WorkflowPlan) -> None:
    xs = [node.position[0] for node in plan.nodes]
    ys = [node.position[1] for node in plan.nodes]
    if not xs or (max(xs) - min(xs) >= 120 or max(ys) - min(ys) >= 120):
        return

    incoming = {node.id: [] for node in plan.nodes}
    outgoing = {node.id: [] for node in plan.nodes}
    for link in plan.links:
        outgoing.setdefault(link.source, []).append(link.sink)
        incoming.setdefault(link.sink, []).append(link.source)

    layers = {node.id: 0 for node in plan.nodes}
    changed = True
    for _ in range(len(plan.nodes)):
        if not changed:
            break
        changed = False
        for link in plan.links:
            next_layer = layers[link.source] + 1
            if layers[link.sink] < next_layer:
                layers[link.sink] = next_layer
                changed = True

    by_layer: dict[int, list[str]] = {}
    for node in plan.nodes:
        by_layer.setdefault(layers[node.id], []).append(node.id)

    positions = {}
    for layer, node_ids in sorted(by_layer.items()):
        offset = -(len(node_ids) - 1) * 85
        for index, node_id in enumerate(node_ids):
            positions[node_id] = (80 + layer * 260, 260 + offset + index * 170)

    for node in plan.nodes:
        node.position = positions[node.id]


def apply_known_widget_settings(
    plan: WorkflowPlan,
    *,
    dataset_path: str | None,
    target_column: str | None,
    ignored_columns: Iterable[str],
) -> WorkflowPlan:
    """Fill reliable settings after an LLM chooses nodes and links."""
    if dataset_path and not plan.dataset.path:
        plan.dataset.path = dataset_path
    if target_column and not plan.dataset.target:
        plan.dataset.target = target_column
    ignored = list(ignored_columns)
    if ignored and not plan.dataset.ignored_columns:
        plan.dataset.ignored_columns = ignored

    table = load_table(plan.dataset.path or dataset_path)
    target = plan.dataset.target or target_column
    ignored = plan.dataset.ignored_columns or ignored

    for node in plan.nodes:
        widget = node.widget
        if widget == "Orange.widgets.data.owfile.OWFile":
            node.properties = file_properties(plan.dataset.path or dataset_path)
        elif widget == "Orange.widgets.data.owcsvimport.OWCSVFileImport":
            node.properties = csv_import_properties(plan.dataset.path or dataset_path)
        elif widget == "Orange.widgets.data.owselectcolumns.OWSelectAttributes":
            node.properties = select_columns_properties(
                table, target_column=target, ignored_columns=ignored
            )
        elif widget == "Orange.widgets.data.owimpute.OWImpute":
            node.properties = impute_properties(plan.dataset.impute_method)
        elif widget == "Orange.widgets.data.owcontinuize.OWContinuize":
            node.properties = continuize_properties(plan.dataset.normalize_method)
        elif widget == "Orange.widgets.evaluate.owtestandscore.OWTestAndScore":
            node.properties = test_and_score_properties()

    _apply_readable_layout(plan)
    return plan
