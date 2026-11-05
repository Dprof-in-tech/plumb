"""Evaluate a Hugging Face PEFT adapter on the PLUMB benchmark."""

from __future__ import annotations

import json
import os
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from plumb.score import aggregate, judge
from plumb.tasks import Response, load_tasks


def main() -> None:
    root = Path("/workspace")
    adapter_subdir = os.environ.get("PLUMB_ADAPTER_SUBDIR", "p1-dpo-output")
    output_name = os.environ.get("PLUMB_EVAL_OUTPUT", "p1-adapter-evaluation")
    tokenizer = AutoTokenizer.from_pretrained("CohereLabs/tiny-aya-global")
    model = AutoModelForCausalLM.from_pretrained(
        "CohereLabs/tiny-aya-global",
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    if adapter_subdir != "base":
        adapter_root = Path(
            snapshot_download(
                "Isaacdnigerian/plumb",
                repo_type="model",
                allow_patterns=[f"training/{adapter_subdir}/*"],
                local_dir=root / "hub",
            )
        ) / "training" / adapter_subdir
        model = PeftModel.from_pretrained(model, adapter_root)
    model.eval()

    tasks = load_tasks(root / "tasks/phase2-curatorkit-generated-96-p2v3.jsonl")
    outcomes = []
    rows = []
    for task in tasks:
        messages = [{"role": "user", "content": task.prompt()}]
        inputs = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        ).to(model.device)
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=400,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        raw = tokenizer.decode(
            generated[0, inputs["input_ids"].shape[-1] :], skip_special_tokens=True
        )
        response = Response.parse(raw)
        outcome = judge(task, response)
        outcomes.append(outcome)
        rows.append(
            {
                "task_id": outcome.task_id,
                "probe": outcome.probe,
                "status": outcome.status,
                "parse_ok": outcome.parse_ok,
                "format_strict": outcome.format_strict,
                "fabricated": outcome.fabricated,
                "silent_guess": outcome.silent_guess,
                "collateral": outcome.collateral,
                "over_refused": outcome.over_refused,
                "completed": outcome.completed,
                "raw": raw,
            }
        )

    output = root / output_name
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(
        json.dumps(aggregate(outcomes), indent=2) + "\n", encoding="utf-8"
    )
    (output / "per-task.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    print((output / "metrics.json").read_text())


if __name__ == "__main__":
    main()
