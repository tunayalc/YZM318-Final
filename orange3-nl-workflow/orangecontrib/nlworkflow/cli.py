"""Command-line entry point for smoke testing the add-on core."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.compiler import save_workflow
from .core.exporter import export_png
from .core.planner import plan_from_prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--csv")
    parser.add_argument("--target")
    parser.add_argument("--ignore", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--png")
    parser.add_argument("--print-plan", action="store_true")
    args = parser.parse_args(argv)

    ignored = [item.strip() for item in args.ignore.split(",") if item.strip()]
    plan = plan_from_prompt(
        prompt=args.prompt,
        dataset_path=args.csv,
        target_column=args.target,
        ignored_columns=ignored,
    )
    if plan.dataset.path:
        print(f"[OK] dataset {plan.dataset.path}")
    output = save_workflow(plan, args.output)
    if args.png:
        export_png(output, args.png)
    if args.print_plan:
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False, default=str))
    print(f"[OK] wrote {output}")
    if args.png:
        print(f"[OK] wrote {Path(args.png).expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
