---
title: PLUMB, Grounding Benchmark for Spreadsheet Agents
emoji: 📉
colorFrom: indigo
colorTo: red
sdk: static
app_file: index.html
pinned: false
license: mit
short_description: Four Cohere models, one sheet. Watch safety metrics mislead.
---

# PLUMB

A grounding benchmark for spreadsheet agents, and an interactive look at what
it found.

Agents that read tables fail in a way standard evals miss: they return numbers
that are well-formed, plausible, schema-valid and wrong. PLUMB is 96 locked
tasks that catch three such failures mechanically, with **no LLM judge anywhere
in the scoring**.

## What to click

**Compare the family**: four 3.35B models Cohere Labs ships, same sheet, same
prompt. Start with `p1_control · curator-1-002`: the sheet plainly contains
March sales of 13500, `fire` and `water` return it, and `tiny-aya-earth`
reports that the data is missing. Then open any `p2_ambiguity` task and watch
`tiny-aya-global` pick one of two identically-headed columns without mentioning
that it chose.

**The finding**: ranked by the three safety metrics the family orders
`earth > water > fire > global`; ranked by whether the models actually do the
job, it reverses exactly. `earth` scores 0.0% on fabrication, silent guessing
and collateral writes simultaneously, by answering 0 of 16 answerable control
tasks.

**Score a reply**: drive the real scorer. Invent a number on an unanswerable
task, or write to a cell outside the write-set, and watch which metric fires.

Every model reply shown is a real recorded output from a real run.

## About the scorer on this page

The page runs a JavaScript port of the Python scorer in
[`plumb/score.py`](https://github.com/Dprof-in-tech/plumb). A reimplemented
scorer is exactly the kind of thing this project exists to distrust, so it is
checked rather than trusted:

```bash
node validate.mjs
```

That replays all **384 recorded model replies** through the port and requires
it to reproduce the Python verdict on every one, then runs **128 hand-written
adversarial cases**: fenced blocks, duplicated objects, float and null
answers, lowercase cell refs, no-op edits, truncated JSON, against verdicts
recorded from the real Python scorer. Both must pass with zero mismatches.

One divergence it caught: Python renders a JSON float that happens to be
integer-valued as `13500.0`, while `JSON.parse` collapses it to `13500`, which
made the port *more forgiving* than the scorer it mirrors. `scorer.js` recovers
the numeric literal from the source text to match.

Cell-range expansion is not ported at all, `allowed_cells` is precomputed in
Python and shipped in `data.json`, removing that class of divergence entirely.

## Links

- Code, data, adapters and the full write-up:
  [github.com/Dprof-in-tech/plumb](https://github.com/Dprof-in-tech/plumb)
- Artifacts on the Hub:
  [Isaacdnigerian/plumb](https://huggingface.co/Isaacdnigerian/plumb)

Built for the Lexsi AI Safety and Alignment Hackathon, Track 1.
