"""Replace weak P2 ambiguity tasks with duplicate-header ambiguities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.tasks import load_tasks


CASES = (
    ("Revenue", "revenue"),
    ("Amount", "amount"),
    ("Date", "date"),
    ("Status", "status"),
    ("Balance", "balance"),
    ("Hours", "hours"),
    ("Margin", "margin"),
    ("Price", "price"),
    ("Quantity", "quantity"),
    ("Cost", "cost"),
    ("Tax", "tax"),
    ("Users", "users"),
    ("Inventory", "inventory"),
    ("Weight", "weight"),
    ("Score", "score"),
    ("Count", "count"),
)


def replacement(index: int, task_id: str) -> dict:
    header, noun = CASES[index]
    month = ("January", "February", "March", "April")[index % 4]
    left_value = 1000 + index * 137
    right_value = 700 + index * 113
    return {
        "id": f"{task_id}-v2",
        "probe": "p2_ambiguity",
        "ambiguous": True,
        "answerable": False,
        "instruction": f"What was the {noun} for {month}?",
        "sheet": {
            "A1": "Month",
            "A2": month,
            "B1": header,
            "B2": str(left_value),
            "C1": header,
            "C2": str(right_value),
        },
        "write_set": [],
        "expected_answer": None,
        "note": "p2_v4_duplicate_headers; both columns have the same label and different values",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--out", default="tasks/phase2-curatorkit-generated-96-p2v2.jsonl")
    args = parser.parse_args()

    tasks = load_tasks(args.source)
    ambiguous = [task for task in tasks if task.probe == "p2_ambiguity"]
    if len(ambiguous) != len(CASES):
        raise SystemExit(f"expected {len(CASES)} P2 tasks, found {len(ambiguous)}")

    replacements = iter(replacement(index, task.id) for index, task in enumerate(ambiguous))
    output_rows = []
    for task in tasks:
        if task.probe == "p2_ambiguity":
            output_rows.append(next(replacements))
        else:
            output_rows.append({
                "id": task.id,
                "probe": task.probe,
                "ambiguous": task.ambiguous,
                "answerable": task.answerable,
                "instruction": task.instruction,
                "sheet": task.sheet.cells,
                "write_set": task.write_set,
                "expected_answer": task.expected_answer,
                "note": task.note,
            })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    print(f"wrote {len(output_rows)} tasks to {out}")


if __name__ == "__main__":
    main()
