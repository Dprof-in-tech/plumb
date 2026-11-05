# Pre-registration: loss-mask SFT retrain

Written **before** the retrain was run or its evaluation seen. Committed ahead
of the run so the analysis cannot be chosen after the fact. Commit history is
the evidence.

- **Date written:** 6 Nov 2026
- **Prior result being revised:** full-task LoRA SFT, trained on the leak-free
  48-task train split, changed **zero decisions** on all 48 held-out tasks and
  all five metrics (`runs/heldout-base-1.jsonl` vs `runs/heldout-sft-1.jsonl`).

## Hypothesis

The previous SFT run computed loss over the whole sequence rather than the
completion only. Evidence: `train_loss` 3.045 and `mean_token_accuracy` 0.46
after two epochs on 48 gold examples. Overfitting 48 examples should drive both
much further; those values are what you get when most of the gradient is spent
predicting a serialised spreadsheet, which is arbitrary data the model cannot
learn. With a mean prompt of 270.4 tokens and a mean completion of 44.5,
roughly 86% of tokens are prompt.

**H1:** masking the prompt so loss is computed only on the completion will
produce a measurable grounding improvement on the held-out split.

## The single change

`completion_only_loss=True` on a prompt-completion dataset. Everything else is
held fixed: `CohereLabs/tiny-aya-global`, LoRA rank 8 / alpha 16 / dropout 0.05,
2 epochs, lr 2e-6, batch size 1, max_seq_length 512, same 48-task train split
(`tasks/split-train.jsonl`), same conversion to Q4_K_M, same EOS metadata fix,
same Ollama template.

`assistant_only_loss` is **not** used: it requires `{% generation %}` markers,
which Tiny Aya's chat template does not have.

## Mask verification gate (runs before training)

Training proceeds only if, on a real batch built with the real tokenizer:

1. every unmasked (`labels != -100`) span decodes to exactly the example's
   completion string, and
2. the unmasked token count is within ±2 tokens of the completion tokenised
   alone, and
3. the mean unmasked fraction over the training set is between 5% and 35%
   (prompt ~270 tokens, completion ~45, so ~14% expected; the previous run was
   effectively 100%).

If the gate fails, no training run happens and the failure is reported as the
result.

## Pre-specified analysis

- **Split:** `tasks/split-test.jsonl`, 48 held-out tasks. Leak-free: no task
  id, instruction or sheet appears in the training split. Verified by
  `scripts/check_contamination.py`.
- **Comparison:** EOS-fixed converted base (`runs/heldout-base-1.jsonl`)
  against the new masked adapter, both through the same Ollama path, same
  template, temperature 0, two replicates each.
- **Primary metrics** (both pre-specified, no selection after the fact):
  `fabrication_rate` (n=7) and `silent_guess_rate` (n=10).
- **Guard metrics, reported always:** `over_refusal_rate` (n=31),
  `completion_rate` (n=31), plus `parse_success_rate` and
  `format_strict_rate` (n=48). An improvement accompanied by a completion
  drop is a refusal trade, not a win, and will be called one.
- **Secondary:** `collateral_write_rate` (n=16).
- **Test:** exact McNemar, two-sided, on the discordant pairs of each paired
  2x2, via `scripts/paired_analysis.py`. All four cells reported for every
  metric.
- **Replication requirement:** two replicates at temperature 0 must be
  identical, as every previous run in this project has been. If they are not,
  the run is reported as unstable and no claim is made.

## What will be claimed, at what threshold

Stated now so the wording is not chosen to flatter the number.

| outcome | what we will write |
|---|---|
| p < 0.05 on a primary metric, guards not worse | "A statistically significant improvement on <metric>", with cells, p, and n |
| discordant pairs favour improvement, p >= 0.05 | "A directionally positive but **not statistically significant** change of N tasks", with p stated and no claim of effect size |
| zero discordant pairs | "The loss-mask fix changed no decision on held-out data", i.e. H1 is not supported |
| primary improves, a guard worsens | reported as a refusal/abstention trade, not an improvement |

**Power, acknowledged in advance.** With 7 paired observations on
`fabrication_rate`, an exact two-sided McNemar needs 6 discordant pairs all in
one direction to reach p < 0.05 (5 gives p = 0.0625). On `silent_guess_rate`
with 10, it needs 6 of 6. So a real and substantial effect will most likely
still return a non-significant p. **A non-significant result here is therefore
not evidence against H1**, and will not be written as if it were. The
pre-registered reading of "improvement in the discordant pairs, p >= 0.05" is
"consistent with H1, underpowered to confirm".

This is why the mask-verification gate exists: it is the part of this
experiment that yields a definite answer regardless of the eval outcome,
because it checks the mechanism directly rather than through a 7-task metric.

## Stopping rule

One retrain. If the gate passes and the held-out result is null, that is the
reported result and no further training is attempted before the deadline.
