"""Prompt Workflow Builder widget."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from AnyQt.QtCore import Qt, QTimer
from AnyQt.QtWidgets import QFileDialog, QLineEdit, QPlainTextEdit

from Orange.widgets import gui
from Orange.widgets.settings import Setting
from Orange.widgets.widget import Msg, OWWidget

from orangecontrib.nlworkflow.core.canvas import open_in_canvas, run_workflow
from orangecontrib.nlworkflow.core.compiler import save_workflow
from orangecontrib.nlworkflow.core.exporter import export_png
from orangecontrib.nlworkflow.core.planner import plan_from_prompt


class OWPromptWorkflowBuilder(OWWidget):
    name = "Prompt Workflow Builder"
    description = "Build an Orange workflow from a natural-language prompt."
    icon = "icons/prompt-workflow.svg"
    priority = 10
    keywords = "prompt workflow natural language openai canvas"
    want_main_area = False
    resizing_enabled = True

    prompt_text = Setting(
        "Bir müşteri terk tahmin çalışması istiyorum. CSV dosyasını aç, "
        "hedef değişkeni seç, gereksiz sütunları ayıkla, eksik değerleri "
        "doldur, veriyi normalize et, lojistik regresyon random forest "
        "gradient boosting modellerini karşılaştır, test and score değerlendir, "
        "confusion matrix ve roc analysis çıktılarını göster."
    )
    csv_path = Setting("")
    target_column = Setting("")
    ignored_columns = Setting("")
    output_dir = Setting(str(Path.home() / "Orange Workflows"))
    last_workflow_path = Setting("")
    last_png_path = Setting("")
    plan_json = Setting("")

    class Error(OWWidget.Error):
        failed = Msg("{}")

    class Warning(OWWidget.Warning):
        planner_warning = Msg("{}")

    def __init__(self):
        super().__init__()
        self.csv_path = ""
        self.target_column = ""
        self.ignored_columns = ""
        self._build_ui()

    def _build_ui(self) -> None:
        box = gui.widgetBox(self.controlArea, "Prompt")
        self.prompt_edit = QPlainTextEdit(self.prompt_text)
        self.prompt_edit.setMinimumHeight(120)
        self.prompt_edit.textChanged.connect(self._sync_prompt)
        box.layout().addWidget(self.prompt_edit)

        data_box = gui.widgetBox(self.controlArea, "Dataset")
        self.csv_edit = self._line(data_box, self.csv_path, self._sync_csv)
        self.csv_edit.setReadOnly(True)
        self.csv_edit.setPlaceholderText("Resolved automatically from prompt")
        self.target_edit = self._line(data_box, self.target_column, self._sync_target)
        self.target_edit.setReadOnly(True)
        self.target_edit.setPlaceholderText("Target resolved from prompt")
        self.ignore_edit = self._line(data_box, self.ignored_columns, self._sync_ignore)
        self.ignore_edit.setReadOnly(True)
        self.ignore_edit.setPlaceholderText("Ignored columns resolved from prompt")

        out_box = gui.widgetBox(self.controlArea, "Output")
        self.output_edit = self._line(out_box, self.output_dir, self._sync_output_dir)
        gui.button(out_box, self, "Browse Output...", callback=self._browse_output)

        buttons = gui.widgetBox(self.controlArea, orientation=Qt.Horizontal)
        gui.button(buttons, self, "Generate", callback=self.generate_workflow)
        gui.button(buttons, self, "Open on Canvas", callback=self.open_generated)
        gui.button(buttons, self, "Run", callback=self.run_generated)
        gui.button(buttons, self, "Export .ows", callback=self.export_ows_dialog)
        gui.button(buttons, self, "Export PNG", callback=self.export_png_dialog)

        status_box = gui.widgetBox(self.controlArea, "Status")
        self.status_label = gui.widgetLabel(status_box, "Ready.")
        self.plan_view = QPlainTextEdit(self.plan_json)
        self.plan_view.setReadOnly(True)
        self.plan_view.setMinimumHeight(150)
        status_box.layout().addWidget(self.plan_view)

    def _line(self, box, value: str, callback):
        edit = QLineEdit(value)
        edit.textChanged.connect(callback)
        box.layout().addWidget(edit)
        return edit

    def _sync_prompt(self):
        self.prompt_text = self.prompt_edit.toPlainText()

    def _sync_csv(self, value):
        self.csv_path = value

    def _sync_target(self, value):
        self.target_column = value

    def _sync_ignore(self, value):
        self.ignored_columns = value

    def _sync_output_dir(self, value):
        self.output_dir = value

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV", str(Path.home()), "Data files (*.csv *.tab *.tsv *.xlsx);;All files (*)"
        )
        if path:
            self.csv_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select output directory", self.output_dir)
        if path:
            self.output_edit.setText(path)

    def _output_paths(self) -> tuple[Path, Path]:
        output_dir = Path(self.output_dir).expanduser()
        stem = "prompt-workflow"
        if self.csv_path:
            stem = Path(self.csv_path).stem + "-workflow"
        return output_dir / f"{stem}.ows", output_dir / f"{stem}.png"

    def _ignored_list(self) -> list[str]:
        return [item.strip() for item in self.ignored_columns.split(",") if item.strip()]

    def generate_workflow(self):
        self.Error.failed.clear()
        self.Warning.planner_warning.clear()
        try:
            plan = plan_from_prompt(
                prompt=self.prompt_text,
                dataset_path=None,
                target_column=None,
                ignored_columns=(),
            )
            if plan.dataset.path and plan.dataset.path != self.csv_path:
                self.csv_path = plan.dataset.path
                self.csv_edit.setText(plan.dataset.path)
            if plan.dataset.target and plan.dataset.target != self.target_column:
                self.target_column = plan.dataset.target
                self.target_edit.setText(plan.dataset.target)
            ignored_text = ", ".join(plan.dataset.ignored_columns)
            if ignored_text != self.ignored_columns:
                self.ignored_columns = ignored_text
                self.ignore_edit.setText(ignored_text)
            workflow_path, png_path = self._output_paths()
            save_workflow(plan, workflow_path)
            export_png(workflow_path, png_path)
            self.last_workflow_path = str(workflow_path.resolve())
            self.last_png_path = str(png_path.resolve())
            self.plan_json = json.dumps(
                plan.to_dict(), indent=2, ensure_ascii=False, default=str
            )
            self.plan_view.setPlainText(self.plan_json)
            if plan.warnings:
                self.Warning.planner_warning("; ".join(plan.warnings[:3]))
            QTimer.singleShot(
                0,
                lambda path=self.last_workflow_path: open_in_canvas(
                    path, merge_current=True
                ),
            )
            self.status_label.setText(
                f"Generated and opening on Canvas: {self.last_workflow_path}"
            )
        except Exception as exc:
            self.Error.failed(str(exc))
            self.status_label.setText("Generation failed.")

    def open_generated(self):
        if not self.last_workflow_path:
            self.generate_workflow()
        if self.last_workflow_path:
            message = open_in_canvas(self.last_workflow_path, merge_current=True)
            self.status_label.setText(message)

    def run_generated(self):
        if not self.last_workflow_path:
            self.generate_workflow()
        if not self.last_workflow_path:
            return
        try:
            completed = run_workflow(self.last_workflow_path)
            if completed.returncode:
                detail = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(detail or f"Exit code {completed.returncode}")
            self.status_label.setText("Workflow executed successfully.")
        except Exception as exc:
            self.Error.failed(str(exc))
            self.status_label.setText("Workflow execution failed.")

    def export_ows_dialog(self):
        if not self.last_workflow_path:
            self.generate_workflow()
        if not self.last_workflow_path:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Orange Workflow", self.last_workflow_path, "Orange Workflow (*.ows)"
        )
        if path:
            shutil.copyfile(self.last_workflow_path, path)
            self.status_label.setText(f"Exported .ows: {path}")

    def export_png_dialog(self):
        if not self.last_workflow_path:
            self.generate_workflow()
        if not self.last_workflow_path:
            return
        default = self.last_png_path or str(Path(self.last_workflow_path).with_suffix(".png"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Workflow PNG", default, "PNG image (*.png)"
        )
        if path:
            export_png(self.last_workflow_path, path)
            self.last_png_path = path
            self.status_label.setText(f"Exported PNG: {path}")


if __name__ == "__main__":
    from Orange.widgets.utils.widgetpreview import WidgetPreview

    WidgetPreview(OWPromptWorkflowBuilder).run(no_exec=True)
