from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

from orangecanvas.scheme import Scheme, SchemeNode

from orangecontrib.nlworkflow.core.canvas import _merge_generated_workflow
from orangecontrib.nlworkflow.core.compiler import save_workflow
from orangecontrib.nlworkflow.core.dataset_resolver import resolve_dataset_path
from orangecontrib.nlworkflow.core.exporter import export_png, load_scheme
from orangecontrib.nlworkflow.core.models import LinkPlan
from orangecontrib.nlworkflow.core.planner import plan_from_prompt
from orangecontrib.nlworkflow.core.recipes import build_churn_workflow_plan
from orangecontrib.nlworkflow.core.registry import RegistryCatalog
from orangecontrib.nlworkflow.core.settings import csv_import_properties
from orangecontrib.nlworkflow.core.validation import validate_plan


def _write_churn_csv(path: Path) -> None:
    rows = [
        ["customer_id", "tenure", "monthly_charges", "contract", "churn"],
        ["c1", 1, 90.0, "month", "yes"],
        ["c2", 24, 30.0, "year", "no"],
        ["c3", 5, "", "month", "yes"],
        ["c4", 36, 40.0, "two-year", "no"],
        ["c5", 3, 80.0, "month", "yes"],
        ["c6", 48, 25.0, "two-year", "no"],
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerows(rows)


def _write_telco_csv(path: Path) -> None:
    rows = [
        ["customerID", "tenure", "MonthlyCharges", "Contract", "Churn"],
        ["c1", 1, 90.0, "Month-to-month", "Yes"],
        ["c2", 24, 30.0, "One year", "No"],
        ["c3", 5, "", "Month-to-month", "Yes"],
        ["c4", 36, 40.0, "Two year", "No"],
        ["c5", 3, 80.0, "Month-to-month", "Yes"],
        ["c6", 48, 25.0, "Two year", "No"],
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerows(rows)


def test_churn_plan_has_required_graph(tmp_path):
    csv_path = tmp_path / "churn.csv"
    _write_churn_csv(csv_path)
    plan = build_churn_workflow_plan(
        prompt="müşteri terk tahmin modeli",
        dataset_path=str(csv_path),
        target_column="churn",
        ignored_columns=["customer_id"],
    )

    node_ids = {node.id for node in plan.nodes}
    assert {
        "file",
        "select",
        "impute",
        "continuize",
        "test_score",
        "logreg",
        "rf",
        "gb",
        "cm",
        "roc",
    } <= node_ids
    assert ("continuize", "test_score", "data", "train_data") in {
        (link.source, link.sink, link.source_channel, link.sink_channel)
        for link in plan.links
    }
    assert ("test_score", "roc", "evaluations_results", "evaluation_results") in {
        (link.source, link.sink, link.source_channel, link.sink_channel)
        for link in plan.links
    }
    assert validate_plan(plan, RegistryCatalog()).ok


def test_registry_validation_rejects_bad_channel(tmp_path):
    csv_path = tmp_path / "churn.csv"
    _write_churn_csv(csv_path)
    plan = build_churn_workflow_plan(
        prompt="müşteri terk tahmin modeli",
        dataset_path=str(csv_path),
        target_column="churn",
        ignored_columns=["customer_id"],
    )
    plan.links = [
        LinkPlan(
            source=link.source,
            sink=link.sink,
            source_channel="not_a_real_channel"
            if link.source == "file" and link.sink == "select"
            else link.source_channel,
            sink_channel=link.sink_channel,
        )
        for link in plan.links
    ]

    report = validate_plan(plan, RegistryCatalog())

    assert not report.ok
    assert "missing output channel" in report.summary()


def test_csv_import_properties_include_selected_path(tmp_path):
    csv_path = tmp_path / "churn.csv"
    _write_churn_csv(csv_path)

    properties = csv_import_properties(str(csv_path))

    assert str(csv_path) in str(properties)


def test_resolves_absolute_csv_path_from_prompt(tmp_path):
    csv_path = tmp_path / "churn.csv"
    _write_churn_csv(csv_path)

    resolution = resolve_dataset_path(f"{csv_path} dosyasını aç")

    assert resolution.path == str(csv_path.resolve())
    assert resolution.source == "prompt"


def test_resolves_named_csv_from_prompt_search_dirs(tmp_path):
    csv_path = tmp_path / "skills.csv"
    _write_churn_csv(csv_path)

    resolution = resolve_dataset_path(
        "indirilenlerdeki skills.csv dosyasını aç",
        search_dirs=[tmp_path],
    )

    assert resolution.path == str(csv_path.resolve())
    assert resolution.source == "prompt"


def test_resolves_last_csv_when_prompt_is_extended(tmp_path):
    old_csv = tmp_path / "old.csv"
    new_csv = tmp_path / "new.csv"
    _write_churn_csv(old_csv)
    _write_churn_csv(new_csv)

    resolution = resolve_dataset_path(
        f"{old_csv} dosyasını aç. Sonra dosyayı {new_csv} olarak değiştir."
    )

    assert resolution.path == str(new_csv.resolve())


def test_resolves_fuzzy_dataset_from_dataset_phrase(tmp_path):
    telco_csv = tmp_path / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
    other_csv = tmp_path / "other.csv"
    _write_telco_csv(telco_csv)
    _write_churn_csv(other_csv)

    resolution = resolve_dataset_path(
        "datasetten telco customer churn csv seç",
        search_dirs=[tmp_path],
    )

    assert resolution.path == str(telco_csv.resolve())
    assert resolution.source == "fuzzy"


def test_plan_from_prompt_uses_csv_mentioned_in_prompt(tmp_path):
    csv_path = tmp_path / "churn.csv"
    _write_churn_csv(csv_path)

    plan = plan_from_prompt(
        prompt=f"{csv_path} dosyasını aç ve müşteri terk tahmini workflowu kur",
        prefer_openai=False,
    )

    assert plan.dataset.path == str(csv_path.resolve())


def test_plan_from_prompt_extracts_target_and_ignore_from_prompt(tmp_path):
    csv_path = tmp_path / "telco.csv"
    _write_telco_csv(csv_path)

    plan = plan_from_prompt(
        prompt=(
            f"{csv_path} dosyasını aç. Hedef değişkeni Churn olarak seç, "
            "gereksiz ID sütunu olan customerID sütununu ayıkla. "
            "Müşteri terk tahmini workflowu kur."
        ),
        prefer_openai=False,
    )

    assert plan.dataset.target == "Churn"
    assert plan.dataset.ignored_columns == ["customerID"]


def test_extended_prompt_can_change_target_and_add_visual_nodes(tmp_path):
    csv_path = tmp_path / "telco.csv"
    _write_telco_csv(csv_path)

    plan = plan_from_prompt(
        prompt=(
            f"{csv_path} dosyasını aç. Hedef değişkeni Churn olarak seç. "
            "Sonra hedef değişkeni Contract olarak değiştir. "
            "Scatter plot, box plot ve data table da ekle."
        ),
        prefer_openai=False,
    )

    assert plan.dataset.target == "Contract"
    assert {"scatter", "box", "data_table"} <= {node.id for node in plan.nodes}


def test_churn_workflow_roundtrip_and_png(tmp_path):
    csv_path = tmp_path / "churn.csv"
    workflow_path = tmp_path / "churn.ows"
    png_path = tmp_path / "churn.png"
    _write_churn_csv(csv_path)

    plan = build_churn_workflow_plan(
        prompt="müşteri terk tahmini",
        dataset_path=str(csv_path),
        target_column="churn",
        ignored_columns=["customer_id"],
    )
    save_workflow(plan, workflow_path)
    scheme = load_scheme(workflow_path, RegistryCatalog())
    export_png(workflow_path, png_path)

    assert len(scheme.nodes) == len(plan.nodes)
    assert len(scheme.links) == len(plan.links)
    assert png_path.exists()
    assert png_path.stat().st_size > 1000


def test_canvas_merge_keeps_builder_and_replaces_generated_nodes(tmp_path):
    csv_path = tmp_path / "churn.csv"
    workflow_path = tmp_path / "churn.ows"
    _write_churn_csv(csv_path)
    plan = build_churn_workflow_plan(
        prompt="müşteri terk tahmini",
        dataset_path=str(csv_path),
        target_column="churn",
        ignored_columns=["customer_id"],
    )
    save_workflow(plan, workflow_path)

    catalog = RegistryCatalog()
    builder_desc = catalog.resolve("Prompt Workflow Builder")
    scheme = Scheme()
    scheme.add_node(
        SchemeNode(
            builder_desc,
            title="Prompt Workflow Builder",
            position=(80, 240),
            properties={},
        )
    )

    class Doc:
        def scheme(self):
            return scheme

    class Window:
        def current_document(self):
            return Doc()

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    _merge_generated_workflow(Window(), str(workflow_path))
    _merge_generated_workflow(Window(), str(workflow_path))

    titles = [node.title for node in scheme.nodes]
    assert titles.count("Prompt Workflow Builder") == 1
    assert titles.count("CSV File") == 1
    assert len(scheme.nodes) == len(plan.nodes) + 1


def test_churn_workflow_executes_headless(tmp_path):
    csv_path = tmp_path / "churn.csv"
    workflow_path = tmp_path / "churn.ows"
    _write_churn_csv(csv_path)
    plan = build_churn_workflow_plan(
        prompt="müşteri terk tahmini",
        dataset_path=str(csv_path),
        target_column="churn",
        ignored_columns=["customer_id"],
    )
    save_workflow(plan, workflow_path)

    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "Orange.canvas.run",
            "--log-level",
            "2",
            str(workflow_path),
        ],
        text=True,
        capture_output=True,
        timeout=120,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
