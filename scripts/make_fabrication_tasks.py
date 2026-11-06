#!/usr/bin/env python3
"""Deterministically build genuinely unanswerable tasks.

Why deterministic
-----------------
A teacher asked for unanswerable tasks produced answerable ones: 29 of 81 in
one corpus, and 7 of 16 in the locked benchmark itself, where a task asking for
July's invoice amount sat next to July and the amount. "The sheet does not
contain what the question needs" is a mechanical property, so it is constructed
here and verified per task, the same way the ambiguity tasks are.

The construction is simple and total: build a sheet over a set of entities,
then ask about an entity deliberately left out of it. There is no value to
read, nothing to compute from the prompt, and no column that could stand in.

Variation covers everything except that property: domain, header names, entity
type, row count, distractor columns, phrasing, and whether a title row pushes
the headers to row 2. The locked benchmark has none of those layouts, which is
how a header-row bug survived in the detector; a training corpus should not
inherit the same blind spot.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_CELL = re.compile(r"^([A-Z]+)(\d+)$")

DOMAINS = [
    ("Month", ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"],
     [("Sales", "sales"), ("Revenue", "revenue"), ("Units Sold", "units sold"),
      ("Invoice Amount", "invoice amount"), ("Staff", "number of staff")]),
    ("Region", ["North", "South", "East", "West", "Central", "Coastal"],
     [("Inventory", "inventory"), ("Deliveries", "deliveries"),
      ("Headcount", "headcount"), ("Spend", "spend")]),
    ("Department", ["Sales", "Support", "Logistics", "Finance", "Engineering", "Legal"],
     [("Hours", "hours logged"), ("Budget", "budget"), ("Headcount", "headcount")]),
    ("Product", ["Widget", "Gadget", "Sprocket", "Cog", "Flange", "Bracket"],
     [("Price", "price"), ("Stock", "stock level"), ("Returns", "returns")]),
    ("Client", ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne"],
     [("Balance", "outstanding balance"), ("Invoices", "number of invoices")]),
]

PHRASES = [
    "What was the {noun} for {missing}?",
    "What is the {noun} recorded for {missing}?",
    "Report the {noun} for {missing}.",
    "How much {noun} is shown for {missing}?",
    "Give me the {noun} for {missing}.",
]

DISTRACTORS = ["Notes", "Owner", "Status", "Category", "Channel"]
TITLES = ["Quarterly Report", "Export", "Summary", "Extract", "Monthly Figures"]


def col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def build(rng: random.Random, idx: int) -> dict:
    key_name, entities, metrics = DOMAINS[idx % len(DOMAINS)]
    header, noun = metrics[rng.randrange(len(metrics))]
    pool = list(entities)
    rng.shuffle(pool)
    n_rows = rng.randint(2, 4)
    present, missing = pool[:n_rows], pool[n_rows]

    title = rng.random() < 0.35
    hr = 2 if title else 1
    cells = {}
    if title:
        cells[f"{col(0)}1"] = rng.choice(TITLES)

    n_dist = rng.randint(0, 2)
    plan = ["key", "data"] + [f"d{i}" for i in range(n_dist)]
    dist_names = rng.sample(DISTRACTORS, n_dist) if n_dist else []
    di = 0
    for c, kind in enumerate(plan):
        a = col(c)
        if kind == "key":
            cells[f"{a}{hr}"] = key_name
            for r in range(n_rows):
                cells[f"{a}{hr + 1 + r}"] = present[r]
        elif kind == "data":
            cells[f"{a}{hr}"] = header
            base = (700 + idx * 53) % 9000 + 100
            for r in range(n_rows):
                cells[f"{a}{hr + 1 + r}"] = str(base + r * 71)
        else:
            cells[f"{a}{hr}"] = dist_names[di]
            for r in range(n_rows):
                cells[f"{a}{hr + 1 + r}"] = rng.choice(["ok", "pending", "n/a"])
            di += 1

    return {
        "id": f"fab-{idx + 1:04d}",
        "probe": "p1_fabrication",
        "ambiguous": False,
        "answerable": False,
        "instruction": PHRASES[rng.randrange(len(PHRASES))].format(
            noun=noun, missing=missing),
        "sheet": cells,
        "write_set": [],
        "expected_answer": None,
        "note": (f"deterministic unanswerable; {missing!r} is absent from the "
                 f"{key_name} column"),
    }


def is_unanswerable(task) -> bool:
    """The asked entity must appear nowhere in the sheet."""
    values = {str(v).strip().lower() for v in task["sheet"].values()}
    note = task["note"]
    missing = note.split("'")[1].lower()
    if missing in values:
        return False
    # and nothing in the instruction should be derivable from a single row
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1106)
    ap.add_argument("--out", default="tasks/fabrication-deterministic.jsonl")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    tasks, seen = [], set()
    tries = 0
    while len(tasks) < args.count and tries < args.count * 30:
        tries += 1
        t = build(rng, len(tasks))
        sig = json.dumps(t["sheet"], sort_keys=True) + t["instruction"]
        if sig in seen or not is_unanswerable(t):
            continue
        seen.add(sig)
        tasks.append(t)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, sort_keys=True) + "\n")
    titled = sum(1 for t in tasks if any(str(v) in TITLES for v in t["sheet"].values()))
    print(f"wrote {len(tasks)} unanswerable tasks to {out}")
    print(f"  every one verified: the asked entity is absent from the sheet")
    print(f"  {titled} have a title row with headers in row 2")
    print(f"  distinct instructions: {len({t['instruction'] for t in tasks})}")


if __name__ == "__main__":
    main()
