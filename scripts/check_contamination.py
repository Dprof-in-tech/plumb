#!/usr/bin/env python3
"""Check that training data and evaluation data do not share tasks.

This check exists because this project trained all three of its interventions
on its own locked benchmark and did not notice for four days. The apparent
result was a modest, well-replicated improvement -- the most believable kind of
wrong number. Nothing in the metrics, the guards, or three identical replicates
could have revealed it, because memorising the test set is a real effect that
reproduces perfectly.

Matching is deliberately paranoid: exact ids, ids after stripping a trailing
suffix (our DPO pairs were benchmark ids plus "-p1"), and substring containment
of each eval instruction in each training prompt (our pair prompts embedded the
full benchmark prompt). Any one of those firing is contamination.

Usage:
    python3 scripts/check_contamination.py --eval tasks/benchmark.jsonl \
        --train tasks/sft.jsonl tasks/pairs.jsonl
"""

import argparse
import json
import re
import sys


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ids_of(rows):
    out = set()
    for r in rows:
        for key in ("id", "task_id"):
            if r.get(key):
                out.add(str(r[key]))
        meta = r.get("metadata") or {}
        if meta.get("task_id"):
            out.add(str(meta["task_id"]))
    return out


def text_of(row):
    """Everything in a training row a prompt could be hiding in."""
    parts = []
    for key in ("prompt", "instruction", "text", "chosen", "rejected", "completion"):
        v = row.get(key)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True, help="the held-out / benchmark task file")
    ap.add_argument("--train", required=True, nargs="+", help="training data files")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ev = load(args.eval)
    ev_ids = ids_of(ev)
    ev_instr = {r["id"]: r["instruction"] for r in ev if r.get("instruction")}

    worst = 0
    for path in args.train:
        tr = load(path)
        tr_ids = ids_of(tr)

        exact = ev_ids & tr_ids
        stripped = {
            i for i in tr_ids
            if re.sub(r"-[a-z0-9]+$", "", i) in ev_ids and i not in ev_ids
        }
        embedded = {}
        for r in tr:
            blob = text_of(r)
            for tid, instr in ev_instr.items():
                if instr and instr in blob:
                    embedded.setdefault(tid, 0)
                    embedded[tid] += 1

        n_bad = len(exact) + len(stripped) + len(embedded)
        worst = max(worst, n_bad)
        status = "CONTAMINATED" if n_bad else "clean"
        print(f"{path}: {len(tr)} rows -> {status}")
        if exact:
            print(f"  exact id overlap: {len(exact)}/{len(tr)}")
            if not args.quiet:
                print(f"    e.g. {sorted(exact)[:5]}")
        if stripped:
            print(f"  id overlap after stripping a suffix: {len(stripped)}/{len(tr)}")
            if not args.quiet:
                print(f"    e.g. {sorted(stripped)[:5]}")
        if embedded:
            print(f"  eval instructions embedded in training text: "
                  f"{len(embedded)} distinct eval tasks")
            if not args.quiet:
                print(f"    e.g. {sorted(embedded)[:5]}")
        if r_uri := {r.get("source_uri") for r in tr if r.get("source_uri")}:
            print(f"  declared source_uri: {sorted(r_uri)}")

    if worst:
        print("\nTraining data overlaps the evaluation set. Any before/after "
              "measured this way is a memorisation score, not a "
              "generalisation result.")
        return 1
    print("\nNo overlap found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
