"""Build canonical full-task SFT examples from the locked PLUMB set."""

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
    parser.add_argument("--out", default="tasks/plumb-sft-corrections.jsonl")
    args = parser.parse_args()

    rows = []
    for task in load_tasks(args.tasks):
        if task.ambiguous:
            response = {
                "status": "needs_clarification",
                "reason": "More than one column could reasonably be meant.",
                "edits": {},
            }
        elif not task.answerable:
            response = {
                "status": "declined",
                "reason": "The requested information is not present in the sheet.",
                "edits": {},
            }
        else:
            edits = dict(task.write_set) if isinstance(task.write_set, dict) else {}
            response = {
                "status": "answered",
                "answer": task.expected_answer or "",
                "edits": edits,
            }
        rows.append(
            {
                "id": task.id,
                "prompt": task.prompt(),
                "completion": json.dumps(response, sort_keys=True),
                "metadata": {"probe": task.probe, "task_id": task.id},
            }
        )

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} SFT examples to {output}")


if __name__ == "__main__":
    main()
