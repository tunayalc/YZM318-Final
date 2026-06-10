"""Guaranteed workflow recipes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import DatasetPlan, LinkPlan, NodePlan, WorkflowPlan
from .settings import (
    continuize_properties,
    file_properties,
    impute_properties,
    load_table,
    select_columns_properties,
    test_and_score_properties,
)

Q = {
    "file": "Orange.widgets.data.owfile.OWFile",
    "select": "Orange.widgets.data.owselectcolumns.OWSelectAttributes",
    "impute": "Orange.widgets.data.owimpute.OWImpute",
    "continuize": "Orange.widgets.data.owcontinuize.OWContinuize",
    "test_score": "Orange.widgets.evaluate.owtestandscore.OWTestAndScore",
    "logreg": "Orange.widgets.model.owlogisticregression.OWLogisticRegression",
    "rf": "Orange.widgets.model.owrandomforest.OWRandomForest",
    "gb": "Orange.widgets.model.owgradientboosting.OWGradientBoosting",
    "cm": "Orange.widgets.evaluate.owconfusionmatrix.OWConfusionMatrix",
    "roc": "Orange.widgets.evaluate.owrocanalysis.OWROCAnalysis",
    "table": "Orange.widgets.data.owtable.OWTable",
    "scatter": "Orange.widgets.visualize.owscatterplot.OWScatterPlot",
    "box": "Orange.widgets.visualize.owboxplot.OWBoxPlot",
}


def _all_prompt_vars(table) -> list:
    if table is None:
        return []
    return list(table.domain.attributes) + list(table.domain.class_vars) + list(
        table.domain.metas
    )


def _find_prompt_var_near_keywords(
    table, prompt: str, keywords: tuple[str, ...], *, window: int = 45
) -> str | None:
    prompt_lower = prompt.casefold()
    best = None
    for var in _all_prompt_vars(table):
        name = var.name.casefold()
        start = 0
        while True:
            index = prompt_lower.find(name, start)
            if index == -1:
                break
            left = prompt_lower[max(0, index - window): index]
            right = prompt_lower[index + len(name): index + len(name) + window]
            distances = []
            for keyword in keywords:
                left_pos = left.rfind(keyword)
                if left_pos >= 0:
                    distances.append(len(left) - left_pos)
                right_pos = right.find(keyword)
                if right_pos >= 0:
                    distances.append(right_pos)
            if distances:
                distance = min(distances)
                if (
                    best is None
                    or distance < best[1] - 5
                    or (abs(distance - best[1]) <= 5 and index > best[0])
                ):
                    best = (index, distance, var.name)
            start = index + len(name)
    return best[2] if best else None


def _infer_target(table, requested: str | None, prompt: str) -> str | None:
    if requested:
        return requested
    if table is None:
        return None
    explicit = _find_prompt_var_near_keywords(
        table,
        prompt,
        ("hedef", "target", "class", "label", "çıktı", "bağımlı"),
    )
    if explicit:
        return explicit
    if table.domain.class_var is not None:
        return table.domain.class_var.name

    candidate_words = (
        "churn",
        "terk",
        "target",
        "class",
        "label",
        "outcome",
        "left",
        "exited",
    )
    all_vars = list(table.domain.attributes) + list(table.domain.metas)
    for var in all_vars:
        name = var.name.casefold()
        if any(word in name for word in candidate_words):
            return var.name
    if all_vars:
        return all_vars[-1].name
    return None


def _infer_ignored(
    table,
    requested: Iterable[str],
    prompt: str = "",
    target_column: str | None = None,
) -> list[str]:
    requested_clean = [item.strip() for item in requested if item and item.strip()]
    if requested_clean or table is None:
        return requested_clean

    ignored = []
    prompt_lower = prompt.casefold()
    ignore_keywords = ("ignore", "ignored", "ayıkla", "çıkar", "gereksiz", "drop")
    explicitly_ignored = set(
        name.casefold()
        for name in _prompt_vars_near_keywords(table, prompt, ignore_keywords)
    )
    for var in list(table.domain.attributes) + list(table.domain.metas):
        if target_column and var.name.casefold() == target_column.casefold():
            continue
        name = var.name.casefold()
        normalized = "".join(ch for ch in name if ch.isalnum())
        if (
            name in {"id", "customer_id", "userid", "user_id"}
            or name.endswith("_id")
            or normalized in {"customerid", "userid"}
            or name in explicitly_ignored
        ):
            ignored.append(var.name)
    return ignored


def _prompt_vars_near_keywords(table, prompt: str, keywords: tuple[str, ...]) -> list[str]:
    prompt_lower = prompt.casefold()
    matches = []
    for var in _all_prompt_vars(table):
        name = var.name.casefold()
        start = 0
        while True:
            index = prompt_lower.find(name, start)
            if index == -1:
                break
            context = prompt_lower[max(0, index - 80): index + len(name) + 80]
            if any(keyword in context for keyword in keywords):
                matches.append(var.name)
                break
            start = index + len(name)
    return matches


def _wants_any(prompt: str, words: tuple[str, ...]) -> bool:
    lowered = prompt.casefold()
    return any(word in lowered for word in words)


def build_churn_workflow_plan(
    *,
    prompt: str,
    dataset_path: str | None = None,
    target_column: str | None = None,
    ignored_columns: Iterable[str] = (),
    normalize_method: str = "normalize01",
    impute_method: str = "average",
) -> WorkflowPlan:
    """Build the guaranteed v1 churn/classification Orange workflow."""
    table = load_table(dataset_path)
    target = _infer_target(table, target_column, prompt)
    ignored = _infer_ignored(table, ignored_columns, prompt, target)

    warnings = []
    if dataset_path and not Path(dataset_path).expanduser().exists():
        warnings.append(f"CSV file does not exist yet: {dataset_path}")
    if table is None:
        warnings.append("Dataset schema was not available; target settings use defaults.")
    elif not target:
        warnings.append("No target column could be inferred.")

    nodes = [
        NodePlan("file", Q["file"], "CSV File", (80, 240), file_properties(dataset_path)),
        NodePlan(
            "select",
            Q["select"],
            "Select Target / Columns",
            (280, 240),
            select_columns_properties(
                table, target_column=target, ignored_columns=ignored
            ),
        ),
        NodePlan(
            "impute",
            Q["impute"],
            "Impute Missing Values",
            (500, 240),
            impute_properties(impute_method),
        ),
        NodePlan(
            "continuize",
            Q["continuize"],
            "Normalize Data",
            (720, 240),
            continuize_properties(normalize_method),
        ),
        NodePlan(
            "test_score",
            Q["test_score"],
            "Test and Score",
            (980, 240),
            test_and_score_properties(),
        ),
        NodePlan("logreg", Q["logreg"], "Logistic Regression", (720, 40), {}),
        NodePlan("rf", Q["rf"], "Random Forest", (720, 420), {}),
        NodePlan("gb", Q["gb"], "Gradient Boosting", (720, 560), {}),
        NodePlan("cm", Q["cm"], "Confusion Matrix", (1240, 150), {}),
        NodePlan("roc", Q["roc"], "ROC Analysis", (1240, 330), {}),
        NodePlan("predictions", Q["table"], "Predictions", (1240, 520), {}),
    ]

    links = [
        LinkPlan("file", "select", "data", "data"),
        LinkPlan("select", "impute", "data", "data"),
        LinkPlan("impute", "continuize", "data", "data"),
        LinkPlan("continuize", "test_score", "data", "train_data"),
        LinkPlan("logreg", "test_score", "learner", "learner"),
        LinkPlan("rf", "test_score", "learner", "learner"),
        LinkPlan("gb", "test_score", "learner", "learner"),
        LinkPlan("test_score", "cm", "evaluations_results", "evaluation_results"),
        LinkPlan("test_score", "roc", "evaluations_results", "evaluation_results"),
        LinkPlan("test_score", "predictions", "predictions", "data"),
    ]

    if _wants_any(prompt, ("data table", "veri tablosu", "ham veriyi göster")):
        nodes.append(NodePlan("data_table", Q["table"], "Data Table", (980, 620), {}))
        links.append(LinkPlan("continuize", "data_table", "data", "data"))

    if _wants_any(prompt, ("scatter plot", "scatter", "saçılım")):
        nodes.append(NodePlan("scatter", Q["scatter"], "Scatter Plot", (980, 780), {}))
        links.append(LinkPlan("continuize", "scatter", "data", "data"))

    if _wants_any(prompt, ("box plot", "boxplot", "kutu grafiği", "kutu")):
        nodes.append(NodePlan("box", Q["box"], "Box Plot", (980, 940), {}))
        links.append(LinkPlan("continuize", "box", "data", "data"))

    plan = WorkflowPlan(
        title="Customer Churn Prediction",
        description=(
            "Generated from a natural-language prompt. Loads a CSV, selects "
            "target/features, imputes missing values, normalizes data, compares "
            "Logistic Regression, Random Forest, and Gradient Boosting, then "
            "sends evaluation results to Confusion Matrix and ROC Analysis."
        ),
        dataset=DatasetPlan(
            path=dataset_path,
            target=target,
            ignored_columns=ignored,
            impute_method=impute_method,
            normalize_method=normalize_method,
        ),
        nodes=nodes,
        links=links,
        warnings=warnings,
    )
    plan.validate()
    return plan
