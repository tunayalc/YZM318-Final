"""Orange widget registry discovery and catalog export."""

from __future__ import annotations

from functools import lru_cache
from typing import Any


def _channel_to_dict(channel) -> dict[str, Any]:
    return {
        "name": getattr(channel, "name", ""),
        "id": getattr(channel, "id", None),
        "type": [str(item) for item in getattr(channel, "type", ())],
        "default": bool(getattr(channel, "default", False)),
        "explicit": bool(getattr(channel, "explicit", False)),
    }


@lru_cache(maxsize=1)
def discover_registry():
    from .qt import ensure_qapplication

    ensure_qapplication()
    from orangecanvas import config
    from orangecanvas.registry import WidgetRegistry, cache
    from Orange.canvas.config import Config

    cfg = Config()
    config.set_default(cfg)
    config.init()
    registry = WidgetRegistry()
    discovery = cfg.widget_discovery(
        registry, cached_descriptions=cache.registry_cache()
    )
    discovery.run(cfg.widgets_entry_points())
    return registry


class RegistryCatalog:
    """Lookup wrapper around Orange's WidgetRegistry."""

    def __init__(self, registry=None):
        self.registry = registry or discover_registry()

    def widgets(self) -> list[dict[str, Any]]:
        rows = []
        for desc in sorted(self.registry.widgets(), key=lambda item: item.name):
            rows.append(
                {
                    "name": desc.name,
                    "qualified_name": desc.qualified_name,
                    "category": desc.category,
                    "inputs": [_channel_to_dict(ch) for ch in desc.inputs],
                    "outputs": [_channel_to_dict(ch) for ch in desc.outputs],
                }
            )
        return rows

    def resolve(self, widget: str):
        try:
            return self.registry.widget(widget)
        except KeyError:
            pass

        lowered = widget.casefold()
        matches = [
            desc
            for desc in self.registry.widgets()
            if desc.name.casefold() == lowered
            or desc.qualified_name.casefold() == lowered
        ]
        if not matches:
            raise KeyError(f"Orange widget not found: {widget}")
        matches.sort(key=lambda item: (item.category.casefold(), item.name.casefold()))
        return matches[0]

    def compact_catalog_text(self) -> str:
        lines = []
        for item in self.widgets():
            inputs = ", ".join(
                f"{ch['name']}[{ch['id']}]" for ch in item["inputs"]
            ) or "-"
            outputs = ", ".join(
                f"{ch['name']}[{ch['id']}]" for ch in item["outputs"]
            ) or "-"
            lines.append(
                f"- {item['name']} | {item['qualified_name']} | "
                f"category={item['category']} | inputs={inputs} | outputs={outputs}"
            )
        return "\n".join(lines)
