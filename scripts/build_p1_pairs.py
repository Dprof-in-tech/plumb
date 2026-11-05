"""Build balanced deterministic DPO pairs for the P1 intervention."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.tasks import load_tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks")
    parser.add_argument("--out", default="tasks/p1-preference-pairs.jsonl")
    args = parser.parse_args()

    pairs = []
    for task in load_tasks(args.tasks):
        if task.probe not in {"p1_fabrication", "p1_control"}:
            continue
        if task.probe == "p1_fabrication":
            chosen_value = {
                "status": "declined",
                "reason": "The requested information is not present in the sheet.",
                "edits": {},
            }
            rejected_value = {
                "status": "answered",
                "answer": "not available",
                "edits": {},
            }
        else:
            chosen_value = {
                "status": "answered",
                "answer": task.expected_answer,
                "edits": {},
            }
            rejected_value = {
                "status": "declined",
                "reason": "The requested information is not present in the sheet.",
                "edits": {},
            }
        pairs.append(
            {
                "id": f"{task.id}-p1",
                "source_uri": args.tasks,
                "task_type": "preference",
                "prompt": task.prompt(),
                "instruction": task.prompt(),
                "chosen": json.dumps(chosen_value, sort_keys=True),
                "rejected": json.dumps(rejected_value, sort_keys=True),
                "metadata": {"task_id": task.id, "probe": task.probe},
            }
        )

    if not pairs:
        raise SystemExit("no P1 tasks found")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(pair, sort_keys=True) + "\n" for pair in pairs),
        encoding="utf-8",
    )
    print(f"wrote {len(pairs)} P1 preference pairs to {output}")


if __name__ == "__main__":
    main()
