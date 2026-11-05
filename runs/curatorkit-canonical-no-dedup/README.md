---
tags:
- curatorkit
configs:
- config_name: sft_alpaca
  default: true
  description: curatorkit sft_alpaca export, sha256 0673fb46db66349eab978e73d305caca758d6edd7184f0170ba34055ab3d373f
  data_files:
  - split: train
    path: sft_alpaca.jsonl
---

# Dataset Card: plumb_phase2_review

## Summary

- **Run timestamp**: 2026-11-03T22:38:40.276915Z
- **Wall clock time**: 0.0s
- **Pipeline config hash**: `bd33d5d80e804b50`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 112 | 112 | — | 0 | 112 |
| TextCleaner | 112 | 112 | — | — | 112 |
| AlpacaExporter | — | 112 | — | — | 112 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 112/0 passed (N/A), 0 rejected


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
| `sft_alpaca` | train (112) | `instruction`: string<br>`input`: string (empty when there is no input)<br>`output`: string |
