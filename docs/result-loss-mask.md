# Result: loss-mask SFT retrain

Outcome of the experiment pre-registered in
`docs/preregistration-loss-mask.md`. That file was committed before this run
existed (commit `96e152e`); this one reports against it without editing it.

## Headline: the replication gate failed, so no grounding claim is made

The pre-registration states: *"two replicates at temperature 0 must be
identical, as every previous run in this project has been. If they are not, the
run is reported as unstable and no claim is made."*

They are not identical.

| run | environment | fabrication (n=7) | silent guess (n=10) | collateral (n=16) | over-refusal (n=31) | completion (n=31) |
|---|---|---:|---:|---:|---:|---:|
| base (reference) | laptop | 71.4% | 40.0% | 0.0% | 12.9% | 80.6% |
| base (validation) | HF Job | 71.4% | 40.0% | 0.0% | 12.9% | 80.6% |
| masked replicate A | laptop | 85.7% | 50.0% | 0.0% | 12.9% | 80.6% |
| masked replicate B | HF Job | 71.4% | 50.0% | 0.0% | 12.9% | 80.6% |
| masked replicate C | HF Job | 85.7% | 50.0% | 0.0% | 9.7% | 83.9% |

Three runs of one model on one task file at temperature 0 produced three
different metric vectors. **Per the pre-registered rule, the masked adapter's
grounding is reported as unstable and no effect is claimed in either
direction.**

## What is unstable, exactly

Two tasks out of 48 disagree with themselves across runs. Both flip between
`needs_clarification` and `answered`, and they flip in opposite directions:

| task | probe | answerable | flips between | effect when it answers |
|---|---|---|---|---|
| `curator-4-005` | p3_collateral | yes | `needs_clarification` / `answered` with edit `B2: 13200` | **correct**: completes the write task properly |
| `curator-4-007` | p1_fabrication | no | `needs_clarification` / `answered: 55` | **a fabrication**: the sheet cannot support it |

So the instability is not noise around a fixed quality level. On one task the
model is sometimes right and sometimes needlessly abstains; on another it is
sometimes correctly abstaining and sometimes fabricating. Whichever way those
two land determines fabrication, over-refusal and completion for the whole run.
The remaining 46 tasks are stable.

## The mechanism was real and is fixed

This part is established independently of the unstable evaluation, which is why
the pre-registration put a verification gate before training.

| | previous run | masked run |
|---|---:|---:|
| unmasked token fraction | 1.000 | **0.065** (verified on a real batch) |
| `train_loss` after 2 epochs | 3.045 | **1.884** |
| LoRA config | r8 / α16 / dropout 0.05 / q,k,v,o | **byte-identical** |

The gate decoded the unmasked span from a real dataloader batch and confirmed it
was exactly the JSON completion: 18 of 276 tokens. Measured on the real
tokenizer, the 48 training examples average 264.5 prompt tokens against 22.4
completion tokens, so the previous run spent about **92% of its gradient trying
to predict serialised spreadsheet cells**: arbitrary data the model cannot
learn. That fully explains a `train_loss` of 3.045 on 48 gold examples, and the
38% drop confirms it.

Two implementation notes for anyone repeating this:

- `DataCollatorForCompletionOnlyLM` was **removed in TRL 1.7**. The supported
  replacement is `completion_only_loss=True` on a prompt-completion dataset,
  which derives the boundary from the dataset columns and needs no
  `{% generation %}` chat-template markers, so Tiny Aya's lack of them is not
  the blocker it appeared to be.
- The likely original cause: AlignTune's generic dataset adapter **adds a
  `text` column** alongside `prompt`/`completion`. A `text` column makes TRL
  read the dataset as language-modelling and mask nothing. The fix is to load
  only the two columns.

## What this changes about the project's conclusions

**The null training result stands and is now better supported.** The most
plausible mechanical explanation for four failed interventions, that the loss
was never pointed at the completions, has been eliminated. The loss is now
provably on the completion and the model still does not ground better.

**One prior claim is weakened.** This project repeatedly cited "three identical
replicates at temperature 0" as evidence that its measurements were sound. That
property turns out to belong to the *base model*, not to the harness: the base
reproduced identically across five runs and two machines, while an adapter of
the same model on the same harness does not reproduce at all. Replicate
identity was evidence about the model under test, and it was being read as
evidence about the measurement chain.

**The honest summary of all training work in this project:** four interventions
(two DPO, one contaminated SFT, one correctly-masked SFT), no demonstrated
improvement in grounding that generalises, and the one adapter whose training
objective was verifiably correct is also the one that fails to produce a
reproducible evaluation.

## Pre-registration miss, recorded

The pre-registered claim table had four outcome rows: significant improvement,
directional improvement, zero discordant pairs, and improvement-with-guard-
worsening. **It had no row for "primary metrics worsen" and no row for "the
replication requirement fails."** The replication rule existed in the document
but its consequence was not in the claim table, and the direction of the
observed change was not anticipated at all. Recorded here rather than
retrofitted into one of the existing rows.

## Reproduction

```bash
# training, with the mask gate (fails closed)
python3 scripts/hf_sft_masked.py          # see the script header for env vars

# evaluation, on rented hardware, self-validating
bash scripts/hf_eval_ollama.sh            # re-runs the base first; it must
                                          # reproduce the recorded row
```

Artifacts: adapter at `training/sft-output-masked` (with `mask_report.json`),
GGUF at `training/ollama/sft-masked-Q4_K_M.gguf`, runs at
`runs/masked-sft-1.jsonl` and `runs/hfeval-*.jsonl`.
