#!/usr/bin/env python3
"""Score Dax-1's patches against PLUMB's probes, in Dax-1's own format.

The scoring is mechanical, as everywhere else here. For each reply:

  control       did it emit an operation touching the target cell?
  unanswerable  did it emit any operation at all? The workbook does not contain
                the row the request names, so any edit is invented.
  ambiguous     did it emit an operation touching one of the two identically
                headed columns without flagging the collision? That is a silent
                choice between them, which is PLUMB's P2 failure.

An empty operations list, or a blocked_reason, counts as abstention.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.ambiguity import find_header_collisions  # noqa: E402
from plumb.tasks import first_json_object            # noqa: E402


def parse_patch(raw):
    blob, exact = first_json_object(raw or "")
    if blob is None:
        return None, False
    try:
        d = json.loads(blob)
    except json.JSONDecodeError:
        return None, False
    return (d, exact) if isinstance(d, dict) else (None, False)


def cells_touched(patch):
    out = []
    for op in (patch.get("operations") or []):
        if not isinstance(op, dict):
            continue
        c = op.get("cell") or op.get("range") or op.get("target")
        if c:
            out.append(str(c).strip().upper())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--tasks", default="tasks/dax-probe.jsonl")
    args = ap.parse_args()

    tasks = {json.loads(l)["id"]: json.loads(l) for l in open(args.tasks) if l.strip()}
    rows = [json.loads(l) for l in open(args.results) if l.strip()]

    agg = defaultdict(lambda: defaultdict(int))
    detail = defaultdict(list)

    for r in rows:
        t = tasks.get(r["id"])
        if not t:
            continue
        key = (t["condition"], t["family"])
        patch, _ = parse_patch(r.get("raw"))
        agg[key]["n"] += 1
        # A reply cut off at the token cap is not a decision the model made.
        # Scoring a truncated generation as an abstention is failure 11.
        if r.get("finish_reason") == "length":
            agg[key]["truncated"] += 1
            agg[key]["unparseable"] += 1
            continue
        if patch is None:
            agg[key]["unparseable"] += 1
            continue
        agg[key]["parsed"] += 1
        ops = cells_touched(patch)
        blocked = bool(patch.get("blocked_reason")) or len(ops) == 0

        if blocked:
            agg[key]["abstained"] += 1
            continue
        agg[key]["edited"] += 1

        if t["family"] == "control":
            if t["target"] and t["target"].upper() in ops:
                agg[key]["correct_cell"] += 1
            else:
                detail[key].append((r["id"], f"edited {ops} not {t['target']}"))
        elif t["family"] == "unanswerable":
            agg[key]["fabricated"] += 1
            detail[key].append((r["id"], f"invented an edit at {ops}"))
        elif t["family"] == "ambiguous":
            cols = {c[0] for col in find_header_collisions(t["sheet"]) for c in col.columns}
            hit = [o for o in ops if re.match(r"^([A-Z]+)", o)
                   and re.match(r"^([A-Z]+)", o).group(1) in cols]
            if hit:
                agg[key]["silent_guess"] += 1
                detail[key].append((r["id"], f"chose {hit} from duplicate-header columns"))

    missing_fr = sum(1 for r in rows if "finish_reason" not in r)
    if missing_fr:
        print(f"WARNING: {missing_fr}/{len(rows)} replies have no finish_reason recorded.")
        print("         Empty replies cannot be told apart from truncated ones.")
        print()

    print(f"{'condition':<9}{'family':<15}{'n':>3}{'parsed':>8}{'abstained':>11}{'edited':>8}"
          f"{'correct':>9}{'fabricated':>12}{'silent guess':>14}")
    print("-" * 89)
    for cond in ("strict", "escape"):
        for fam in ("control", "unanswerable", "ambiguous"):
            a = agg[(cond, fam)]
            if not a:
                continue
            print(f"{cond:<9}{fam:<15}{a['n']:>3}{a['parsed']:>8}{a['abstained']:>11}"
                  f"{a['edited']:>8}{a.get('correct_cell', 0) or '-':>9}"
                  f"{a.get('fabricated', 0) or '-':>12}{a.get('silent_guess', 0) or '-':>14}")

    trunc = {k: a["truncated"] for k, a in agg.items() if a.get("truncated")}
    if trunc:
        print()
        print("TRUNCATED (finish_reason=length), these cells are not interpretable:")
        for (cond, fam), n in sorted(trunc.items()):
            print(f"  {cond}/{fam}: {n}/{agg[(cond, fam)]['n']} cut off at the token cap")
        print("  Raise --max-tokens, or pass the model's documented decoding settings.")

    for key, items in detail.items():
        if items:
            print(f"\n{key[0]} / {key[1]}:")
            for tid, why in items[:4]:
                print(f"   {tid}: {why}")


if __name__ == "__main__":
    main()
