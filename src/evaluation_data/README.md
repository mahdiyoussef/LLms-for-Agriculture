# Gold evaluation set (P0.2)

Frozen, versioned QA set for retrieval + answer evaluation.
- `gold_v1.json`: all items with `nuggets` (required facts), `answerable`, `review_status`.
- `dev.json` / `test.json`: 70/30 stratified split (seed 42). **Test is frozen — never tune on it (R3).**
- Item fields: `id, question, language, intent, region, crop, nuggets, answerable, review_status`.
- Chunk-level 0/1/2 relevance labels: NOT yet collected — P0.2 remainder (needs retrieval run on target HW).
