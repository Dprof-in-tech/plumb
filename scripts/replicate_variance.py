#!/usr/bin/env python3
"""Report run-to-run variance across replicates, and which tasks are unstable.

This exists because the project's practice of citing "three identical
replicates at temperature 0" turned out to be unsafe. Replicate identity held
for some model/file/machine combinations and not others: the base model
reproduced bit-identically across five local runs, and the same model from the
vendor GGUF on a GPU does not reproduce against itself.

Greedy decoding is not bit-reproducible on GPU -- reduction order can vary with
batching, and a task whose top two logits are near-tied will flip. With 16
tasks per probe, one flipped task is 6.25 percentage points, which is the same
size as most of the deltas this benchmark discusses. So a single run is not a
measurement, and identical replicates are not evidence about the harness.

Report metrics as a range over replicates, and list the boundary tasks.

Usage:
    python3 scripts/replicate_variance.py runs/sweep-global-1.jsonl runs/sweep-global-2.jsonl
    python3 scripts/replicate_variance.py --label global runs/sweep-global-*.jsonl
"""

import argparse
import json
from collections import Counter, defaultdict

METRICS = [
    ("fabricated", "fabrication_rate"),
    ("silent_guess", "silent_guess_rate"),
    ("collateral", "collateral_write_rate"),
    ("over_refused", "over_refusal_rate"),
    ("completed", "completion_rate"),
]


def load(path):
    rows = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                rows[r["task_id"]] = r
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    reps = [load(p) for p in args.runs]
    names = [p.split("/")[-1].replace(".jsonl", "") for p in args.runs]
    ids = sorted(set.intersection(*(set(r) for r in reps)))

    print(f"{args.label or 'model'}: {len(reps)} replicates, {len(ids)} common tasks")
    print(f"  {', '.join(names)}\n")

    header = f"{'metric':<24}{'n':>4}" + "".join(f"{n[-6:]:>10}" for n in names) + \
             f"{'range':>10}{'spread':>9}"
    print(header)
    print("-" * len(header))

    spreads = {}
    for field, label in METRICS:
        scored = [i for i in ids if all(r[i][field] is not None for r in reps)]
        if not scored:
            continue
        rates = [100 * sum(1 for i in scored if r[i][field]) / len(scored) for r in reps]
        spread = max(rates) - min(rates)
        spreads[label] = spread
        mark = "  <--" if spread > 0 else ""
        print(f"{label:<24}{len(scored):>4}" +
              "".join(f"{x:>9.1f}%" for x in rates) +
              f"{min(rates):>5.1f}-{max(rates):<4.1f}{spread:>8.1f}{mark}")

    # Which tasks disagree with themselves across replicates?
    #
    # Comparing `status` alone is not enough, and getting this wrong once
    # already hid an instability: on curator-1-023 two runs both returned
    # `answered` but wrote to different cells (B2 vs C2), so the status matched
    # while collateral_write_rate moved. A task is unstable if the status OR
    # any scored flag differs.
    FLAGS = ["status"] + [f for f, _ in METRICS]
    unstable = defaultdict(list)
    for i in ids:
        sigs = [tuple(r[i].get(f) for f in FLAGS) for r in reps]
        if len(set(sigs)) > 1:
            which = [f for f in FLAGS
                     if len({r[i].get(f) for r in reps}) > 1]
            unstable[i] = (
                [r[i]["status"] for r in reps],
                which,
                [r[i].get("stray_cells") for r in reps] if "collateral" in which else None,
            )

    print(f"\nboundary tasks (status or any scored flag differs): "
          f"{len(unstable)}/{len(ids)}")
    for i, (sts, which, stray) in sorted(unstable.items()):
        probe = reps[0][i]["probe"]
        print(f"  {i:<22} {probe:<16} {' | '.join(sts)}")
        print(f"      differs on: {', '.join(which)}"
              + (f"   stray_cells: {stray}" if stray else ""))

    if not unstable:
        print("  none -- every task returned the same status in every replicate")
        print("  (evidence about THIS model on THIS path, not about the harness)")
    else:
        worst_metric = max(spreads, key=spreads.get)
        print(f"\n  worst spread from run-to-run variance alone: "
              f"{spreads[worst_metric]:.1f} pp on {worst_metric}")
        print("  Report ranges, not point estimates. Do not read a delta "
              "smaller than this as an effect.")


if __name__ == "__main__":
    main()
