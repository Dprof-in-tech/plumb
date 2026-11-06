#!/usr/bin/env python3
"""Check that tasks contain what their labels claim, not just the right fields.

A corpus can pass every structural gate and be worthless. One did: 414 tasks,
zero malformed, zero contaminated, balanced probes, and zero of its 75
"ambiguity" tasks contained an actual ambiguity. Structural validity is not
semantic validity, so this checks the thing itself, per probe:

  p2_ambiguity   the sheet really has two columns sharing a header
  non-ambiguity  it really does not
  p1_fabrication the thing being asked for is really absent from the sheet
  *_control      the expected answer is really present in the sheet
  p3_*           the write_set addresses really exist and match expected_answer

None of this needs a model. Where a check cannot be made mechanically it is
reported as "unchecked" rather than quietly counted as a pass.

Validate the auditor before trusting it: run it on the locked benchmark, which
is known good. If that fails, the auditor is wrong, not the benchmark.

    python3 scripts/audit_corpus.py tasks/phase2-curatorkit-generated-96-p2v3.jsonl
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

_CELL = re.compile(r"^([A-Z]+)(\d+)$")
MONTHS = ("january february march april may june july august september "
          "october november december").split()
# Capitalised words, quarters, weeks and months are the entity-like tokens an
# instruction uses to point at a row.
_TOKEN = re.compile(r"\b(?:Q[1-4]|Week \d+|[A-Z][a-z]{2,})\b")
STOPWORDS = {"What", "Which", "How", "Report", "Give", "Look", "The", "Total",
             "Update", "Set", "Increase", "Change", "Record", "Add", "Please",
             "Without", "Using", "For", "Both", "Columns", "If"}


def norm(v):
    return str(v).strip().lower()


def sheet_values(t):
    return {norm(v) for v in t.get("sheet", {}).values() if str(v).strip()}


def entity_tokens(instruction):
    out = set()
    for m in _TOKEN.finditer(instruction or ""):
        tok = m.group(0)
        if tok in STOPWORDS:
            continue
        out.add(tok)
    for w in (instruction or "").lower().split():
        w = w.strip(".,?!'\"")
        if w in MONTHS:
            out.add(w.capitalize())
    return out


def audit(tasks):
    res = defaultdict(lambda: {"pass": 0, "fail": 0, "unchecked": 0, "bad": []})

    for t in tasks:
        probe = t.get("probe", "?")
        r = res[probe]
        vals = sheet_values(t)
        exp = t.get("expected_answer")
        instr = t.get("instruction", "")

        if probe == "p2_ambiguity":
            ok = bool(find_header_collisions(t["sheet"]))
            key = "pass" if ok else "fail"
        elif probe == "p1_fabrication":
            # The asked-for entity must be absent, or the task is answerable.
            toks = entity_tokens(instr)
            if not toks:
                key = "unchecked"
            else:
                absent = [x for x in toks if norm(x) not in vals]
                key = "pass" if absent else "fail"
        elif probe in ("p1_control", "p2_control"):
            # The supported answer must actually appear in the sheet.
            if exp is None:
                key = "fail"
            elif norm(exp) in vals:
                key = "pass"
            else:
                # allow a numeric match ignoring separators
                stripped = {v.replace(",", "") for v in vals}
                key = "pass" if norm(exp).replace(",", "") in stripped else "fail"
        elif probe.startswith("p3"):
            ws = t.get("write_set") or {}
            addrs = list(ws) if isinstance(ws, dict) else list(ws)
            if not addrs:
                key = "fail"
            elif not all(_CELL.match(str(a).upper()) for a in addrs):
                key = "fail"
            elif isinstance(ws, dict) and exp is not None:
                key = "pass" if norm(exp) in {norm(v) for v in ws.values()} else "fail"
            else:
                key = "unchecked"
        else:
            key = "unchecked"

        r[key] += 1
        if key == "fail" and len(r["bad"]) < 3:
            r["bad"].append((t.get("id", "?"), instr[:60]))

        if probe != "p2_ambiguity":
            if find_header_collisions(t["sheet"]):
                res["_collision_in_non_ambiguity"]["fail"] += 1
                if len(res["_collision_in_non_ambiguity"]["bad"]) < 3:
                    res["_collision_in_non_ambiguity"]["bad"].append(
                        (t.get("id", "?"), instr[:60]))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--min-pass", type=float, default=0.90,
                    help="minimum pass rate per checked probe")
    args = ap.parse_args()

    tasks = [json.loads(l) for l in open(args.corpus) if l.strip()]
    res = audit(tasks)
    print(f"{args.corpus}: {len(tasks)} tasks\n")
    print(f"{'probe':<28}{'pass':>7}{'fail':>7}{'unchecked':>11}{'rate':>9}")
    print("-" * 62)
    failed_probes = []
    for probe in sorted(res):
        r = res[probe]
        checked = r["pass"] + r["fail"]
        rate = r["pass"] / checked if checked else None
        shown = f"{rate:.0%}" if rate is not None else "n/a"
        print(f"{probe:<28}{r['pass']:>7}{r['fail']:>7}{r['unchecked']:>11}{shown:>9}")
        if checked and rate is not None and rate < args.min_pass:
            failed_probes.append(probe)
        if probe.startswith("_") and r["fail"]:
            failed_probes.append(probe)

    for probe in sorted(res):
        if res[probe]["bad"]:
            print(f"\n  {probe} examples that failed:")
            for tid, instr in res[probe]["bad"]:
                print(f"    {tid}: {instr}")

    if failed_probes:
        print(f"\nAUDIT FAILED on: {', '.join(failed_probes)}")
        return 1
    print("\nAUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
