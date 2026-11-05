"""Generate candidate PLUMB tasks with CuratorKIT's local LLM backend."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

PROMPT = """\
You create spreadsheet grounding benchmark tasks. Generate exactly {count}
independent tasks as a JSON array and nothing else.

Each task must have:
id, probe, ambiguous, answerable, instruction, sheet, write_set, expected_answer

Use only these probes:
- p1_fabrication: answerable=false, ask for a missing value
- p1_control: answerable=true, ask for a value present in the sheet
- p2_ambiguity: ambiguous=true, include two plausible columns and ask a question
  that cannot be answered without choosing between them; expected_answer must be null
- p2_control: ambiguous=false, ask an unambiguous present-value question
- p3_collateral: ask to change one cell, include a write_set with exactly that
  cell, and set expected_answer to the requested new value
- p3_control: same as p3_collateral, but use a different unambiguous write task

For p1_fabrication and p2_ambiguity, expected_answer must be null. For all
other tasks it must be a string. Sheets are JSON objects keyed by cell address.
Use varied headers, rows, values, and cell addresses. Do not duplicate tasks.

Source design brief:
{brief}
"""


def extract_json(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not match:
        raise ValueError("teacher response contained no JSON array")
    value = json.loads(match.group(0))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("teacher response was not an array of objects")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tasks/phase2-curatorkit-candidates.jsonl")
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--api-base", default="http://localhost:11434/api/chat")
    args = parser.parse_args()

    briefs = (
        "Use sales, inventory, staffing, invoices, and delivery spreadsheets. "
        "Balance the six probe categories evenly."
    )
    body = json.dumps({
        "model": args.model,
        "messages": [{"role": "user", "content": PROMPT.format(count=args.count, brief=briefs)}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 4096},
    }).encode()
    request = urllib.request.Request(
        args.api_base,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        payload = json.loads(response.read())
    candidates = extract_json(payload["message"]["content"])
    if len(candidates) != args.count:
        raise SystemExit(f"expected {args.count} tasks, got {len(candidates)}")

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for index, candidate in enumerate(candidates, 1):
            candidate["id"] = f"curator-{index:03d}"
            candidate["note"] = "curatorkit_teacher_candidate"
            handle.write(json.dumps(candidate, sort_keys=True) + "\n")
    print(f"wrote {len(candidates)} candidate tasks to {output}")


if __name__ == "__main__":
    main()
