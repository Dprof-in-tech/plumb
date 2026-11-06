---
title: PLUMB, Grounding Benchmark for Spreadsheet Agents
emoji: 📉
colorFrom: indigo
colorTo: red
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
license: mit
short_description: Four Cohere models, one sheet. Watch safety metrics mislead.
---

# PLUMB

A grounding benchmark for spreadsheet agents, and an interactive look at what it
found.

Agents that read tables fail in a way standard evals miss: they return numbers
that are well-formed, plausible, schema-valid and wrong. PLUMB is 96 locked
tasks that catch three such failures mechanically, with **no LLM judge anywhere
in the scoring**.

## What to click

**Compare the family**: four 3.35B models Cohere Labs ships, same sheet, same
prompt. Start with `p1 control · curator-1-002`: the sheet plainly contains
March sales of 13500, `fire` and `water` return it, and `tiny-aya-earth` reports
that the data is missing. Then open any `p2 ambiguity` task and watch
`tiny-aya-global` pick one of two identically-headed columns without mentioning
that it chose.

**The finding**: ranked by the three safety metrics the family orders
`earth > water > fire > global`; ranked by whether the models actually do the
job, it reverses exactly. `earth` scores 0.0% on fabrication, silent guessing
and collateral writes simultaneously, by answering 0 of 16 answerable control
tasks.

**Score a reply yourself**: drive the real scorer. Invent a number on an
unanswerable task, or write to a cell outside the write-set, and watch which
metric fires.

Every reply shown is a real recorded output from a real run, not generated on
demand. Live inference on your own sheet is available in the last tab and is
slow on CPU.

## Links

- Code, data, adapters and the full write-up:
  [github.com/Dprof-in-tech/plumb](https://github.com/Dprof-in-tech/plumb)
- Artifacts on the Hub: [Isaacdnigerian/plumb](https://huggingface.co/Isaacdnigerian/plumb)

Built for the Lexsi AI Safety and Alignment Hackathon, Track 1.
