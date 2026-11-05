"""Run CuratorKIT hygiene checks without collapsing benchmark task identities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from curatorkit import Curator, CuratorConfig


def canonical_rows(task_path: Path, output_path: Path) -> int:
    count = 0
    with task_path.open(encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8"
    ) as target:
        for line in source:
            if not line.strip():
                continue
            task = json.loads(line)
            if task["ambiguous"]:
                status = "needs_clarification"
            elif not task["answerable"]:
                status = "declined"
            else:
                status = "answered"
            answer = {"status": status, "edits": {}}
            if task.get("expected_answer") is not None:
                answer["answer"] = task["expected_answer"]
            target.write(
                json.dumps(
                    {
                        "instruction": task["instruction"],
                        "input": json.dumps(task["sheet"], sort_keys=True),
                        "output": json.dumps(answer, sort_keys=True),
                        "task_type": "instruction_following",
                        "metadata": {
                            "plumb_id": task["id"],
                            "probe": task["probe"],
                        },
                    }
                )
                + "\n"
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks")
    parser.add_argument("--output", default="runs/curatorkit-review")
    args = parser.parse_args()

    task_path = Path(args.tasks)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    canonical = output / "canonical-input.jsonl"
    count = canonical_rows(task_path, canonical)

    result = Curator(
        CuratorConfig(
            dataset=str(canonical),
            format="alpaca",
            clean=True,
            dedup=None,
            output_dir=output,
            export_formats=["alpaca"],
            name="plumb_phase2_review",
            schema_gate=False,
        )
    ).run()
    result.print_summary()
    if result.rejected:
        raise SystemExit(f"CuratorKIT rejected {len(result.rejected)} of {count} tasks")
    print(f"reviewed {count} tasks without task-level deduplication")


if __name__ == "__main__":
    main()
