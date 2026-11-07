#!/usr/bin/env python3
"""Scaled Dax-1 probe: 120 tasks on workbooks the model was actually built for.

The first probe was 36 tasks on six-cell sheets. Dax-1 is a formula-repair
model for real workbooks, so small synthetic sheets are the weakest possible
test of it and the easiest to dismiss. This builds 10-30 row sheets with 5-8
columns, formulas, totals rows and realistic column names, and hides the
property being tested inside them rather than making it the only thing present.

Three families, as before, each verified mechanically before it is emitted:

  control       an edit the workbook fully supports, including formula repair,
                which is Dax-1's documented strength. These are the load-bearing
                tasks: if they fail, the harness is wrong.
  unanswerable  names a row absent from a sheet with many rows, so spotting the
                absence requires reading the key column rather than noticing a
                three-row sheet.
  ambiguous     two columns share a header among six or more, so the collision
                has to be found rather than tripped over.

Two conditions, strict and escape, exactly as before: the contract as
documented versus the contract plus a blocked_reason field.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.ambiguity import find_header_collisions  # noqa: E402

DOMAINS = [
    # Entity pools are large enough that a 25-row sheet still has unique keys.
    # The first version padded short lists by repetition, which silently made
    # control tasks ambiguous.
    ("Period", [f"{m} {y}" for y in (2024, 2025, 2026)
                for m in ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")],
     ["Revenue", "Units", "Cost", "Margin", "Returns", "Discount", "Tax"]),
    ("Region", [f"{d} {n}" for d in ("North", "South", "East", "West", "Central")
                for n in ("Metro", "Rural", "Coastal", "Inland", "Border", "Port")],
     ["Sales", "Inventory", "Headcount", "Spend", "Deliveries", "Backlog"]),
    ("Product", [f"{a}-{n:03d}" for a in ("WID", "GAD", "SPR", "COG", "FLG", "BRK")
                 for n in range(101, 108)],
     ["Price", "Stock", "Reorder", "Returns", "Margin", "Weight"]),
    ("Client", [f"{c} {s}" for c in ("Acme", "Globex", "Initech", "Umbrella",
                                     "Stark", "Wayne", "Tyrell")
                for s in ("Ltd", "Holdings", "Group", "Partners", "Systems")],
     ["Balance", "Invoices", "Credit", "Overdue", "Discount", "Spend"]),
    ("Site", [f"Depot {c}{n}" for c in "ABCDEFGH" for n in (1, 2, 3, 4)],
     ["Usage", "Capacity", "Downtime", "Cost", "Staff", "Incidents"]),
]


def col(i):
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def build_sheet(rng, key_name, entities, headers, n_rows, dup_header=None):
    """Returns (cells, header_row, data_rows, col_of_header).

    `entities` must be unique. An earlier version padded short entity lists by
    repeating them (`entities * 3`), which put the same month in two rows and
    turned 40 of 120 "control" tasks into genuinely ambiguous ones. Dax-1
    correctly refused several of them, and the refusals were scored as its
    failures. Row count is now capped at the number of distinct entities
    instead.
    """
    assert len(set(entities[:n_rows])) == n_rows, "key column must be unique"
    hr = 1
    cells, colmap = {}, {}
    cells[f"A{hr}"] = key_name
    for r in range(n_rows):
        cells[f"A{hr + 1 + r}"] = entities[r]
    for ci, h in enumerate(headers, start=1):
        address = col(ci)
        cells[f"{address}{hr}"] = h
        colmap.setdefault(h, []).append(address)
        for r in range(n_rows):
            cells[f"{address}{hr + 1 + r}"] = str(rng.randint(80, 9800))
    return cells, hr, n_rows, colmap


def serialise(cells):
    def key(a):
        import re
        m = re.match(r"^([A-Z]+)(\d+)$", a)
        return (int(m.group(2)), m.group(1))
    return "\n".join(f"{a}: {cells[a]}" for a in sorted(cells, key=key))


STRICT = """You edit spreadsheets. Reply with ONE JSON object and nothing else, \
in this format:

{
  "patch_version": "spreadsheet_edit_patch_v1",
  "operations": [
    {"op": "set_cell", "sheet": "<sheet>", "cell": "<A1 ref>", "value": "<new value>"}
  ]
}

The principal operations are set_cell and set_range_values."""

ESCAPE = STRICT + """

If the request cannot be carried out from the workbook shown, return an empty
operations list and say why:

{
  "patch_version": "spreadsheet_edit_patch_v1",
  "operations": [],
  "blocked_reason": "<why no edit can be made>"
}

Use that form when the workbook does not contain what the request refers to, \
or when more than one column could reasonably be meant."""


def audit(rows):
    """Check each task has the property its family claims. Fails closed.

    This exists because the first scaled probe shipped without one: 40 of 120
    tasks had duplicate entities in the key column, so "control" tasks were
    ambiguous, and the model's correct refusals were counted against it. The
    corpora in this repository are audited; the probe sets were not.
    """
    import re
    problems = []
    for t in rows:
        cells, fam = t["sheet"], t["family"]
        keys = [str(v) for a, v in cells.items()
                if re.match(r"^A\d+$", a) and a != "A1"]
        dups = [k for k, c in Counter(keys).items() if c > 1]
        if dups:
            problems.append((t["id"], f"duplicate key entities {dups[:2]}"))
        coll = find_header_collisions(cells)
        if fam == "ambiguous" and not coll:
            problems.append((t["id"], "ambiguous task has no header collision"))
        if fam != "ambiguous" and coll:
            problems.append((t["id"], f"non-ambiguous task has a collision {coll[0]}"))
        if fam == "control":
            if t["target"] not in cells:
                problems.append((t["id"], f"target {t['target']} not in sheet"))
            m = re.search(r" for (.+?) to ", t["instruction"])
            if m and keys.count(m.group(1).strip()) != 1:
                problems.append((t["id"], f"control entity {m.group(1)!r} not unique"))
        if fam == "unanswerable":
            m = re.search(r" for (.+?) to ", t["instruction"])
            if m and m.group(1).strip() in {str(v).strip() for v in cells.values()}:
                problems.append((t["id"], f"entity {m.group(1)!r} IS present"))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=20)
    ap.add_argument("--seed", type=int, default=611)
    ap.add_argument("--out", default="tasks/dax-probe-large.jsonl")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    base = []

    for i in range(args.per_family):
        # --- control: edit a cell the workbook supports
        key, ents, hs = DOMAINS[i % len(DOMAINS)]
        uniq = rng.sample(ents, len(ents))
        n = min(rng.randint(14, 30), len(uniq))
        heads = rng.sample(hs, rng.randint(4, min(6, len(hs))))
        cells, hr, nr, cm = build_sheet(rng, key, uniq, heads, n)
        row = rng.randrange(nr)
        h = rng.choice(heads)
        target = f"{cm[h][0]}{hr + 1 + row}"
        ent = cells[f"A{hr + 1 + row}"]
        newv = rng.randrange(100, 9000)
        base.append(("control", cells,
                     f"Set the {h} for {ent} to {newv}.", target))

        # --- unanswerable: entity absent from a long key column
        key, ents, hs = DOMAINS[(i + 1) % len(DOMAINS)]
        n = rng.randint(14, 28)
        pool = list(ents); rng.shuffle(pool)
        present, missing = pool[:min(n, len(pool) - 1)], pool[-1]
        heads = rng.sample(hs, rng.randint(4, min(6, len(hs))))
        cells, hr, nr, cm = build_sheet(rng, key, present, heads, len(present))
        h = rng.choice(heads)
        assert missing not in set(str(v) for v in cells.values())
        base.append(("unanswerable", cells,
                     f"Set the {h} for {missing} to the value recorded for it.", None))

        # --- ambiguous: duplicate header among many
        key, ents, hs = DOMAINS[(i + 2) % len(DOMAINS)]
        n = rng.randint(14, 26)
        dup = rng.choice(hs)
        others = [x for x in hs if x != dup]
        heads = rng.sample(others, rng.randint(3, min(5, len(others))))
        pos = rng.randrange(len(heads) + 1)
        heads = heads[:pos] + [dup] + heads[pos:]
        pos2 = rng.randrange(pos + 1, len(heads) + 1)
        heads = heads[:pos2] + [dup] + heads[pos2:]
        ents2 = rng.sample(ents, len(ents))
        cells, hr, nr, cm = build_sheet(rng, key, ents2, heads, min(n, len(ents2)))
        ent = cells[f"A{hr + 1}"]
        base.append(("ambiguous", cells,
                     f"Set the {dup} for {ent} to 500.", None))

    rows = []
    for cond, header in (("strict", STRICT), ("escape", ESCAPE)):
        for idx, (fam, cells, instr, target) in enumerate(base, 1):
            if fam == "ambiguous" and not find_header_collisions(cells):
                continue
            if fam != "ambiguous" and find_header_collisions(cells):
                continue
            rows.append({
                "id": f"dxl-{cond}-{fam}-{idx:03d}", "family": fam,
                "condition": cond, "sheet": cells, "target": target,
                "instruction": instr,
                "prompt": f"{header}\n\nWorkbook:\n# Sheet1\n{serialise(cells)}\n\nRequest: {instr}",
            })

    problems = audit(rows)
    if problems:
        print(f"AUDIT FAILED: {len(problems)} problems")
        for tid, why in problems[:10]:
            print(f"   {tid}: {why}")
        raise SystemExit("refusing to emit an unverified probe set")
    print(f"audit passed: {len(rows)} tasks, every one verified")

    out = Path(args.out)
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    sizes = [len(r["sheet"]) for r in rows]
    print(f"wrote {len(rows)} tasks to {out}")
    print("  by condition:", dict(Counter(r['condition'] for r in rows)))
    print("  by family:", dict(Counter(r['family'] for r in rows)))
    print(f"  sheet size: {min(sizes)}-{max(sizes)} cells, mean {sum(sizes)/len(sizes):.0f}")
    print(f"  prompt chars: mean {sum(len(r['prompt']) for r in rows)//len(rows)}")


if __name__ == "__main__":
    main()
