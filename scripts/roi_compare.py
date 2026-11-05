#!/usr/bin/env python3
"""Self-hosting vs per-token billing for a spreadsheet agent.

Consumes a measurement file from scripts/roi_measure.py and prints the monthly
cost both ways across a range of volumes, plus the break-even point.

Self-hosting cost is wall-clock GPU time at a stated hourly rate, derived from
the measured throughput of this project's own runs. Per-token cost uses the
measured prompt/completion token counts from the same runs, so both sides are
priced on identical traffic.

Usage:
    python3 scripts/roi_compare.py --measure runs/roi-measure-base.json
"""

import argparse
import json

# Hosted per-token rates, USD per million tokens.
# Source: Anthropic list pricing, checked Nov 2026.
HOSTED = {
    "Claude Haiku 4.5": (1.00, 5.00),
    "Claude Sonnet 5": (2.00, 10.00),
}

# AWS g5.xlarge (1x A10G, 4 vCPU, 16 GiB), on-demand, us-east-1.
# Source: AWS EC2 on-demand list price, checked Nov 2026.
GPU_HOURLY_DEFAULT = 1.006

VOLUMES = [1_000, 10_000, 100_000, 1_000_000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", required=True, help="output of roi_measure.py")
    ap.add_argument("--gpu-hourly", type=float, default=GPU_HOURLY_DEFAULT)
    ap.add_argument("--utilisation", type=float, default=1.0,
                    help="fraction of the paid hour actually serving requests")
    args = ap.parse_args()

    m = json.load(open(args.measure))
    p_in = m["prompt_tokens_mean"]
    p_out = m["completion_tokens_mean"]
    tps = m["total_tokens_per_s"]
    sec_per_task = (p_in + p_out) / tps

    print(f"measured on {m['tasks_ok']} tasks, model {m['model']}")
    print(f"  mean prompt tokens     : {p_in}")
    print(f"  mean completion tokens : {p_out}")
    print(f"  throughput             : {tps} tok/s total, "
          f"{m['decode_tokens_per_s']} tok/s decode")
    print(f"  => {sec_per_task:.2f} s of GPU per task")
    print(f"  => {3600 / sec_per_task:.0f} tasks per GPU-hour at 100% utilisation")
    print()
    print(f"self-host rate: ${args.gpu_hourly}/h (A10G on-demand), "
          f"utilisation {args.utilisation:.0%}")
    print()

    cols = ["volume/mo", "self-host"] + list(HOSTED)
    print("".join(c.rjust(20) for c in cols))
    print("-" * (20 * len(cols)))
    for v in VOLUMES:
        gpu_hours = v * sec_per_task / 3600 / args.utilisation
        self_host = gpu_hours * args.gpu_hourly
        row = [f"{v:,}", f"${self_host:,.2f}"]
        for name, (ri, ro) in HOSTED.items():
            cost = v * (p_in * ri + p_out * ro) / 1e6
            row.append(f"${cost:,.2f}")
        print("".join(c.rjust(20) for c in row))

    print()
    for name, (ri, ro) in HOSTED.items():
        per_task_hosted = (p_in * ri + p_out * ro) / 1e6
        per_task_self = sec_per_task / 3600 * args.gpu_hourly / args.utilisation
        print(f"{name}: ${per_task_hosted * 1000:.3f} per 1k tasks "
              f"vs ${per_task_self * 1000:.3f} self-hosted "
              f"({per_task_hosted / per_task_self:.1f}x)")
    print()
    print("Break-even against a dedicated instance billed 24/7 "
          f"(${args.gpu_hourly * 24 * 30:,.0f}/mo):")
    for name, (ri, ro) in HOSTED.items():
        per_task_hosted = (p_in * ri + p_out * ro) / 1e6
        tasks = args.gpu_hourly * 24 * 30 / per_task_hosted
        print(f"  vs {name}: {tasks:,.0f} tasks/mo "
              f"({tasks / 30 / 24:,.0f} per hour sustained)")


if __name__ == "__main__":
    main()
