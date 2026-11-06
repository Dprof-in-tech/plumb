#!/usr/bin/env python3
"""Tests for plumb.ambiguity, scored against the benchmark itself.

The detector's claim is that it catches the collisions a 3.35B model cannot
see. The benchmark already labels which tasks contain one, so the honest test
is not a handful of fixtures: run it over all 96 tasks of both P2 variants and
require perfect recall on p2_ambiguity and zero false positives everywhere
else. Fixtures then cover the edge cases the task set does not contain.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb.ambiguity import Collision, announce, describe, find_header_collisions

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def against_benchmark(path, label):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    tp = fp = fn = tn = 0
    misses, falses = [], []
    for r in rows:
        found = bool(find_header_collisions(r["sheet"]))
        should = r["probe"] == "p2_ambiguity"
        if should and found:
            tp += 1
        elif should and not found:
            fn += 1; misses.append(r["id"])
        elif not should and found:
            fp += 1; falses.append(r["id"])
        else:
            tn += 1
    n_amb = tp + fn
    check(f"{label}: recall on p2_ambiguity", fn == 0,
          f"{tp}/{n_amb}" + (f", missed {misses[:3]}" if misses else ""))
    check(f"{label}: no false positives on the other {tn + fp} tasks", fp == 0,
          f"{fp} false" + (f", e.g. {falses[:3]}" if falses else ""))


print("=== against the locked benchmark ===")
against_benchmark("tasks/phase2-curatorkit-generated-96-p2v3.jsonl", "p2v3 announced")
against_benchmark("tasks/phase2-curatorkit-generated-96-p2v4.jsonl", "p2v4 unannounced")

print("\n=== edge cases the task set does not contain ===")
check("empty sheet", find_header_collisions({}) == [])
check("no collision", find_header_collisions({"A1": "Month", "B1": "Sales"}) == [])
check("exact duplicate",
      len(find_header_collisions({"A1": "Revenue", "B1": "Revenue"})) == 1)
check("case-insensitive",
      len(find_header_collisions({"A1": "Revenue", "B1": "revenue"})) == 1)
check("whitespace and underscores folded",
      len(find_header_collisions({"A1": "net  revenue", "B1": "Net_Revenue"})) == 1)
check("trailing punctuation folded",
      len(find_header_collisions({"A1": "Revenue:", "B1": "Revenue"})) == 1)
check("blank headers ignored",
      find_header_collisions({"A1": "", "B1": "   "}) == [])
check("data rows ignored",
      find_header_collisions({"A1": "Month", "B1": "Sales",
                              "A2": "Same", "B2": "Same"}) == [])
check("three-way collision reports all columns",
      find_header_collisions({"A1": "X", "B1": "X", "C1": "X"})[0].columns == ["A", "B", "C"])
check("multi-letter columns handled",
      find_header_collisions({"AA1": "X", "AB1": "X"})[0].columns == ["AA", "AB"])
check("non-default header row",
      len(find_header_collisions({"A3": "X", "B3": "X"}, header_row=3)) == 1)
check("malformed addresses skipped",
      find_header_collisions({"total": "X", "B1": "Y", "": "Z"}) == [])
check("plural is NOT folded (conservative)",
      find_header_collisions({"A1": "Revenue", "B1": "Revenues"}) == [])
check("near-duplicates excluded when switched off",
      find_header_collisions({"A1": "Revenue", "B1": "revenue"},
                             include_near_duplicates=False) == [])
check("exact duplicates still found when switched off",
      len(find_header_collisions({"A1": "Revenue", "B1": "Revenue"},
                                 include_near_duplicates=False)) == 1)

c = find_header_collisions({"A1": "Revenue", "B1": "Revenue"})[0]
check("exact flag true for identical text", c.exact is True)
c2 = find_header_collisions({"A1": "Revenue", "B1": "revenue"})[0]
check("exact flag false for folded match", c2.exact is False)

print("\n=== announcement wording ===")
msg = announce(find_header_collisions({"A1": "Month", "B1": "Revenue", "C1": "Revenue"}))
check("names both columns", "B and C" in msg, msg[:60])
check("names the header", "'Revenue'" in msg)
check("says the request does not specify", "does not specify" in msg)
check("tells the model to ask", "ask for clarification" in msg)
check("empty for a clean sheet", announce([]) == "")
check("describe() is one line",
      describe({"A1": "Revenue", "B1": "Revenue"}).startswith("1 header collision"))
check("describe() clean case", describe({"A1": "Month"}) == "no header collisions")

print(f"\n{'ALL PASS' if not FAILED else str(len(FAILED)) + ' FAILED: ' + ', '.join(FAILED)}")
sys.exit(1 if FAILED else 0)
