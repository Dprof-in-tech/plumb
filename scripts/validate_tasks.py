"""Validate a task JSONL before it can be used as a baseline."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.tasks import PROBES, load_tasks


def validate(path: str, minimum_tasks: int = 80) -> list[str]:
    errors: list[str] = []
    tasks = load_tasks(path)
    if len(tasks) < minimum_tasks:
        errors.append(f"only {len(tasks)} tasks; need at least {minimum_tasks}")

    counts = Counter(task.probe for task in tasks)
    for probe in PROBES:
        if counts[probe] == 0:
            errors.append(f"missing probe: {probe}")

    write_tasks = [
        task for task in tasks
        if task.probe in {"p3_collateral", "p3_control"}
    ]
    if len(write_tasks) < max(16, len(tasks) // 8):
        errors.append(
            f"only {len(write_tasks)} write tasks; need at least "
            f"{max(16, len(tasks) // 8)}"
        )
    if not any(task.probe == "p3_control" for task in write_tasks):
        errors.append("missing p3 control tasks")

    for task in tasks:
        if task.probe == "p1_fabrication" and task.answerable:
            errors.append(f"{task.id}: fabrication task must be unanswerable")
        if task.probe == "p2_ambiguity" and not task.ambiguous:
            errors.append(f"{task.id}: ambiguity task must be ambiguous")
        if task.probe.startswith("p3_") and not task.write_set:
            errors.append(f"{task.id}: write task has empty write_set")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks")
    parser.add_argument("--minimum-tasks", type=int, default=80)
    args = parser.parse_args()
    errors = validate(args.tasks, args.minimum_tasks)
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        raise SystemExit(1)
    tasks = load_tasks(args.tasks)
    print(json.dumps({
        "valid": True,
        "tasks": len(tasks),
        "probe_counts": dict(sorted(Counter(task.probe for task in tasks).items())),
    }, indent=2))


if __name__ == "__main__":
    main()
