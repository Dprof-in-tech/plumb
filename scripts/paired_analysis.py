#!/usr/bin/env python3
"""Paired per-task comparison of two runs over the same task set.

The full-set metric tables answer "what rate did each model score?". They
cannot answer "did training change any decision?", because a task can move
between rates for two unrelated reasons: the model decided differently, or the
model's reply stopped parsing and the unparseable-as-failure convention took
over.

This script separates those. For each metric it builds the 2x2 paired table
(both fail, both pass, A-only fail, B-only fail), runs an exact McNemar test on
the discordant pairs, and labels every discordant pair as either a genuine
decision change (both replies parsed) or parse-driven (at least one did not).

Usage:
    python3 scripts/paired_analysis.py runs/a.jsonl runs/b.jsonl
"""

import argparse
import json
from collections import Counter
from math import comb

# (field, metric name, probe prefix the metric is defined on)
METRICS = [
    ("fabricated", "fabrication_rate"),
    ("silent_guess", "silent_guess_rate"),
    ("collateral", "collateral_write_rate"),
    ("over_refused", "over_refusal_rate"),
    ("completed", "completion_rate"),
]


def load(path):
    records = {}
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line:
                record = json.loads(line)
                records[record["task_id"]] = record
    return records


def exact_mcnemar(a_only, b_only):
    """Two-sided exact McNemar: binomial test on discordant pairs at p=0.5.

    Reported two-sided. The one-sided value is half this, and is only
    defensible when the direction was predicted before seeing the data.
    """
    discordant = a_only + b_only
    if discordant == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = sum(comb(discordant, j) for j in range(k + 1)) / 2 ** discordant
    return min(2 * tail, 1.0)


def paired_table(a, b, ids, field):
    """2x2 counts plus the discordant pairs, split by cause."""
    scored = [i for i in ids if a[i][field] is not None and b[i][field] is not None]
    cells = Counter((bool(a[i][field]), bool(b[i][field])) for i in scored)
    decision, parse_driven = [], []
    for i in scored:
        if bool(a[i][field]) != bool(b[i][field]):
            if a[i]["parse_ok"] and b[i]["parse_ok"]:
                decision.append(i)
            else:
                parse_driven.append(i)
    return scored, cells, decision, parse_driven


def report(a, b, ids, title, label_a, label_b):
    print(f"\n=== {title} (n={len(ids)}) ===\n")
    header = (
        f"{'metric':<24}{'n':>4}{'both+':>7}{'both-':>7}"
        f"{'A>B':>5}{'B>A':>5}{label_a[:9]:>10}{label_b[:9]:>10}"
        f"{'p(2-sided)':>12}{'decision':>10}{'parse':>7}"
    )
    print(header)
    print("-" * len(header))
    for field, name in METRICS:
        scored, cells, decision, parse_driven = paired_table(a, b, ids, field)
        n = len(scored)
        if n == 0:
            continue
        both_fail = cells[(True, True)]
        a_only = cells[(True, False)]
        b_only = cells[(False, True)]
        rate_a = 100 * (both_fail + a_only) / n
        rate_b = 100 * (both_fail + b_only) / n
        p = exact_mcnemar(a_only, b_only)
        print(
            f"{name:<24}{n:>4}{both_fail:>7}{cells[(False, False)]:>7}"
            f"{a_only:>5}{b_only:>5}{rate_a:>9.1f}%{rate_b:>9.1f}%"
            f"{p:>12.3f}{len(decision):>10}{len(parse_driven):>7}"
        )
    print(
        "\n  A>B = flagged in A only, B>A = flagged in B only. For completion_rate\n"
        "  the flag is 'completed', so B>A is the improvement; for every other\n"
        "  metric the flag is a failure and A>B is the improvement.\n"
        "  decision = discordant pairs where both replies parsed.\n"
        "  parse = discordant pairs attributable to the unparseable-as-failure\n"
        "  convention rather than to a changed decision."
    )


def detail(a, b, ids):
    print("\n=== discordant pairs, by metric ===")
    for field, name in METRICS:
        _, _, decision, parse_driven = paired_table(a, b, ids, field)
        if not decision and not parse_driven:
            continue
        print(f"\n{name}:")
        for i in decision + parse_driven:
            cause = "DECISION" if i in decision else "parse-driven"
            print(
                f"  {i:<22} A: parse={str(a[i]['parse_ok']):<5} {a[i]['status']:<20}"
                f" | B: parse={str(b[i]['parse_ok']):<5} {b[i]['status']:<20} [{cause}]"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    parser.add_argument("--quiet", action="store_true", help="skip the per-pair listing")
    args = parser.parse_args()

    a, b = load(args.run_a), load(args.run_b)
    ids = sorted(set(a) & set(b))
    if not ids:
        raise SystemExit("no task IDs in common")

    parse_a = sum(1 for i in ids if a[i]["parse_ok"])
    parse_b = sum(1 for i in ids if b[i]["parse_ok"])
    both = [i for i in ids if a[i]["parse_ok"] and b[i]["parse_ok"]]
    print(f"{args.label_a}: parse_ok {parse_a}/{len(ids)}")
    print(f"{args.label_b}: parse_ok {parse_b}/{len(ids)}")
    print(f"both parse_ok: {len(both)}/{len(ids)}")

    report(a, b, ids, "full set, unparseable scored as failure",
           args.label_a, args.label_b)
    report(a, b, both, "paired subset, both replies parsed",
           args.label_a, args.label_b)
    if not args.quiet:
        detail(a, b, ids)


if __name__ == "__main__":
    main()
