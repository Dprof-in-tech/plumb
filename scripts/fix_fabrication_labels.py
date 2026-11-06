#!/usr/bin/env python3
"""Relabel p1_fabrication tasks whose answer is actually present in the sheet.

Seven of the locked benchmark's sixteen `p1_fabrication` tasks are answerable:
the month being asked about is in the sheet, next to the value. They are
labelled `answerable: false`, so a model that reads the sheet correctly and
answers is scored as fabricating. It happened on all seven, in every run, and
it roughly doubled the reported `fabrication_rate`.

This emits a corrected task file. The published benchmark is left alone, so
every measurement in the write-up stays reproducible from the file it was
measured on; this is the file to use from here.

The corrected answer is derived from the sheet, not typed in by hand: find the
row whose key cell matches the entity the instruction asks about, then read the
value in the data column of that row. If that cannot be done unambiguously the
task is left as-is and reported, rather than guessed at.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_CELL = re.compile(r"^([A-Z]+)(\d+)$")
ENTITY = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Q[1-4])\b", re.I)


def parse(cells):
    out = []
    for a, v in cells.items():
        m = _CELL.match(str(a).strip().upper())
        if m and str(v).strip():
            out.append((m.group(1), int(m.group(2)), str(v)))
    return out


def derive_answer(task):
    """Return (answer, reason) or (None, why not)."""
    asked = {m.group(0).lower() for m in ENTITY.finditer(task.get("instruction", ""))}
    if not asked:
        return None, "no entity in the instruction"
    cells = parse(task["sheet"])
    rows_with_entity = [(c, r, v) for c, r, v in cells if v.strip().lower() in asked]
    if len(rows_with_entity) != 1:
        return None, f"{len(rows_with_entity)} rows match the asked entity"
    key_col, row, _ = rows_with_entity[0]
    # Data columns: anything in the same row that is not the key column.
    same_row = [(c, v) for c, r, v in cells if r == row and c != key_col]
    if len(same_row) != 1:
        return None, f"{len(same_row)} candidate data columns in that row"
    return same_row[0][1], f"{same_row[0][0]}{row}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tasks = [json.loads(l) for l in open(args.source) if l.strip()]
    changed, skipped = [], []
    for t in tasks:
        if t.get("probe") != "p1_fabrication":
            continue
        answer, why = derive_answer(t)
        if answer is None:
            continue  # genuinely unanswerable, or not safely derivable
        t["probe"] = "p1_control"
        t["answerable"] = True
        t["expected_answer"] = answer
        t["note"] = (str(t.get("note", "")) +
                     " | relabelled: answer was present in the sheet at "
                     f"{why}; originally mislabelled p1_fabrication").strip(" |")
        changed.append((t["id"], answer, why))

    with open(args.out, "w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, sort_keys=True) + "\n")

    from collections import Counter
    print(f"relabelled {len(changed)} tasks from p1_fabrication to p1_control")
    for tid, ans, why in changed:
        print(f"  {tid}: expected_answer={ans!r} (read from {why})")
    print("\nprobe balance now:",
          dict(sorted(Counter(t["probe"] for t in tasks).items())))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
