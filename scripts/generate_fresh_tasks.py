#!/usr/bin/env python3
"""Generate a fresh training corpus that is disjoint from the locked benchmark.

Why a new generator
-------------------
Every training attempt in this project so far was trained on the benchmark
itself: 96 of 96 task ids shared, recorded in the training files' own
provenance metadata. The apparent win was memorisation and vanished on a
leak-free split.

So the only version of the training experiment that was ever set up correctly
needs data the model has never been evaluated on. This generates it in batches
from a non-Cohere teacher, varies the domain per batch so the corpus is not 400
paraphrases of one sheet, assigns globally unique ids, and then refuses to emit
anything that overlaps the benchmark.

The contamination check is not advisory here. If a generated task duplicates a
benchmark instruction or sheet it is dropped, and the summary says how many
went. A corpus that silently overlaps is worse than no corpus, because it
produces a number that looks like a result.

Usage (designed to run on rented hardware, not a laptop):
    python3 scripts/generate_fresh_tasks.py --target 400 --out tasks/fresh.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_tasks import PROMPT, extract_json  # noqa: E402

# Varied so the corpus is not one spreadsheet restated. Each batch gets one.
DOMAINS = [
    "retail sales by month, with revenue and units columns",
    "warehouse inventory, stock counts and reorder levels",
    "staffing rosters, headcount and hours by department",
    "supplier invoices, amounts due and payment dates",
    "delivery logistics, shipment weights and distances",
    "SaaS subscriptions, seats and monthly recurring revenue",
    "manufacturing output, units produced and defect counts",
    "marketing spend by channel, cost and conversions",
    "school enrolment, students and classroom capacity",
    "clinic appointments, patient counts and durations",
    "energy usage, kilowatt hours and cost per site",
    "fleet maintenance, mileage and service intervals",
]


def generate_batch(count, model, api_base, domain, timeout=900):
    brief = (f"Use spreadsheets about {domain}. "
             "Balance the six probe categories evenly. "
             "Vary column names, row counts and phrasing between tasks.")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(count=count, brief=brief)}],
        "stream": False, "think": False,
        "options": {"temperature": 0.7, "num_predict": 8192},
    }).encode()
    req = urllib.request.Request(api_base, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read())
    return extract_json(payload["message"]["content"])


def key_of(task):
    return (str(task.get("instruction", "")).strip().lower(),
            json.dumps(task.get("sheet", {}), sort_keys=True))


REQUIRED = {"probe", "instruction", "sheet"}
PROBES = {"p1_fabrication", "p1_control", "p2_ambiguity", "p2_control",
          "p3_collateral", "p3_control"}


def usable(t):
    if not REQUIRED.issubset(t):
        return False
    if t.get("probe") not in PROBES:
        return False
    if not isinstance(t.get("sheet"), dict) or len(t["sheet"]) < 2:
        return False
    return bool(str(t.get("instruction", "")).strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=400)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--api-base", default="http://localhost:11434/api/chat")
    ap.add_argument("--benchmark",
                    default="tasks/phase2-curatorkit-generated-96-p2v3.jsonl")
    ap.add_argument("--out", default="tasks/fresh-training-tasks.jsonl")
    ap.add_argument("--max-batches", type=int, default=60)
    args = ap.parse_args()

    bench = [json.loads(l) for l in open(args.benchmark) if l.strip()]
    bench_keys = {key_of(t) for t in bench}
    bench_instr = {str(t["instruction"]).strip().lower() for t in bench}
    bench_sheets = {json.dumps(t["sheet"], sort_keys=True) for t in bench}
    print(f"benchmark: {len(bench)} tasks, {len(bench_instr)} distinct instructions, "
          f"{len(bench_sheets)} distinct sheets")

    kept, seen = [], set()
    dropped = {"malformed": 0, "duplicate": 0, "overlaps_benchmark": 0}
    batches = 0

    while len(kept) < args.target and batches < args.max_batches:
        domain = DOMAINS[batches % len(DOMAINS)]
        batches += 1
        try:
            cands = generate_batch(args.batch, args.model, args.api_base, domain)
        except Exception as exc:
            print(f"  batch {batches} ({domain[:28]}): FAILED {type(exc).__name__}")
            continue
        added = 0
        for t in cands:
            if not usable(t):
                dropped["malformed"] += 1
                continue
            k = key_of(t)
            # Overlap with the benchmark is fatal; this is the whole point.
            if (k in bench_keys
                    or k[0] in bench_instr
                    or k[1] in bench_sheets):
                dropped["overlaps_benchmark"] += 1
                continue
            if k in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(k)
            t["id"] = f"fresh-{len(kept) + 1:04d}"
            t["note"] = f"teacher_generated:{args.model}; domain:{domain}"
            kept.append(t)
            added += 1
        print(f"  batch {batches:>2} ({domain[:30]:<30}) +{added:>2}  total {len(kept)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for t in kept:
            fh.write(json.dumps(t, sort_keys=True) + "\n")

    from collections import Counter
    probes = Counter(t["probe"] for t in kept)
    print(f"\nwrote {len(kept)} tasks to {out}")
    print("  probe balance:", dict(sorted(probes.items())))
    print("  dropped:", dropped)
    print(f"  batches used: {batches}")
    if dropped["overlaps_benchmark"]:
        print(f"\n  NOTE: {dropped['overlaps_benchmark']} generated tasks overlapped "
              "the benchmark and were discarded. That is the check working.")


if __name__ == "__main__":
    main()
