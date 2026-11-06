# Pre-registration: the recipe experiment (attempt 7)

Written **before** the run existed, committed ahead of it, and reported against
without editing. The same discipline as `docs/preregistration-loss-mask.md`,
which is the only reason the loss-mask result was not reported as a win off one
replicate.

- **Date written:** 6 Nov 2026
- **Attempts so far:** six, all negative.

## What every previous attempt had in common

Six runs varied the *data*: contaminated, clean, imbalanced, exactly balanced,
96 examples to 450. All six produced a model that abstains *less* than the base
it started from. The converted base declines on 56% of genuinely unanswerable
tasks; every fine-tuned model declines on none.

The constant across all six is the recipe:

```
LoRA rank 8, alpha 16, dropout 0.05
target_modules = q_proj, k_proj, v_proj, o_proj
learning_rate  = 2e-6
epochs         = 2
```

## Hypothesis

**H1: the recipe cannot move a decision policy, so the model falls back to its
prior regardless of the data.**

The specific suspicion is the learning rate. 2e-6 is a *full fine-tuning* rate.
LoRA adapters are normally trained at 1e-4 to 2e-4, roughly fifty times higher,
because only a low-rank update is being learned. A rank-8 adapter on attention
projections at 2e-6 for two epochs may change surface wording, which is what
was observed on the held-out split, without changing which status the model
chooses.

This is a hypothesis of the same kind as the one that failed last run, and it
is written down as such. The balance hypothesis was stated with equal
confidence and was wrong.

## The change

One coherent change to the recipe, holding the data fixed at the audited,
balanced 450-task corpus used in attempt 6:

| | attempts 1-6 | attempt 7 |
|---|---|---|
| learning rate | 2e-6 | **1e-4** |
| LoRA rank | 8 | **32** |
| alpha | 16 | **64** |
| target modules | attention only | **all linear projections** |
| epochs | 2 | **3** |

Data, benchmark, serving path, mask gate, contamination gate and audit are
unchanged, so the recipe is the only thing that moves.

## Pre-specified analysis

- **Eval set:** `tasks/phase2-curatorkit-generated-96-p2v5.jsonl`, the corrected
  benchmark, so `fabrication_rate` is not the inflated figure.
- **Comparison:** converted base through the identical path, two replicates each.
- **Test:** exact McNemar on discordant pairs, all four cells reported, via
  `scripts/paired_analysis.py`.
- **Reported first, before any metric:** the status distribution across all 96
  tasks. On attempts 5 and 6 that single line was more informative than the
  whole metric table.

## What counts as success, decided now

**Gate 0, a precondition.** The model must return more than one status across
the 96 tasks. A model emitting a single constant has not learned a policy and
no metric from it will be interpreted, whichever direction the constant points.

Then, all three must hold:

1. `fabrication_rate` or `silent_guess_rate` improves against the base by more
   than one task, with the paired table showing discordant pairs favouring the
   improvement.
2. `over_refusal_rate` stays at or below **25%**.
3. `completion_rate` stays at or above **60%**.

Conditions 2 and 3 exist because the two ways this has failed are opposite
constants. Attempt 1 scored 0.0% on all three safety metrics by refusing
everything; attempts 5 and 6 scored 0.0% over-refusal by answering everything.
Either would satisfy condition 1 alone.

## What will be written, per outcome

| outcome | wording |
|---|---|
| gate 0 fails | "attempt 7 produced a constant-output model; the recipe hypothesis is not supported" |
| gate 0 passes, all three hold, p < 0.05 | "a statistically significant improvement from the recipe change", with cells, p and n |
| gate 0 passes, all three hold, p >= 0.05 | "directionally positive, not statistically significant", with the discordant counts |
| condition 1 holds but 2 or 3 fails | reported as an abstention trade, not an improvement |
| nothing improves | the seventh negative result, reported as such |

**Power.** With 9 unanswerable and 16 ambiguity tasks, an exact two-sided
McNemar needs 6 discordant pairs in one direction to clear p < 0.05. A real
effect may well return non-significant, and that will not be written as
evidence against H1.

## Stopping rule

**One run.** If attempt 7 fails, training stops and the submission is made on
the benchmark, the measurement-failure sequence, and the harness result. No
further recipe search, because at that point seven controlled attempts across
both the data and recipe axes is the finding.
