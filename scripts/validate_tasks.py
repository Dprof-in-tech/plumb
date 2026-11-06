"""Validate a task JSONL before it can be used as a baseline."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.tasks import PROBES, load_tasks


_CELL_RE = re.compile(r"^[A-Z]+\d+(?::[A-Z]+\d+)?$")
_ENTITY_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Q[1-4])\b", re.I)


def _derivable_answer(task):
    """(answer, cell) if the sheet plainly answers the question, else (None, None).

    Deliberately narrow. It fires only when exactly one row matches the entity
    the instruction asks about and that row has exactly one data column, so the
    answer is unambiguous. A looser rule flags "total energy usage for Site A in
    June" on a sheet where June exists but belongs to Site B, which is a genuine
    unanswerable task and a false alarm. Over-reporting here would train people
    to ignore the gate, which is how the original defect survived.
    """
    asked = {m.group(0).lower()
             for m in _ENTITY_RE.finditer(task.instruction or "")}
    if not asked:
        return None, None
    cells = []
    for address, value in task.sheet.cells.items():
        m = re.match(r"^([A-Z]+)(\d+)$", str(address).strip().upper())
        if m and str(value).strip():
            cells.append((m.group(1), int(m.group(2)), str(value)))
    matches = [(c, r) for c, r, v in cells if v.strip().lower() in asked]
    if len(matches) != 1:
        return None, None
    key_col, row = matches[0]
    same_row = [(c, v) for c, r, v in cells if r == row and c != key_col]
    if len(same_row) != 1:
        return None, None
    return same_row[0][1], f"{same_row[0][0]}{row}"


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

        # Shape, not just presence. A generator emitted write_set as
        # [{"cell": "B2", "value": "110"}] where the schema is {"B2": "110"}.
        # This gate passed it, because it only asked whether a write_set
        # existed. build_sft_data reads the dict form only, so all 108 write
        # tasks silently trained a model to answer with no edits at all.
        if task.probe.startswith("p3_") and task.write_set:
            ws = task.write_set
            if isinstance(ws, dict):
                bad = [a for a in ws if not _CELL_RE.match(str(a).strip().upper())]
            elif isinstance(ws, list):
                bad = [a for a in ws
                       if not (isinstance(a, str)
                               and _CELL_RE.match(a.strip().upper()))]
            else:
                bad = [ws]
            if bad:
                errors.append(
                    f"{task.id}: write_set is not {{cell: value}} or [cell]; "
                    f"got {type(ws).__name__} with {bad[:2]!r}")
            else:
                try:
                    task.allowed_cells
                except Exception as exc:
                    errors.append(f"{task.id}: write_set does not expand: {exc}")

        # An unanswerable task whose answer is sitting in the sheet is not
        # unanswerable. Seven of the locked benchmark's sixteen were, and every
        # existing gate passed them because they checked that expected_answer
        # was null, not that the null was true.
        if task.probe == "p1_fabrication":
            answer, where = _derivable_answer(task)
            if answer is not None:
                errors.append(
                    f"{task.id}: labelled unanswerable, but the answer is in the "
                    f"sheet at {where} ({answer!r})")

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
