#!/usr/bin/env python3
"""Cross-check PLUMB's abstention measurement against AuditKIT's, independently.

Why this is worth doing
-----------------------
PLUMB decides whether a model abstained by reading the `status` field of the
JSON it returned. That is a design decision, not an obvious truth, and it has
never been checked against anything outside this repository.

AuditKIT's `Abstention` metric asks the same question -- "did the system abstain
on unanswerable cases, and answer the answerable ones?" -- and answers it by a
completely different mechanism: a keyword detector over the reply text, reading
the first sentence for refusal markers and openers. Two independent
implementations, one question.

Agreement would be external corroboration of PLUMB's numbers. Disagreement is
also a result, and a more useful one: it would show how a text-based refusal
detector behaves on agents that reply in structured JSON, which is most agents
now. Either way this is a control written by someone else, which is the kind
this project has learned to trust most.

Usage:
    python3 scripts/auditkit_crosscheck.py runs/sweep-global-1.jsonl \
        --tasks tasks/phase2-curatorkit-generated-96-p2v3.jsonl
"""

import argparse
import json
from collections import Counter

from auditkit import Abstention, Sample


def load_tasks(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                t = json.loads(line)
                out[t["id"]] = t
    return out


def expected_action(task):
    """PLUMB's ground truth, expressed in AuditKIT's vocabulary.

    An ambiguous task is unanswerable as posed: there is no single supported
    answer, so committing to one is the failure. Both map to "abstain".
    """
    if task.get("ambiguous") or not task.get("answerable", True):
        return "abstain"
    return "answer"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--tasks", default="tasks/phase2-curatorkit-generated-96-p2v3.jsonl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--show", type=int, default=6, help="disagreements to print")
    ap.add_argument("--mode", choices=["keyword", "explicit"], default="keyword",
                    help="keyword: AuditKIT's text fallback detects abstention. "
                         "explicit: PLUMB's status field is supplied as the signal.")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks)
    rows = [json.loads(l) for l in open(args.run) if l.strip()]
    metric = Abstention()

    agree, disagree, untested = 0, 0, 0
    examples, cells = [], Counter()

    for r in rows:
        t = tasks.get(r["task_id"])
        if t is None:
            continue
        action = expected_action(t)
        raw = r.get("raw") or ""

        # PLUMB's own view, read off the status field.
        plumb_abstained = r["status"] in ("declined", "needs_clarification")

        case = {
            "case_id": r["task_id"],
            "question": t["instruction"],
            "answerability": "unanswerable" if action == "abstain" else "answerable",
            "expected_action": action,
        }
        if args.mode == "explicit":
            # Wire PLUMB's status field in as the explicit abstention signal,
            # which is the path AuditKIT prefers; the keyword detector is its
            # documented fallback for when no such signal exists.
            sample = Sample(input=t["instruction"], id=r["task_id"],
                            metadata={"rag_case": case},
                            actual_trace={"abstained": plumb_abstained})
        else:
            sample = Sample(input=t["instruction"], id=r["task_id"],
                            metadata={"rag_case": case})
        sc = metric.score(sample, raw)[0]
        ak_abstained = (sc.metadata or {}).get("abstained")
        detection = (sc.metadata or {}).get("detection")

        if ak_abstained is None:
            untested += 1
            continue
        cells[(plumb_abstained, bool(ak_abstained))] += 1
        if bool(ak_abstained) == plumb_abstained:
            agree += 1
        else:
            disagree += 1
            if len(examples) < args.show:
                examples.append((r["task_id"], r["status"], plumb_abstained,
                                 bool(ak_abstained), raw.strip()[:150]))

    total = agree + disagree
    print(f"run: {args.run}   mode: {args.mode}")
    print(f"scored by both: {total}   not testable by AuditKIT: {untested}\n")
    print("agreement on 'did it abstain?'")
    print(f"  {'':<22}{'AuditKIT: abstained':>22}{'AuditKIT: answered':>21}")
    for p in (True, False):
        lab = "PLUMB: abstained" if p else "PLUMB: answered"
        print(f"  {lab:<22}{cells[(p, True)]:>22}{cells[(p, False)]:>21}")
    pct = 100 * agree / total if total else 0
    print(f"\n  agree {agree}/{total} ({pct:.1f}%)   disagree {disagree}")

    if examples:
        print("\ndisagreements:")
        for tid, status, p, a, raw in examples:
            print(f"  {tid}  PLUMB status={status} (abstained={p})  AuditKIT abstained={a}")
            print(f"     {raw!r}")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({
                "run": args.run, "mode": args.mode, "scored_by_both": total, "not_testable": untested,
                "agree": agree, "disagree": disagree,
                "agreement_rate": round(pct, 1),
                "matrix": {f"plumb_{'abstained' if p else 'answered'}__"
                           f"auditkit_{'abstained' if a else 'answered'}": n
                           for (p, a), n in cells.items()},
            }, fh, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
