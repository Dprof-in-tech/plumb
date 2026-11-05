"""Review PLUMB tasks with a non-Cohere teacher model via Ollama."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


PROMPT = """\
Review this spreadsheet benchmark task for data quality. Return exactly one JSON
object with these keys:
{"valid": true, "reason": "brief reason", "risk": "low|medium|high"}

Mark valid=false if the stated answerability, ambiguity, expected answer, sheet,
instruction, or write_set is inconsistent. Do not solve a task by guessing
missing data. This is a review only; do not rewrite the task.

An unanswerable task and an ambiguous task intentionally have no expected_answer;
that is valid. An answerable, unambiguous control should have an expected_answer.

Task:
"""


def first_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start:index + 1])
                except json.JSONDecodeError:
                    return None
                return value if isinstance(value, dict) else None
    return None


def review_task(task: dict[str, Any], model: str, base_url: str) -> tuple[dict[str, Any] | None, str]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT + json.dumps(task, sort_keys=True)}],
        "think": False,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 256},
    }).encode()
    request = urllib.request.Request(
        base_url.rstrip("/"),
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read())
    message = payload.get("message") or payload["choices"][0]["message"]
    raw = message.get("content") or message.get("reasoning", "")
    return first_object(raw), raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks")
    parser.add_argument("--out", default="tasks/phase2-teacher-review.jsonl")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--base-url", default="http://localhost:11434/api/chat")
    args = parser.parse_args()

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in Path(args.tasks).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        try:
            review, raw = review_task(task, args.model, args.base_url)
            error = None
        except Exception as exc:
            review, raw, error = None, "", str(exc)
        rows.append({
            "task_id": task["id"],
            "review": review,
            "raw": raw,
            "error": error,
        })
        output.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    summary = {
        "tasks": len(rows),
        "reviewed": sum(row["review"] is not None for row in rows),
        "valid": sum(row["review"] and row["review"].get("valid") is True for row in rows),
        "invalid": sum(row["review"] and row["review"].get("valid") is False for row in rows),
        "unparseable_or_error": sum(row["review"] is None for row in rows),
        "teacher_model": args.model,
    }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
