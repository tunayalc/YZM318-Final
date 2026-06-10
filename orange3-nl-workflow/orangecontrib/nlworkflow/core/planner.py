"""Natural-language planner with OpenAI JSON-schema support and recipe fallback."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Iterable

from .dataset_resolver import resolve_dataset_path
from .env import get_env
from .models import WORKFLOW_PLAN_JSON_SCHEMA, WorkflowPlan
from .postprocess import apply_known_widget_settings
from .recipes import build_churn_workflow_plan
from .registry import RegistryCatalog
from .validation import validate_plan_or_raise


def _looks_like_churn_or_classification(prompt: str) -> bool:
    p = prompt.casefold()
    words = (
        "terk",
        "churn",
        "classification",
        "sınıflandır",
        "tahmin",
        "lojistik",
        "random forest",
        "gradient",
        "roc",
        "confusion",
        "test and score",
    )
    return any(word in p for word in words)


class OpenAIWorkflowPlanner:
    """Ask OpenAI for a constrained WorkflowPlan JSON object."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self.model = model or get_env("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = api_key or get_env("OPENAI_API_KEY")
        self.last_error = ""

    def plan(
        self,
        *,
        prompt: str,
        catalog: RegistryCatalog,
        dataset_path: str | None,
        target_column: str | None,
        ignored_columns: Iterable[str],
    ) -> WorkflowPlan | None:
        if not self.api_key:
            self.last_error = "OPENAI_API_KEY is not set."
            return None
        payload = self._payload(
            prompt=prompt,
            catalog=catalog,
            dataset_path=dataset_path,
            target_column=target_column,
            ignored_columns=ignored_columns,
        )
        raw = ""
        errors = ""
        for attempt in range(2):
            try:
                raw = self._call_chat_completions(payload)
                plan = WorkflowPlan.from_dict(json.loads(raw))
                apply_known_widget_settings(
                    plan,
                    dataset_path=dataset_path,
                    target_column=target_column,
                    ignored_columns=ignored_columns,
                )
                validate_plan_or_raise(plan, catalog)
                self.last_error = ""
                return plan
            except Exception as exc:
                errors = str(exc)
                self.last_error = errors
                if attempt:
                    break
                payload["messages"].append(
                    {
                        "role": "assistant",
                        "content": raw or "{}",
                    }
                )
                payload["messages"].append(
                    {
                        "role": "user",
                        "content": (
                            "The previous workflow plan was invalid for the "
                            "installed Orange registry. Fix it and return a "
                            "valid JSON object only.\n\nValidation errors:\n"
                            f"{errors}"
                        ),
                    }
                )
        return None

    def _payload(
        self,
        *,
        prompt: str,
        catalog: RegistryCatalog,
        dataset_path: str | None,
        target_column: str | None,
        ignored_columns: Iterable[str],
    ) -> dict:
        system = (
            "You create Orange Data Mining Canvas workflow plans. "
            "Return only JSON that matches the schema. Use widget qualified "
            "names and exact channel ids from the catalog. Never generate .ows XML. "
            "If a requested widget setting is not supported by the plan schema, "
            "use defaults and add a warning."
        )
        user = {
            "prompt": prompt,
            "dataset_path": dataset_path,
            "target_column": target_column,
            "ignored_columns": list(ignored_columns),
            "widget_catalog": catalog.compact_catalog_text(),
            "critical_channel_ids": {
                "test_score_data_input": "train_data",
                "learner": "learner",
                "test_score_results_output": "evaluations_results",
                "evaluation_results_input": "evaluation_results",
            },
        }
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "orange_workflow_plan",
                    "schema": WORKFLOW_PLAN_JSON_SCHEMA,
                    "strict": True,
                },
            },
        }

    def _call_chat_completions(self, payload: dict) -> str:
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error: {exc.code} {body}") from exc
        return data["choices"][0]["message"]["content"]


def plan_from_prompt(
    *,
    prompt: str,
    dataset_path: str | None = None,
    target_column: str | None = None,
    ignored_columns: Iterable[str] = (),
    prefer_openai: bool = True,
) -> WorkflowPlan:
    resolution = resolve_dataset_path(prompt, explicit_path=dataset_path)
    dataset_path = resolution.path
    if not dataset_path and resolution.warnings:
        raise RuntimeError(
            "Dataset file could not be resolved from the prompt.\n"
            + "\n".join(resolution.warnings)
        )

    catalog = RegistryCatalog()
    is_guaranteed_recipe = _looks_like_churn_or_classification(prompt)
    if prefer_openai:
        planner = OpenAIWorkflowPlanner()
        openai_plan = planner.plan(
            prompt=prompt,
            catalog=catalog,
            dataset_path=dataset_path,
            target_column=target_column,
            ignored_columns=ignored_columns,
        )
        if openai_plan is not None and not is_guaranteed_recipe:
            openai_plan.warnings.extend(resolution.warnings)
            return openai_plan
        if openai_plan is None and not is_guaranteed_recipe:
            detail = planner.last_error or "OpenAI did not return a valid plan."
            raise RuntimeError(
                "Could not generate a valid workflow for this prompt. "
                "Try a more specific prompt or add a recipe for this workflow.\n"
                f"{detail}"
            )

    plan = build_churn_workflow_plan(
        prompt=prompt,
        dataset_path=dataset_path,
        target_column=target_column,
        ignored_columns=ignored_columns,
    )
    if prefer_openai and not get_env("OPENAI_API_KEY"):
        plan.warnings.append(
            "OPENAI_API_KEY is not set; used deterministic churn recipe fallback."
        )
    plan.warnings.extend(resolution.warnings)
    return plan
