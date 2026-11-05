"""Run PLUMB against a model and print the metrics.

    python scripts/run.py --model stub          # harness self-test, no GPU
    python scripts/run.py --model refuser       # proves the guards bite
    python scripts/run.py --model api  --api-id tiny-aya-global   # Ollama etc.
    python scripts/run.py --model hf   --hf-id CohereLabs/tiny-aya-global

The stub backends exist so the scoring loop can be verified without a model.
Every backend is just str -> str, so adding one is a few lines in get_backend().
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plumb.score import aggregate, judge, report  # noqa: E402
from plumb.tasks import Response, load_tasks  # noqa: E402


def stub_backend(prompt: str) -> str:
    """A deliberately ungrounded model: always answers, always over-writes.

    This is the worst case, and running it should light up every headline
    metric. If it does not, the harness is wrong.
    """
    return json.dumps(
        {"status": "answered", "answer": "42", "edits": {"A1": "clobbered"}}
    )


def refuser_backend(prompt: str) -> str:
    """The lobotomy: declines everything. Should score 0 on the headline
    metrics and get caught by over_refusal_rate and completion_rate."""
    return json.dumps({"status": "declined", "reason": "not sure", "edits": {}})


def api_backend(model_id: str, base_url: str, api_key: str, max_tokens: int = 400):
    """Any OpenAI-compatible chat endpoint: Ollama, llama.cpp server, vLLM.

    This is the cheap path for the first capability check. A 3.35B model in
    GGUF runs on a laptop, so you can find out whether it holds the output
    contract without spending a minute of GPU credit on the question.
    """
    import urllib.request  # noqa: PLC0415

    url = base_url.rstrip("/") + "/chat/completions"

    def call(prompt: str) -> str:
        body = json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_tokens,
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key or 'none'}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                payload = json.loads(r.read())
            return payload["choices"][0]["message"]["content"]
        except Exception as exc:  # a dead call is a result, not a crash
            return f"__BACKEND_ERROR__ {exc}"

    return call


def hf_backend(hf_id: str, max_new_tokens: int = 400):
    """Local transformers backend. Only imported when actually used."""
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    tok = AutoTokenizer.from_pretrained(hf_id)
    model = AutoModelForCausalLM.from_pretrained(hf_id, device_map="auto")

    def call(prompt: str) -> str:
        msgs = [{"role": "user", "content": prompt}]
        ids = tok.apply_chat_template(
            msgs, add_generation_prompt=True, return_tensors="pt"
        ).to(model.device)
        out = model.generate(ids, max_new_tokens=max_new_tokens, do_sample=False)
        return tok.decode(out[0][ids.shape[-1] :], skip_special_tokens=True)

    return call


def get_backend(args):
    if args.model == "stub":
        return stub_backend
    if args.model == "refuser":
        return refuser_backend
    if args.model == "api":
        if not args.api_id:
            sys.exit("--api-id is required with --model api")
        return api_backend(args.api_id, args.base_url, args.api_key, args.max_tokens)
    if args.model == "hf":
        if not args.hf_id:
            sys.exit("--hf-id is required with --model hf")
        return hf_backend(args.hf_id, args.max_tokens)
    sys.exit(f"unknown backend: {args.model}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="tasks/seed.jsonl")
    ap.add_argument("--model", default="stub")
    ap.add_argument("--hf-id", default=None, help="HF repo id, e.g. CohereLabs/tiny-aya-global")
    ap.add_argument("--api-id", default=None, help="model name at an OpenAI-compatible endpoint")
    ap.add_argument("--base-url", default=os.environ.get("PLUMB_BASE_URL", "http://localhost:11434/v1"))
    ap.add_argument("--api-key", default=os.environ.get("PLUMB_API_KEY", ""))
    ap.add_argument("--out", default=None, help="write per-task results as JSONL")
    ap.add_argument("--label", default=None, help="run label for the metrics file")
    ap.add_argument(
        "--max-tokens",
        type=int,
        default=400,
        help=(
            "generation cap. 400 suits Tiny Aya, whose replies are ~25 tokens. "
            "Reasoning models need far more: a truncated reply is scored as a "
            "parse failure, which silently charges a serving limit against the "
            "content metrics."
        ),
    )
    args = ap.parse_args()

    tasks = load_tasks(args.tasks)
    call = get_backend(args)

    outcomes, rows = [], []
    for t in tasks:
        raw = call(t.prompt())
        resp = Response.parse(raw)
        o = judge(t, resp)
        outcomes.append(o)
        rows.append(
            {
                "task_id": o.task_id,
                "probe": o.probe,
                "status": o.status,
                "parse_ok": o.parse_ok,
                "format_strict": o.format_strict,
                "fabricated": o.fabricated,
                "silent_guess": o.silent_guess,
                "collateral": o.collateral,
                "stray_cells": o.stray_cells,
                "over_refused": o.over_refused,
                "completed": o.completed,
                "raw": resp.raw,
            }
        )

    metrics = aggregate(outcomes)
    metrics["label"] = args.label or args.model
    print(report(metrics))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        mpath = args.out.rsplit(".", 1)[0] + ".metrics.json"
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)
        print(f"\nper-task: {args.out}\nmetrics:  {mpath}")


if __name__ == "__main__":
    main()