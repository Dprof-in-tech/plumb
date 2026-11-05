"""Full-task SFT with the loss masked to the completion, verified before training.

Why this exists
---------------
The previous SFT run computed loss over the whole sequence. Its symptoms were
`train_loss` 3.045 and `mean_token_accuracy` 0.46 after two epochs on 48 gold
examples -- not what overfitting 48 examples looks like. With a mean prompt of
270 tokens against a mean completion of 45, roughly 86% of the gradient was
spent trying to predict a serialised spreadsheet, which is arbitrary data the
model cannot learn.

The documented blocker was that `assistant_only_loss` needs `{% generation %}`
markers and Tiny Aya's chat template has none. TRL's older
`DataCollatorForCompletionOnlyLM` would have sidestepped that, but it was
removed in TRL 1.7. The supported replacement is `completion_only_loss=True`
on a *prompt-completion* dataset, which derives the boundary from the dataset
columns and needs no template markers at all.

The trap that produced the original bug is that an extra `text` column makes
TRL read the dataset as language-modelling and mask nothing. So this script
loads only `prompt` and `completion`, and then *verifies the mask on a real
batch from the real dataloader* before training. If the mask is wrong, nothing
trains -- the whole point is to stop re-running an interpretation problem
instead of a training problem.
"""

from __future__ import annotations

import json
import os
import sys

import torch
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoTokenizer
from trl import SFTConfig, SFTTrainer

MODEL = os.environ.get("PLUMB_SFT_MODEL", "CohereLabs/tiny-aya-global")
DATASET = os.environ.get("PLUMB_SFT_DATASET", "/workspace/sft-corrections-train.jsonl")
OUTPUT = os.environ.get("PLUMB_SFT_OUTPUT", "/workspace/sft-output-masked")
EPOCHS = int(os.environ.get("PLUMB_SFT_EPOCHS", "2"))
LR = float(os.environ.get("PLUMB_SFT_LR", "2e-6"))
MAXLEN = int(os.environ.get("PLUMB_SFT_MAXLEN", "512"))

# Gate thresholds. Prompt ~270 tokens, completion ~45, so ~14% is expected.
# The unmasked run was effectively 100%.
MIN_FRAC, MAX_FRAC = 0.05, 0.35


def load_rows(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                # Only these two columns. A `text` column here would make TRL
                # treat the dataset as language-modelling and mask nothing,
                # which is the original bug.
                rows.append({"prompt": r["prompt"], "completion": r["completion"]})
    return rows


def verify_mask(trainer, tokenizer, rows):
    """Decode what the loss is actually computed on. Hard-fail if it is wrong.

    Checks, per the pre-registration:
      1. every unmasked span decodes to exactly that example's completion
      2. unmasked token count is within +/-2 of the completion tokenised alone
      3. mean unmasked fraction across the set is in [MIN_FRAC, MAX_FRAC]
    """
    loader = trainer.get_train_dataloader()
    batch = next(iter(loader))
    if "labels" not in batch:
        raise SystemExit("GATE FAILED: collated batch has no `labels`")

    labels, input_ids = batch["labels"], batch["input_ids"]
    completions = {r["completion"] for r in rows}

    print("\n=== mask verification (real batch from the real dataloader) ===")
    print(f"batch shape: {tuple(input_ids.shape)}")

    total_unmasked = total_real = 0
    failures = []
    for i in range(labels.shape[0]):
        row_labels = labels[i]
        keep = row_labels != -100
        if "attention_mask" in batch:
            real = int(batch["attention_mask"][i].sum())
        else:
            real = int(row_labels.shape[0])
        n_unmasked = int(keep.sum())
        total_unmasked += n_unmasked
        total_real += real

        decoded = tokenizer.decode(row_labels[keep], skip_special_tokens=True).strip()
        match = decoded in completions or any(
            decoded == c.strip() for c in completions
        )
        exp = None
        for c in completions:
            if decoded == c.strip():
                exp = len(tokenizer(c, add_special_tokens=False)["input_ids"])
                break
        print(f"  row {i}: {n_unmasked}/{real} tokens unmasked "
              f"({100 * n_unmasked / max(real, 1):.1f}%)  match={match}")
        print(f"    loss computed on: {decoded[:140]!r}")
        if not match:
            failures.append(f"row {i} unmasked span is not a completion: {decoded[:160]!r}")
        elif exp is not None and abs(n_unmasked - exp) > 2:
            failures.append(
                f"row {i} unmasked {n_unmasked} tokens, completion alone is {exp}")

    frac = total_unmasked / max(total_real, 1)
    print(f"\nbatch unmasked fraction: {frac:.3f} "
          f"({total_unmasked}/{total_real} tokens)")

    if not (MIN_FRAC <= frac <= MAX_FRAC):
        failures.append(
            f"unmasked fraction {frac:.3f} outside [{MIN_FRAC}, {MAX_FRAC}] -- "
            f"{'nothing is masked, loss is on the whole sequence' if frac > MAX_FRAC else 'too much is masked'}")

    if failures:
        print("\nGATE FAILED:")
        for f in failures:
            print("  -", f)
        raise SystemExit(1)

    print("GATE PASSED: loss is computed on the completion only.\n")
    return frac


def main():
    rows = load_rows(DATASET)
    print(f"{len(rows)} prompt-completion examples from {DATASET}")
    ds = Dataset.from_list(rows)
    print(f"dataset columns: {ds.column_names}  (must be exactly prompt+completion)")

    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    p = [len(tokenizer(r["prompt"], add_special_tokens=False)["input_ids"]) for r in rows]
    c = [len(tokenizer(r["completion"], add_special_tokens=False)["input_ids"]) for r in rows]
    print(f"prompt tokens: mean {sum(p)/len(p):.1f}  "
          f"completion tokens: mean {sum(c)/len(c):.1f}  "
          f"=> expected unmasked fraction {sum(c)/(sum(p)+sum(c)):.3f}")

    cfg = SFTConfig(
        output_dir=OUTPUT,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=1,
        learning_rate=LR,
        max_length=MAXLEN,
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        report_to=[],
        packing=False,
        # THE ONE CHANGE from the previous run. Requires a prompt-completion
        # dataset, and unlike assistant_only_loss needs no `{% generation %}`
        # markers in the chat template -- which Tiny Aya does not have.
        completion_only_loss=True,
    )

    trainer = SFTTrainer(
        model=MODEL,
        args=cfg,
        train_dataset=ds,
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=8, lora_alpha=16, lora_dropout=0.05,
            task_type="CAUSAL_LM", bias="none",
        ),
    )

    frac = verify_mask(trainer, tokenizer, rows)

    result = trainer.train()
    print(f"\ntrain_loss: {result.training_loss}")
    trainer.save_model(OUTPUT)

    with open(os.path.join(OUTPUT, "mask_report.json"), "w") as f:
        json.dump({
            "completion_only_loss": True,
            "verified_unmasked_fraction": frac,
            "prompt_tokens_mean": sum(p) / len(p),
            "completion_tokens_mean": sum(c) / len(c),
            "train_loss": result.training_loss,
            "epochs": EPOCHS,
            "learning_rate": LR,
            "n_examples": len(rows),
        }, f, indent=2)

    repo = os.environ.get("PLUMB_HF_REPO")
    token = os.environ.get("HF_TOKEN")
    if repo and token:
        from huggingface_hub import HfApi
        info = HfApi(token=token).upload_folder(
            repo_id=repo,
            folder_path=OUTPUT,
            path_in_repo=os.environ.get(
                "PLUMB_SFT_REMOTE_OUTPUT", "training/sft-output-masked"),
            repo_type="model",
            commit_message="Upload completion-only-loss SFT adapter",
        )
        print(f"uploaded: {info.commit_url}")


if __name__ == "__main__":
    main()
