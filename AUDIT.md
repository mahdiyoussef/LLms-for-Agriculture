# AUDIT.md — GA-RAG Precision Agriculture: Repository & Behaviour Audit (P0.1)

Date: 2026-10-11 · Auditor: engineering agent · Scope: unmodified repo at `916d04c`
Method: static reads of all `src/**/*.py`, `config.py`, tests, `documents/` sampling via
`pdftotext` (stdlib + poppler only; **no** torch/langchain/spacy installed, no Ollama).
Anything not directly observed is marked **UNKNOWN**. No benchmark numbers are claimed.

## 1. Assumption verdicts (A1–A7)

| ID | Assumption | Verdict | Evidence |
|----|------------|---------|----------|
| A1 | Corpus is FR/AR-heavy while pipeline is English-centric | **REFUTED (corpus side), CONFIRMED (pipeline side)** | Sampled 14 PDFs (2/category) + 4 Morocco-specific docs via `pdftotext`: **0 Arabic-script chars in every sample**; `primary_kb/` samples are English academic prose. `irrigation_qa_dataset.json`: 50/50 English, no `language` field. Pipeline is English-centric: reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`, SpaCy `en_core_web_sm`, English `SYSTEM_PROMPT`/`DOMAIN_SYNONYMS`, BM25 `re.findall(\b\w+\b).lower()` with no AR/FR analyser. **Surprise:** `config.py:57-58` embedder is `distiluse-base-multilingual-cased-v2` (512-d multilingual), **not** `all-MiniLM-L6-v2` (384-d) as README claims; `.env.example:11` also says MiniLM. Real gap is **cross-lingual**: FR/AR/Darija farmer queries against EN documents. |
| A2 | Chunk metrics never validated vs retrieval/answer quality | **CONFIRMED** | `semantic_chunker.py:451-572`: stickiness, CIG, boundary-clarity implemented; no caller correlates them with Recall or answer scores. README §14 admits approximations (`unique_ratio` as entropy, cosine as MI). |
| A3 | Judge = same 3B generator (self-preference) | **CONFIRMED** | `utils/evaluator.py:98-109` (+ duplicate `application/evaluation/rag_eval.py`): all 5 judges use `LLM_CONFIG["model"]` = `llama3.2:3b`. `agentic_eval.py:247` falls back to `gemma2:9b` via Ollama `/v1`. |
| A4 | Confidence is uncalibrated heuristic | **CONFIRMED** | `rag_chain.py:211-238` (`0.5+src/cite−uncertainty`), `rag_orchestrator.py:543` (`0.4+0.1·n_src+0.05·n_find`), router `min(score/5,1)` (`query_router.py:226`). No calibration, no ECE. |
| A5 | Agronomic numbers are LLM-generated | **CONFIRMED** | No ET0/Kc/water-balance/unit tool exists. Only numeric-adjacent tool is the new Open-Meteo weather path (`agents/weather_agent.py`, `infrastructure/weather_service.py`, TTL 1800 s, timeout 10 s). |
| A6 | Router is regex/intent-pattern based | **CONFIRMED** | `retrieval/query_router.py:109-179` compiled regexes + keyword `+1.0`, pattern `+3.0`; `application/agents/rag_agent.py:138` second regex set. No learned router, no abstain/calc/no-retrieval routes. |
| A7 | Llama 3.2 3B has limited Arabic support | **UNKNOWN (unverified)** | No Ollama in this env (`ollama: command not found`); model card not fetched. Must verify + measure FR/AR/Darija fidelity on gold set. |

## 2. Corpus statistics (measured)

- PDFs: **48** (01:9, 02:11, 03:8, 04:7, 05:3, 06:3, 07:7) + `AGRIS.ODS.xml` (2.3 MB) + `primary_kb/` **3592 `.md`** (~709 MB, AGRIS-derived, English samples).
- Language (first-2-pages sample + 4 full-text Morocco docs): **English throughout; 0 Arabic-script characters anywhere sampled**. French-hit counts are English/French cognate overlap — inconclusive, treat as UNKNOWN pending full-text lang-ID.
- Scanned/low-text pages exist (e.g. `425362469-Water-Reuse-for-Irrigation.pdf`: 71 chars on pp.1–2; two 02_* PDFs <300 chars) → pdfplumber/pypdf path will silently yield near-empty chunks (pages <50 chars are skipped, so content is **lost, not flagged**).
- `metadata.json` lists only a subset of actual PDFs (drift: documents added without metadata update).

## 3. Defect list (ordered by risk)

1. **Silent truncation (G7).** `LLM_CONFIG num_ctx=4096`; 5 chunks × up to 2000 chars + contextual headers + KG context + 5-turn history + system prompt exceeds budget on long queries. `rag_chain.py:171` logs only `len(prompt)` chars; `num_predict=512` is **never passed** to `Ollama()` (`rag_chain.py:35-44`). Hard slices (`text[:500]` in orchestrator/server, `context[:2000/4000]` in agent/eval) truncate evidence without flags.
2. **Embedder identity drift.** README/`VECTOR_STORE_CONFIG`/`EMBEDDING_CONFIG` disagree (MiniLM 384-d vs distiluse-multilingual 512-d). No index manifest; a re-ingest with the other model silently breaks retrieval. → Fixed in P0.5 (manifest + refuse-on-mismatch).
3. **Self-judging (G5).** Reported quality numbers come from the generator itself. → P0.3 harness uses rule/NLI primary + optional distinct API judge; generator score never reported.
4. **Heuristic confidence (G4).** See A4. → Interim `evidence_strength` (P0 quick win) → calibrated bands in P2.6.
5. **Numeric safety (G3).** Dose/volume arithmetic by LLM; no unit handling; no refusal policy in code. → Deny rule quick win + P2.2 tool layer.
6. **Duplicated modules.** `generation/rag_orchestrator.py` ≈ `application/agents/orchestrator.py` (latter lacks weather); `utils/evaluator.py` ≈ `application/evaluation/rag_eval.py`. Import drift risk; dedupe in P1 (not P0 — behaviour freeze).
7. **Multi-query fan-out without RRF.** `main.py:158-180` dedups by max score; `aggregation_method: reciprocal_rank_fusion` in config is never applied across query variants. RRF only fuses semantic+keyword (`hybrid_retriever.py:164`).
8. **KG fragility (G12).** `en_core_web_sm` only, 500-char proximity edges, pickle persistence, ego-graph retrieval. No P0 change; slice-evaluated in P3.2 with kill-switch.
9. **Agent budgets (G13).** Only `max_attempts=5`; no token/time budget, loop detection is visited-set only. → P3.3.
10. **Production gaps (G14).** No auth/rate-limit/tracing/feedback/injection handling. → P0.4 tracing first; rest in P4.

## 4. Truncation estimate (static, chars/4 ≈ tokens)

Worst-case single-pass prompt ≈ system (~900 ch) + 5×(2000+header ~120) + KG (~1500) + history 5×2×(~600) ≈ **19k chars ≈ 4.8k tokens > 4096**. Median case (600-char recursive chunks) fits. Conclusion: truncation is **query-dependent and silent** — budgeter required (P1.7); logging added now (quick win).

## 5. What P0.1 did NOT verify (needs runtime)

Ollama generation, embedding/rerank latency + VRAM, Chroma recall, SpaCy extraction quality, full-text language-ID, human κ. All gated on target hardware in P0.2–P0.3.

## 6. Config/licence notes

- `torch` imported unconditionally in `config.py` → whole package unimportable without torch. Loosened to optional (CPU fallback) in P0 so tests/eval run anywhere. Behaviour with torch installed is unchanged.
- Licence register missing (K9): 48 PDFs + 3592 AGRIS `.md` have no recorded licences. **Do not redistribute corpus or fine-tune on it until cleared (R8).**
