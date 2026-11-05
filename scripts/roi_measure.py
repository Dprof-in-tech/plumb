#!/usr/bin/env python3
"""Measure real token counts and throughput for the ROI comparison.

Runs the locked task set through an OpenAI-compatible endpoint and records the
prompt/completion token usage the server reports, plus wall-clock latency per
task. Writes a JSON summary used by the README's ROI section.

Usage:
    python3 scripts/roi_measure.py --api-id plumb-base-eosfix \
        --tasks tasks/phase2-curatorkit-generated-96-p2v3.jsonl \
        --out runs/roi-measure-base.json
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request

sys.path.insert(0, ".")
from plumb.tasks import Task  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-id", required=True)
    ap.add_argument("--tasks", default="tasks/phase2-curatorkit-generated-96-p2v3.jsonl")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--limit", type=int, default=None, help="measure only the first N tasks")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.tasks) if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    tasks = [Task.from_dict(r) for r in rows]

    records = []
    for t in tasks:
        body = json.dumps({
            "model": args.api_id,
            "messages": [{"role": "user", "content": t.prompt()}],
            "temperature": 0,
            "max_tokens": args.max_tokens,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{args.base_url}/chat/completions",
            data=body, headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
        except Exception as exc:  # a failed task still costs wall-clock time
            records.append({"task_id": t.id, "error": str(exc),
                            "latency_s": time.perf_counter() - t0})
            continue
        dt = time.perf_counter() - t0
        u = d.get("usage") or {}
        records.append({
            "task_id": t.id,
            "prompt_tokens": u.get("prompt_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            "total_tokens": u.get("total_tokens"),
            "latency_s": dt,
            "finish_reason": d["choices"][0].get("finish_reason"),
        })

    ok = [r for r in records if "error" not in r and r.get("completion_tokens") is not None]
    prompt_tokens = sum(r["prompt_tokens"] for r in ok)
    completion_tokens = sum(r["completion_tokens"] for r in ok)
    wall = sum(r["latency_s"] for r in records)
    gen_time = sum(r["latency_s"] for r in ok)

    summary = {
        "model": args.api_id,
        "tasks_measured": len(records),
        "tasks_ok": len(ok),
        "prompt_tokens_total": prompt_tokens,
        "completion_tokens_total": completion_tokens,
        "prompt_tokens_mean": round(prompt_tokens / len(ok), 1) if ok else None,
        "completion_tokens_mean": round(completion_tokens / len(ok), 1) if ok else None,
        "completion_tokens_median": statistics.median(
            r["completion_tokens"] for r in ok) if ok else None,
        "wall_clock_s": round(wall, 2),
        "mean_latency_s": round(wall / len(records), 3) if records else None,
        "decode_tokens_per_s": round(completion_tokens / gen_time, 2) if gen_time else None,
        "total_tokens_per_s": round(
            (prompt_tokens + completion_tokens) / gen_time, 2) if gen_time else None,
        "finish_reasons": {
            k: sum(1 for r in ok if r.get("finish_reason") == k)
            for k in {r.get("finish_reason") for r in ok}
        },
        "per_task": records,
    }
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
    for k, v in summary.items():
        if k != "per_task":
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
