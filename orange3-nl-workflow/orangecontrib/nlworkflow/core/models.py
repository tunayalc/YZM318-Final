"""Small typed model used between the planner and Orange compiler."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DatasetPlan:
    path: str | None = None
    target: str | None = None
    ignored_columns: list[str] = field(default_factory=list)
    impute_method: str = "average"
    normalize_method: str = "normalize01"


@dataclass
class NodePlan:
    id: str
    widget: str
    title: str | None = None
    position: tuple[float, float] = (0.0, 0.0)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkPlan:
    source: str
    sink: str
    source_channel: str
    sink_channel: str


@dataclass
class WorkflowPlan:
    title: str
    description: str = ""
    dataset: DatasetPlan = field(default_factory=DatasetPlan)
    nodes: list[NodePlan] = field(default_factory=list)
    links: list[LinkPlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.nodes:
            raise ValueError("Workflow plan must contain at least one node.")
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("Workflow plan contains duplicate node ids.")
        for link in self.links:
            if link.source not in node_ids:
                raise ValueError(f"Link source does not exist: {link.source}")
            if link.sink not in node_ids:
                raise ValueError(f"Link sink does not exist: {link.sink}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkflowPlan":
        dataset = DatasetPlan(**raw.get("dataset", {}))
        nodes = [
            NodePlan(
                id=str(item["id"]),
                widget=str(item["widget"]),
                title=item.get("title"),
                position=tuple(item.get("position", (0.0, 0.0))),
                properties=dict(item.get("properties", {})),
            )
            for item in raw.get("nodes", [])
        ]
        links = [
            LinkPlan(
                source=str(item["source"]),
                sink=str(item["sink"]),
                source_channel=str(item["source_channel"]),
                sink_channel=str(item["sink_channel"]),
            )
            for item in raw.get("links", [])
        ]
        plan = cls(
            title=str(raw.get("title", "Orange Workflow")),
            description=str(raw.get("description", "")),
            dataset=dataset,
            nodes=nodes,
            links=links,
            warnings=[str(item) for item in raw.get("warnings", [])],
        )
        plan.validate()
        return plan


WORKFLOW_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "description", "dataset", "nodes", "links", "warnings"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "dataset": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "path",
                "target",
                "ignored_columns",
                "impute_method",
                "normalize_method",
            ],
            "properties": {
                "path": {"type": ["string", "null"]},
                "target": {"type": ["string", "null"]},
                "ignored_columns": {"type": "array", "items": {"type": "string"}},
                "impute_method": {"type": "string"},
                "normalize_method": {"type": "string"},
            },
        },
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "widget", "title", "position", "properties"],
                "properties": {
                    "id": {"type": "string"},
                    "widget": {"type": "string"},
                    "title": {"type": ["string", "null"]},
                    "position": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                        "items": {"type": "number"},
                    },
                    "properties": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {},
                    },
                },
            },
        },
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "sink", "source_channel", "sink_channel"],
                "properties": {
                    "source": {"type": "string"},
                    "sink": {"type": "string"},
                    "source_channel": {"type": "string"},
                    "sink_channel": {"type": "string"},
                },
            },
        },
    },
}
