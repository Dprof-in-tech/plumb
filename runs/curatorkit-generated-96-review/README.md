---
tags:
- curatorkit
configs:
- config_name: sft_alpaca
  default: true
  description: curatorkit sft_alpaca export, sha256 830605c8f3516ee15b7b642511f10af61a8ab02211e7bf5f954e27844c036bd3
  data_files:
  - split: train
    path: sft_alpaca.jsonl
---

# Dataset Card: plumb_phase2_review

## Summary

- **Run timestamp**: 2026-11-04T08:07:44.490392Z
- **Wall clock time**: 0.1s
- **Pipeline config hash**: `42f1a7885650f704`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 96 | 96 | — | 0 | 96 |
| TextCleaner | 96 | 96 | — | — | 96 |
| AlpacaExporter | — | 96 | — | — | 96 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 96/0 passed (N/A), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - No deduplication step recorded

## Known Limitations

- No MinHash deduplication applied.
- Table extraction requires `extract_tables: true` on the PDF reader and MinerU with GPU support. Disabled by default.
- Token counting uses a whitespace tokenizer by default. For exact LLM context window
  enforcement, enable `use_tiktoken: true` in the SchemaGate config.
- Both within-run (MinHash/Diversity) and cross-run (EmbeddingDeduplicator) deduplication
  are available. Cross-run dedup persists an embedding index across runs; use
  `embedding_reset_index: true` to start fresh.

## Reproduction

```bash
pip install curatorkit
curatorkit run pipeline.yaml --output-dir ./out/
```

## Tool Versions

- **curatorkit**: 0.1.22
- **python**: 3.13.1

## Configs

Load one with `datasets.load_dataset("<this folder or Hub repo>", "<config>")`.

| Config | Splits (rows) | Columns |
|--------|---------------|---------|
| `sft_alpaca` | train (96) | `instruction`: string<br>`input`: string (empty when there is no input)<br>`output`: string |
