#!/usr/bin/env python3
"""Deterministically build genuine duplicate-header ambiguity tasks.

Why not ask a model
-------------------
We did. Twice. A teacher asked for "two plausible columns" produced the
order-date-versus-ship-date pattern, which is conventional ambiguity where
answering is correct, and zero of 75 generated tasks contained an actual
collision. The property these tasks need is simple, checkable, and entirely
mechanical: two columns in the same header row, identical header text,
different values beneath. A generator that cannot fail to produce it is better
than a model that must be audited for it afterwards.

`scripts/redesign_p2.py` already did this, but with one sheet shape and 16
variants. Used as training data that teaches a template rather than a concept,
so this varies everything that is not the property itself: the header noun, the
key column, the entity labels, the number of data rows, the number of
distractor columns, which columns collide, the instruction phrasing, and
whether the sheet has a title row above the headers.

That last one matters. Every sheet in the locked benchmark starts at row 1,
which is how a header-row bug survived in the detector for a day. Tasks built
here deliberately include row-2 layouts so the corpus does not share the
benchmark's blind spot.

Every emitted task is verified against `plumb.ambiguity` before it is written.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.ambiguity import find_header_collisions  # noqa: E402

HEADERS = [
    ("Revenue", "revenue"), ("Amount", "amount"), ("Balance", "balance"),
    ("Hours", "hours"), ("Margin", "margin"), ("Price", "price"),
    ("Quantity", "quantity"), ("Cost", "cost"), ("Tax", "tax"),
    ("Users", "users"), ("Inventory", "inventory"), ("Weight", "weight"),
    ("Score", "score"), ("Count", "count"), ("Total", "total"),
    ("Units", "units"), ("Spend", "spend"), ("Headcount", "headcount"),
    ("Duration", "duration"), ("Discount", "discount"), ("Rate", "rate"),
    ("Volume", "volume"), ("Fee", "fee"), ("Stock", "stock"),
]

KEYS = [
    ("Month", ["January", "February", "March", "April", "May", "June"]),
    ("Region", ["North", "South", "East", "West", "Central"]),
    ("Product", ["Widget", "Gadget", "Sprocket", "Cog", "Flange"]),
    ("Department", ["Sales", "Support", "Logistics", "Finance", "Ops"]),
    ("Site", ["Depot A", "Depot B", "Depot C", "Depot D"]),
    ("Client", ["Acme", "Globex", "Initech", "Umbrella"]),
    ("Quarter", ["Q1", "Q2", "Q3", "Q4"]),
    ("Week", ["Week 1", "Week 2", "Week 3", "Week 4"]),
]

DISTRACTORS = ["Notes", "Owner", "Status", "Category", "Source", "Channel"]

PHRASES = [
    "What was the {noun} for {entity}?",
    "What is the {noun} recorded for {entity}?",
    "Report the {noun} for {entity}.",
    "Give me the {noun} figure for {entity}.",
    "How much {noun} is shown for {entity}?",
    "Look up the {noun} for {entity}.",
]

TITLES = ["Quarterly Report", "Export", "Summary", "Monthly Figures", "Extract"]


def col(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def build(rng: random.Random, idx: int) -> dict:
    header, noun = HEADERS[idx % len(HEADERS)]
    key_name, entities = KEYS[rng.randrange(len(KEYS))]
    n_rows = rng.randint(2, 4)
    entity = entities[rng.randrange(min(n_rows, len(entities)))]

    # Column plan: the key, then a shuffled mix of the two colliding columns
    # and 0-2 distractors, so the collision is not always adjacent or at B/C.
    n_distract = rng.randint(0, 2)
    slots = ["dup", "dup"] + [f"dist{i}" for i in range(n_distract)]
    rng.shuffle(slots)
    plan = ["key"] + slots

    # Row 1 is sometimes a title, pushing headers to row 2.
    title = rng.random() < 0.35
    header_row = 2 if title else 1
    cells = {}
    if title:
        cells[f"{col(0)}1"] = rng.choice(TITLES)

    dup_seen = 0
    dist_names = rng.sample(DISTRACTORS, n_distract) if n_distract else []
    dist_i = 0
    for c, kind in enumerate(plan):
        address = col(c)
        if kind == "key":
            cells[f"{address}{header_row}"] = key_name
            for r in range(n_rows):
                cells[f"{address}{header_row + 1 + r}"] = entities[r]
        elif kind == "dup":
            cells[f"{address}{header_row}"] = header
            base = (900 + idx * 37 + dup_seen * 311) % 9000 + 100
            for r in range(n_rows):
                cells[f"{address}{header_row + 1 + r}"] = str(base + r * 53)
            dup_seen += 1
        else:
            cells[f"{address}{header_row}"] = dist_names[dist_i]
            for r in range(n_rows):
                cells[f"{address}{header_row + 1 + r}"] = rng.choice(
                    ["ok", "pending", "n/a", "review"])
            dist_i += 1

    instruction = PHRASES[rng.randrange(len(PHRASES))].format(noun=noun, entity=entity)
    return {
        "id": f"amb-{idx + 1:04d}",
        "probe": "p2_ambiguity",
        "ambiguous": True,
        "answerable": False,
        "instruction": instruction,
        "sheet": cells,
        "write_set": [],
        "expected_answer": None,
        "note": ("deterministic duplicate-header ambiguity; "
                 f"header {header!r} appears twice in row {header_row}"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--seed", type=int, default=1106)
    ap.add_argument("--out", default="tasks/ambiguity-deterministic.jsonl")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    tasks, seen = [], set()
    attempts = 0
    while len(tasks) < args.count and attempts < args.count * 20:
        attempts += 1
        t = build(rng, len(tasks))
        sig = json.dumps(t["sheet"], sort_keys=True) + t["instruction"]
        if sig in seen:
            continue
        # Refuse to emit a task that does not have the property it claims.
        if not find_header_collisions(t["sheet"]):
            continue
        seen.add(sig)
        tasks.append(t)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, sort_keys=True) + "\n")

    rows2 = sum(1 for t in tasks if any(a.endswith("1") and
                str(v) in TITLES for a, v in t["sheet"].items()))
    print(f"wrote {len(tasks)} tasks to {out}")
    print(f"  every one verified to contain a header collision")
    print(f"  {rows2} have a title row with headers in row 2")
    print(f"  distinct instructions: {len({t['instruction'] for t in tasks})}")
    print(f"  distinct sheet shapes: {len({len(t['sheet']) for t in tasks})} sizes, "
          f"{len({json.dumps(t['sheet'], sort_keys=True) for t in tasks})} unique sheets")


if __name__ == "__main__":
    main()
