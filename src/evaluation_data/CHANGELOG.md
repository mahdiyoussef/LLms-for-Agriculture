# Gold set changelog

## v1-seed (2026-10-11)
- 106 items (50 legacy EN + 56 authored).
- Languages: en/fr/ar/darija_latn/darija_arab. Intents include numeric, unanswerable, out-of-region, adversarial (incl. prompt-injection + chemical-dose refusal).
- 70/30 dev/test split, seed 42, stratified by (language, intent).
- Status: DRAFT seed. Human review pending: 30% overall, 100% of numeric/adversarial. Cohen kappa NOT yet measured (requires double annotation of 50-item overlap).
- Target full v1: 300-500 items; grow via `src/evaluation_data/` + /feedback queue (P4.3).
