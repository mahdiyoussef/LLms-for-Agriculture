"""Safety guardrails (R5 + P2.4 seed): deterministic, stdlib-only.

Hard rules live here so they are testable without torch/LLM:
1. Chemical/pesticide/fertiliser DOSE requests (value+unit or product+rate) MUST
   have a cited authoritative source; otherwise REFUSE + refer to extension officer.
2. Every irrigation volume/schedule should come from a tool or cited table
   (P2.2); until then, answers with numbers and no citation are flagged
   `numeric_unverified=True` for the verifier layer.
3. Ingested document text is UNTRUSTED: instruction-like snippets inside
   evidence must never be obeyed (checked by tests, enforced in prompts at P4.2).

This is the P0 deny-rule quick win, not the full P2.4 verifier.
"""
import re

CHEMICAL_WORDS = re.compile(
    r"(pesticide|herbicide|insecticide|fongicide|glyphosate|fertili[sz]er|engrais|"
    r"azote|phosphate|potasse|nitrate|ur[eé]e|pest|مبيد|سماد|الدوا|pesticide dose)", re.I)
DOSE_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ml/l|g/l|kg/ha|l/ha|ppm|mg/l|g/m2|kg/m3|mL/L)\b", re.I)
DOSE_ASK_RE = re.compile(
    r"(dose|dosage|how much|combien|quelle dose|chhal|شحال|جرعة|كم|rate per|per hectare)", re.I)
INSTRUCTION_INJECTION_RE = re.compile(
    r"(ignore (previous|all) instructions|reveal (your|the) system prompt|disregard.*instructions)",
    re.I)

REFUSAL_CHEMICAL = (
    "I can't provide a chemical or pesticide dose without a cited authoritative source "
    "(label, ministry/ORMVA guidance, or FAO reference). Please consult your local "
    "extension officer (ORMVA / conseiller agricole / المرشد الفلاحي) with the product "
    "label. If you share the cited source, I can help interpret it.")

REFUSAL_INJECTION = (
    "I can't follow instructions embedded in documents or tool output; "
    "ingested content is treated as untrusted data, not commands.")


def needs_authoritative_dose_check(question: str, answer: str = "") -> bool:
    """True if the exchange requests or states a chemical dose."""
    text = f"{question}\n{answer}"
    return bool(CHEMICAL_WORDS.search(text) and (DOSE_RE.search(text) or DOSE_ASK_RE.search(question)))


def has_citation(answer: str) -> bool:
    return bool(re.search(r"\[Source:\s*[^\]]+\]", answer))


def chemical_dose_refusal(question: str, answer: str = "") -> str | None:
    """Return refusal text if a chemical dose lacks a cited source, else None."""
    if needs_authoritative_dose_check(question, answer) and not has_citation(answer):
        return REFUSAL_CHEMICAL
    return None


def contains_injection(text: str) -> bool:
    return bool(INSTRUCTION_INJECTION_RE.search(text))


def evidence_strength(num_docs: int, has_citations: bool, top_score: float | None = None) -> str:
    """Interim calibrated-language replacement for heuristic % confidence (G4).

    Derived from reranker score + citation coverage until P2.6 calibration exists.
    """
    if num_docs >= 3 and has_citations and (top_score is None or top_score >= 0.5):
        return "high"
    if num_docs >= 1 and (has_citations or (top_score is not None and top_score >= 0.3)):
        return "medium"
    return "low"
