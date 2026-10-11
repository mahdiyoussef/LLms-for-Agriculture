"""Deterministic eval metrics (stdlib only — no model downloads).

Implements P0.3 metric layer:
- Retrieval: Recall@k, MRR, nDCG@k, Hit@1 from ranked chunk-id lists + graded relevance.
- Generation (no-LLM heuristics, clearly labelled as proxies):
  citation precision/recall (chunk-id/doc-name matching), nugget coverage
  (normalised token overlap), language fidelity (script heuristic),
  numeric-support rate (numbers+units vs evidence/tool text).
- Statistics: bootstrap 95% CIs, paired difference with CI.

These are PROXIES, not substitutes for NLI/HHEM + human calibration (P2).
The harness reports them as `proxy_*` and refuses to present them as faithfulness.
"""
import math
import random
import re
from typing import Dict, List, Sequence

AR_RE = re.compile(r"[\u0600-\u06FF]")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mm|cm|m3|m³|/ha|ha|L/h|L/day|ml/l|g/l|kg/ha|l/ha|ppm|mg/l|kPa|dS/m|%|°C|ET0|ETc|Kc)?", re.I)
CITE_RE = re.compile(r"\[Source:\s*([^\]]+)\]", re.I)


def recall_at_k(ranked: Sequence[str], relevant: Sequence[str], k: int) -> float:
    if not relevant:
        return 1.0
    return len(set(ranked[:k]) & set(relevant)) / len(set(relevant))


def mrr(ranked: Sequence[str], relevant: Sequence[str]) -> float:
    rel = set(relevant)
    for i, doc_id in enumerate(ranked, 1):
        if doc_id in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], graded: Dict[str, int], k: int) -> float:
    def dcg(ids):
        return sum((2 ** graded.get(i, 0) - 1) / math.log2(rank + 1) for rank, i in enumerate(ids[:k], 2))
    ideal = sorted(graded, key=lambda i: graded[i], reverse=True)
    denom = dcg(ideal)
    return dcg(ranked) / denom if denom > 0 else 0.0


def _norm_tokens(s: str) -> List[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", s.lower())


def nugget_coverage(answer: str, nuggets: Sequence[str], threshold: float = 0.5) -> float:
    """Fraction of nuggets with >=threshold token overlap in the answer (proxy)."""
    if not nuggets:
        return 1.0
    ans = set(_norm_tokens(answer))
    hit = 0
    for n in nuggets:
        toks = set(_norm_tokens(n))
        if not toks:
            continue
        if len(toks & ans) / len(toks) >= threshold:
            hit += 1
    return hit / len(nuggets)


def citation_stats(answer: str, retrieved_ids: Sequence[str]) -> Dict[str, float]:
    """Citation precision/recall proxy: cited chunk-ids (or doc names) vs retrieved set."""
    cited = {c.strip() for c in CITE_RE.findall(answer)}
    if not cited:
        return {"citation_precision": 0.0, "citation_recall": 0.0, "num_citations": 0}
    # match on substring either direction (chunk id or doc filename)
    matched = {c for c in cited for r in retrieved_ids if c in r or r in c}
    return {
        "citation_precision": len(matched) / len(cited),
        "citation_recall": len({r for r in retrieved_ids for c in cited if c in r or r in c}) / max(1, len(retrieved_ids)),
        "num_citations": len(cited),
    }


def language_fidelity(question: str, answer: str, language: str) -> float:
    """Proxy: answer script matches query language family. 1.0/0.0 (UNKNOWN→0.5 for Darija-latn)."""
    if language in ("ar", "darija_arab"):
        return 1.0 if AR_RE.search(answer) else 0.0
    if language in ("fr", "en"):
        # answer should be dominantly Latin script
        latin = len(re.findall(r"[A-Za-zÀ-ÿ]", answer))
        return 1.0 if latin > 0 and not AR_RE.search(answer) else 0.0
    return 0.5  # darija_latn / unknown


def numeric_support(answer: str, evidence_texts: Sequence[str]) -> Dict[str, float]:
    """Proxy: fraction of numeric claims in answer also appearing in evidence/tool text."""
    nums = {m.group(0).strip().lower() for m in NUM_RE.finditer(answer)}
    nums = {n for n in nums if re.search(r"\d", n)}
    if not nums:
        return {"numeric_claims": 0, "numeric_supported_rate": 1.0}
    ev = " ".join(evidence_texts).lower()
    supported = {n for n in nums if re.sub(r"\s+", " ", n) in ev or re.match(r"\d+", n).group(0) in ev}
    return {"numeric_claims": len(nums), "numeric_supported_rate": len(supported) / len(nums)}


def mean_ci(values: Sequence[float], n_boot: int = 2000, seed: int = 42) -> Dict[str, float]:
    """Bootstrap 95% CI for the mean. Returns {mean, lo, hi}."""
    vals = list(values)
    if not vals:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0}
    rng = random.Random(seed)
    n = len(vals)
    mean = sum(vals) / n
    if n == 1:
        return {"mean": mean, "lo": mean, "hi": mean}
    boots = []
    for _ in range(n_boot):
        s = sum(rng.choice(vals) for _ in range(n)) / n
        boots.append(s)
    boots.sort()
    return {"mean": mean, "lo": boots[int(0.025 * n_boot)], "hi": boots[int(0.975 * n_boot) - 1]}


def paired_diff_ci(a: Sequence[float], b: Sequence[float], n_boot: int = 2000, seed: int = 42) -> Dict[str, float]:
    """Bootstrap 95% CI for mean(a-b) on paired samples."""
    diffs = [x - y for x, y in zip(a, b)]
    out = mean_ci(diffs, n_boot=n_boot, seed=seed)
    return {"mean_diff": out["mean"], "lo": out["lo"], "hi": out["hi"]}
