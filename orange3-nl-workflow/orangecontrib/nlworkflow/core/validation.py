"""Registry-backed validation for generated Orange workflow plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import WorkflowPlan
from .registry import RegistryCatalog


@dataclass
class PlanValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self, limit: int = 12) -> str:
        rows = []
        for prefix, items in (("ERROR", self.errors), ("WARNING", self.warnings)):
            for item in items[:limit]:
                rows.append(f"{prefix}: {item}")
            if len(items) > limit:
                rows.append(f"{prefix}: ... {len(items) - limit} more")
        return "\n".join(rows)


def _channel_label(channel: Any) -> str:
    channel_id = getattr(channel, "id", None)
    name = getattr(channel, "name", "")
    return str(channel_id or name)


def _find_channel(channels: list[Any], requested: str):
    requested_fold = requested.casefold()
    requested_options = {requested_fold}
    if "[" in requested and requested.endswith("]"):
        label, bracketed = requested.rsplit("[", 1)
        requested_options.add(label.strip().casefold())
        requested_options.add(bracketed[:-1].strip().casefold())
    for channel in channels:
        labels = {
            str(getattr(channel, "id", "") or "").casefold(),
            str(getattr(channel, "name", "") or "").casefold(),
        }
        if requested_options & labels:
            return channel
    return None


def _available_channels(channels: list[Any]) -> str:
    labels = [_channel_label(channel) for channel in channels]
    return ", ".join(label for label in labels if label) or "-"


def canonical_channel_id(channels: list[Any], requested: str) -> str:
    channel = _find_channel(channels, requested)
    if channel is None:
        return requested
    return _channel_label(channel)


def _type_names(channel: Any) -> set[str]:
    names = set()
    for item in getattr(channel, "type", ()) or ():
        if isinstance(item, str):
            names.add(item)
        else:
            module = getattr(item, "__module__", "")
            qualname = getattr(item, "__qualname__", getattr(item, "__name__", ""))
            names.add(f"{module}.{qualname}".strip("."))
    return names


def _types_look_compatible(source: Any, sink: Any) -> bool:
    source_types = _type_names(source)
    sink_types = _type_names(sink)
    if not source_types or not sink_types:
        return True
    if source_types & sink_types:
        return True
    broad_names = {"object", "typing.Any", "Any"}
    return bool(source_types & broad_names or sink_types & broad_names)


def validate_plan(
    plan: WorkflowPlan, catalog: RegistryCatalog | None = None
) -> PlanValidationReport:
    """Validate node/widget/channel existence before writing a workflow."""
    report = PlanValidationReport()
    catalog = catalog or RegistryCatalog()

    try:
        plan.validate()
    except Exception as exc:
        report.errors.append(str(exc))
        return report

    node_descs = {}
    for node in plan.nodes:
        try:
            node_descs[node.id] = catalog.resolve(node.widget)
        except KeyError:
            report.errors.append(
                f"Node '{node.id}' references unknown Orange widget '{node.widget}'."
            )

    for link in plan.links:
        source_desc = node_descs.get(link.source)
        sink_desc = node_descs.get(link.sink)
        if source_desc is None or sink_desc is None:
            continue

        source_channel = _find_channel(source_desc.outputs, link.source_channel)
        if source_channel is None:
            report.errors.append(
                f"Link {link.source}->{link.sink} uses missing output channel "
                f"'{link.source_channel}' on '{source_desc.name}'. Available: "
                f"{_available_channels(source_desc.outputs)}."
            )
            continue

        sink_channel = _find_channel(sink_desc.inputs, link.sink_channel)
        if sink_channel is None:
            report.errors.append(
                f"Link {link.source}->{link.sink} uses missing input channel "
                f"'{link.sink_channel}' on '{sink_desc.name}'. Available: "
                f"{_available_channels(sink_desc.inputs)}."
            )
            continue

        if not _types_look_compatible(source_channel, sink_channel):
            report.warnings.append(
                f"Link {link.source}->{link.sink} may have incompatible channel "
                f"types: {sorted(_type_names(source_channel))} -> "
                f"{sorted(_type_names(sink_channel))}."
            )

    return report


def validate_plan_or_raise(
    plan: WorkflowPlan, catalog: RegistryCatalog | None = None
) -> PlanValidationReport:
    report = validate_plan(plan, catalog)
    if not report.ok:
        raise ValueError("Generated workflow plan is invalid:\n" + report.summary())
    return report
