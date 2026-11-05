---
tags:
- curatorkit
---

# Dataset Card: plumb_phase2_review

## Summary

- **Run timestamp**: 2026-11-03T22:35:02.270517Z
- **Wall clock time**: 0.0s
- **Pipeline config hash**: `893cbbb89778d223`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 112 | 112 | — | 0 | 112 |
| ExactDeduplicator | 112 | 34 | — | — | 34 |
| TextCleaner | 34 | 34 | — | — | 34 |
| AlpacaExporter | — | 34 | — | — | 34 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 112/0 passed (N/A), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - exact_duplicates_removed: 78

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
