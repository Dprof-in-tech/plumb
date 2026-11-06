#!/usr/bin/env python3
"""Normalise and filter a generated corpus so it is safe to train on.

Written after training on an unaudited corpus produced a model that answered
every question, including the unanswerable ones. Two defects caused it, and
neither was visible to the structural gates:

1. `write_set` came back as [{"cell": "B2", "value": "110"}] where the schema
   is {"B2": "110"}. `build_sft_data` only reads a dict, so all 108 write tasks
   trained the model to answer with no edits at all.
2. Tasks labelled unanswerable were computable: "What was the revenue for
   January if the average unit price was $25 and units sold were 120?" is a
   multiplication, not a missing value. Training "decline this" on a question
   with a derivable answer teaches incoherence.

So: normalise what can be normalised, drop what cannot be verified, and re-audit.
A smaller corpus that means what it says beats a larger one that does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_corpus import audit  # noqa: E402

# Phrases that make a task computable from the prompt itself, so "declined" is
# the wrong target even when the sheet lacks the figure.
HYPOTHETICAL = (" if ", "assuming", "given that", "suppose", "were to be",
                "what would", "if the", "at a rate of")


def normalise_write_set(ws):
    """Accept the shapes a generator produces; emit the schema's shape."""
    if isinstance(ws, dict):
        return {str(k).strip().upper(): v for k, v in ws.items()}
    if isinstance(ws, list):
        out = {}
        for item in ws:
            if isinstance(item, dict):
                cell = item.get("cell") or item.get("address") or item.get("ref")
                if cell is None:
                    return None
                out[str(cell).strip().upper()] = item.get("value", "")
            elif isinstance(item, str):
                out[item.strip().upper()] = ""
            else:
                return None
        return out
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tasks = [json.loads(l) for l in open(args.source) if l.strip()]
    kept, dropped = [], Counter()

    for t in tasks:
        probe = t.get("probe", "")

        if probe.startswith("p3"):
            ws = normalise_write_set(t.get("write_set"))
            if not ws:
                dropped["p3 write_set unusable"] += 1
                continue
            t["write_set"] = ws
            # the expected answer should be the value actually requested
            if t.get("expected_answer") is None:
                vals = [v for v in ws.values() if str(v).strip()]
                if len(vals) != 1:
                    dropped["p3 ambiguous expected answer"] += 1
                    continue
                t["expected_answer"] = str(vals[0])
        else:
            t["write_set"] = []

        if probe == "p1_fabrication":
            low = (t.get("instruction") or "").lower()
            if any(h in low for h in HYPOTHETICAL):
                dropped["p1_fabrication is computable from the prompt"] += 1
                continue

        kept.append(t)

    # Drop whatever still fails the semantic audit.
    res = audit(kept)
    bad_ids = set()
    for probe, r in res.items():
        if probe.startswith("_"):
            continue
    # re-run per task to identify failures precisely
    final = []
    for t in kept:
        one = audit([t])
        probe = t.get("probe", "")
        r = one.get(probe, {})
        if r.get("fail"):
            dropped[f"{probe} failed the audit"] += 1
            continue
        if one.get("_collision_in_non_ambiguity", {}).get("fail"):
            dropped["collision in a non-ambiguity task"] += 1
            continue
        final.append(t)

    with open(args.out, "w", encoding="utf-8") as fh:
        for t in final:
            fh.write(json.dumps(t, sort_keys=True) + "\n")

    print(f"in: {len(tasks)}  out: {len(final)}  dropped: {sum(dropped.values())}")
    for k, v in dropped.most_common():
        print(f"   {v:>4}  {k}")
    print("\nprobe balance:", dict(sorted(Counter(t['probe'] for t in final).items())))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
