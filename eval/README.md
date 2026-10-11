# Evaluation harness (P0.3)

## Commands

```bash
make eval          # static baseline (always works, no deps)
python eval/run_eval.py --static
python eval/run_eval.py --run eval/sample_run.json --split dev
python eval/run_eval.py --run run.json --split dev --gate eval/reports/baseline.json
```

## Judge policy (G5 fix)

- **Primary (checked in): proxy metrics in `eval/metrics.py`** — deterministic, stdlib-only,
  computed from a run file. They are labelled `proxy_*` and are NOT faithfulness.
- **Secondary (offline): a different, stronger judge** (API model allowed per owner decision),
  run manually on samples; never the `llama3.2:3b` generator itself.
- **Calibration:** before any automated judge drives a decision, calibrate on ≥100
  human-labelled items and report agreement (P2). The generator's own
  `_estimate_confidence` MUST NOT be reported as a quality number (see AUDIT.md A3/A4).

## Run-file format

```json
[{"id": "v1-001", "answer": "... [Source: doc.pdf]",
  "retrieved_ids": ["abc123", "..."], "evidence_texts": ["..."],
  "relevant_ids": ["..."], "graded_relevance": {"abc123": 2},
  "latency_ms": 1234, "abstained": false}]
```

`relevant_ids`/`graded_relevance` enable Recall/MRR/nDCG; without them the report
covers generation proxies + slices only. Slices always reported: language, intent
(+ region/crop/numeric/answerable when run entries carry them).

## Statistics (R1)

All means carry bootstrap 95% CIs (`n_boot=2000`, seed 42). A/B uses paired
difference CIs (`paired_diff_ci`); fix the decision rule BEFORE running (R1/R2).
