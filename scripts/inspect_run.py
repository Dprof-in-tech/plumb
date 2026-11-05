"""Inspect model behavior behind aggregate PLUMB metrics."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.tasks import Response


def inspect(path: str) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    statuses: Counter[str] = Counter()
    parse_failures: list[str] = []
    write_tasks = 0
    no_edit_tasks = 0
    edited_tasks = 0
    edit_counts: Counter[int] = Counter()

    for row in rows:
        response = Response.parse(row.get("raw", ""))
        statuses[response.status] += 1
        if not response.parse_ok:
            parse_failures.append(row.get("task_id", "<unknown>"))
        if row.get("probe") in {"p3_collateral", "p3_control"}:
            write_tasks += 1
            edit_counts[len(response.edits)] += 1
            if response.edits:
                edited_tasks += 1
            else:
                no_edit_tasks += 1

    return {
        "tasks": len(rows),
        "status_vocabulary": dict(sorted(statuses.items())),
        "parse_failures": parse_failures,
        "write_tasks": write_tasks,
        "edited_write_tasks": edited_tasks,
        "no_edit_tasks": no_edit_tasks,
        "no_edit_rate": (
            round(no_edit_tasks / write_tasks, 4) if write_tasks else None
        ),
        "edits_per_write_task": dict(sorted(edit_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="per-task JSONL produced by scripts/run.py")
    args = parser.parse_args()
    print(json.dumps(inspect(args.run), indent=2))


if __name__ == "__main__":
    main()
