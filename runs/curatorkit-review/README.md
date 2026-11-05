---
tags:
- curatorkit
---

# Dataset Card: plumb_phase2_review

## Summary

- **Run timestamp**: 2026-11-03T22:33:11.120516Z
- **Wall clock time**: 0.1s
- **Pipeline config hash**: `63c2acbda991943b`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 0 | 0 | — | 6395 | 0 |
| ExactDeduplicator | 0 | 0 | — | — | 0 |
| TextCleaner | 0 | 0 | — | — | 0 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 0/0 passed (N/A), 6395 rejected


**Rejection reasons:**
  - `invalid_forced_format:jsonl`: 6395

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
