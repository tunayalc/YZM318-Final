"""Compile WorkflowPlan objects into Orange Canvas .ows files."""

from __future__ import annotations

from pathlib import Path

from .models import WorkflowPlan
from .registry import RegistryCatalog
from .validation import canonical_channel_id, validate_plan_or_raise


def compile_scheme(plan: WorkflowPlan, catalog: RegistryCatalog | None = None):
    from orangecanvas.scheme import Scheme, SchemeLink, SchemeNode

    catalog = catalog or RegistryCatalog()
    validate_plan_or_raise(plan, catalog)
    scheme = Scheme(title=plan.title, description=plan.description)
    nodes = {}
    node_descs = {}

    for node_plan in plan.nodes:
        desc = catalog.resolve(node_plan.widget)
        node = SchemeNode(
            desc,
            title=node_plan.title or desc.name,
            position=tuple(node_plan.position),
            properties=node_plan.properties,
        )
        scheme.add_node(node)
        nodes[node_plan.id] = node
        node_descs[node_plan.id] = desc

    for link_plan in plan.links:
        source_desc = node_descs[link_plan.source]
        sink_desc = node_descs[link_plan.sink]
        link = SchemeLink(
            nodes[link_plan.source],
            canonical_channel_id(source_desc.outputs, link_plan.source_channel),
            nodes[link_plan.sink],
            canonical_channel_id(sink_desc.inputs, link_plan.sink_channel),
        )
        scheme.add_link(link)

    return scheme


def save_workflow(plan: WorkflowPlan, output_path: str | Path) -> Path:
    from orangecanvas.scheme.readwrite import scheme_to_ows_stream

    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    scheme = compile_scheme(plan)
    scheme.set_runtime_env("basedir", str(output.parent))
    with output.open("wb") as stream:
        scheme_to_ows_stream(scheme, stream, pretty=True, pickle_fallback=True)
    return output
