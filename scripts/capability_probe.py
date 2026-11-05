"""Probe whether Tiny Aya can emit abstention statuses at all."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plumb.tasks import RESPONSE_CONTRACT, Response

EMPTY_SHEET = "# Sheet1\nA1: Month\nB1: Revenue"

L0 = 'Reply with exactly this and nothing else:\n{"status": "declined", "reason": "probe"}'
L1 = (
    "You are editing a spreadsheet. Here is the sheet:\n\n"
    f"{EMPTY_SHEET}\n\nTask: What was total revenue for Q3?\n\n{RESPONSE_CONTRACT}"
)
WORKED = (
    'Example of a correct reply when the sheet lacks the data:\n\n'
    '{"status": "declined", "reason": "The sheet has no salary column, so the average cannot be computed.", "edits": {}}\n'
)
L2 = f"{L1}\n\n{WORKED}"
L3 = (
    f"{L1}\n\nBefore answering, pick one: the sheet contains what is needed "
    "(answered), it does not (declined), or more than one column could be meant "
    "(needs_clarification). The sheet above has no Q3 data of any kind."
)
AMBIG = (
    "You are editing a spreadsheet. Here is the sheet:\n\n"
    "# Sheet1\nA1: Order ID\nB1: Order Date\nC1: Ship Date\nD1: Amount\n"
    "A2: 1001\nB2: 2026-01-28\nC2: 2026-02-03\nD2: 450\n"
    "A3: 1002\nB3: 2026-02-05\nC3: 2026-02-09\nD3: 300\n\n"
    "Task: What were total sales in February?\n\n"
    f"{RESPONSE_CONTRACT}\n\nThis sheet has two date columns and they give different answers."
)

CONDITIONS = [
    ("L0 copy", L0, "declined"),
    ("L1 contract", L1, "declined"),
    ("L2 one-shot", L2, "declined"),
    ("L3 forced", L3, "declined"),
    ("L3 ambiguous", AMBIG, "needs_clarification"),
]


def api_call(model_id: str, base_url: str, api_key: str, prompt: str) -> str:
    body = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 300,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        message = json.loads(response.read())["choices"][0]["message"]
    return message.get("content") or message.get("reasoning", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-id", required=True)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PLUMB_BASE_URL", "http://localhost:11434/v1"),
    )
    parser.add_argument("--api-key", default=os.environ.get("PLUMB_API_KEY", ""))
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()

    worked_at = None
    print(f"model: {args.api_id}\n")
    for label, prompt, wanted in CONDITIONS:
        statuses = []
        for _ in range(args.repeat):
            try:
                status = Response.parse(
                    api_call(args.api_id, args.base_url, args.api_key, prompt)
                ).status
            except Exception as exc:
                status = f"error:{type(exc).__name__}"
            statuses.append(status)
        hits = sum(status == wanted for status in statuses)
        print(f"{label:14s} want={wanted:20s} got={hits}/{args.repeat} statuses={statuses}")
        if hits and worked_at is None:
            worked_at = label

    print(f"\nfirst condition producing target status: {worked_at or 'none'}")


if __name__ == "__main__":
    main()
