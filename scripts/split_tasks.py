#!/usr/bin/env python3
"""Leak-free train/test split of a PLUMB task file.

Exists because all three of this project's interventions were trained on the
full locked benchmark and then evaluated on it, making their deltas a
memorisation score rather than a generalisation result.

A naive stratified split is not enough here. The 96-task benchmark has only 82
distinct instructions and 46 distinct sheets, so tasks reuse both: a random
split put 4 exact (instruction, sheet) duplicates on both sides, and left 23 of
48 test tasks sharing a sheet with a training task. A model that has seen a
sheet is not being tested on unseen data even if the question differs.

So tasks are grouped first. Any two tasks sharing an instruction *or* a sheet
land in the same group (transitively), and whole groups are assigned to one
side. Groups are then placed greedily, largest first, into whichever side is
furthest below its per-probe quota, which keeps the six-category balance
approximately intact without ever splitting a group.

Usage:
    python3 scripts/split_tasks.py tasks/phase2-curatorkit-generated-96-p2v3.jsonl \
        --train tasks/split-train.jsonl --test tasks/split-test.jsonl
"""

import argparse
import json
import random
from collections import Counter, defaultdict


def components(rows, keys):
    """Union-find over tasks sharing any of `keys`."""
    parent = {r["id"]: r["id"] for r in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for key in keys:
        buckets = defaultdict(list)
        for r in rows:
            buckets[json.dumps(r[key], sort_keys=True)].append(r["id"])
        for ids in buckets.values():
            for i in ids[1:]:
                union(ids[0], i)

    groups = defaultdict(list)
    for r in rows:
        groups[find(r["id"])].append(r)
    return list(groups.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks")
    ap.add_argument("--train", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--seed", type=int, default=1105)
    ap.add_argument("--train-frac", type=float, default=0.5)
    ap.add_argument("--group-keys", nargs="*", default=["instruction", "sheet"],
                    help="tasks sharing any of these go to the same side")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.tasks) if l.strip()]
    probes = sorted({r["probe"] for r in rows})
    total = Counter(r["probe"] for r in rows)
    quota = {p: total[p] * args.train_frac for p in probes}

    groups = components(rows, args.group_keys)
    rng = random.Random(args.seed)
    rng.shuffle(groups)
    # Largest first: big groups have the least placement freedom.
    groups.sort(key=len, reverse=True)

    train, test = [], []
    have = Counter()

    def deficit(group):
        """How far placing this group in train keeps us under quota."""
        return sum(quota[p] - have[p] for p in {r["probe"] for r in group})

    for g in groups:
        gp = Counter(r["probe"] for r in g)
        over = sum(max(0, have[p] + gp[p] - quota[p]) for p in gp)
        if over > 0 and len(train) >= len(rows) * args.train_frac:
            test.extend(g)
            continue
        if deficit(g) > 0 and len(train) < len(rows) * args.train_frac:
            train.extend(g)
            have.update(gp)
        else:
            test.extend(g)

    train.sort(key=lambda r: r["id"])
    test.sort(key=lambda r: r["id"])

    # Hard guarantees, not hopes.
    tr_ids = {r["id"] for r in train}
    te_ids = {r["id"] for r in test}
    assert not (tr_ids & te_ids), "id leak"
    assert len(tr_ids) + len(te_ids) == len(rows), "lost tasks"
    for key in args.group_keys:
        a = {json.dumps(r[key], sort_keys=True) for r in train}
        b = {json.dumps(r[key], sort_keys=True) for r in test}
        assert not (a & b), f"{key} leak: {len(a & b)} shared"

    for path, out in ((args.train, train), (args.test, test)):
        with open(path, "w") as f:
            for r in out:
                f.write(json.dumps(r, sort_keys=True) + "\n")

    print(f"seed {args.seed}, grouped by {args.group_keys}")
    print(f"{len(groups)} groups -> {len(train)} train / {len(test)} test")
    for name, out in (("train", train), ("test", test)):
        c = Counter(r["probe"] for r in out)
        print(f"  {name}: " + "  ".join(f"{p}={c[p]}" for p in probes))
    print("no shared ids, instructions, or sheets across the split")


if __name__ == "__main__":
    main()
