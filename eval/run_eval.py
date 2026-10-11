"""One-command eval (P0.3): `python eval/run_eval.py --static` or `--run run.json`.

- `--static`: hardware-independent baseline (gold stats, corpus inventory,
  config hash, static truncation estimate). Always runnable.
- `--run RUN.json --split dev`: scores a system run file against the gold set.
  Run-file entry: {id, answer, retrieved_ids:[...], evidence_texts:[...],
  latency_ms, abstained:bool}.
- Writes eval/reports/{baseline,report}.json + report.md; `--gate baseline.json`
  fails CI if proxy means regress beyond tolerance.

R1: every claim carries bootstrap 95% CI. R3: default split is dev; test only
with --split test (reported once per milestone, never for tuning).
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from metrics import (  # noqa: E402
    recall_at_k, mrr, ndcg_at_k, nugget_coverage, citation_stats,
    language_fidelity, numeric_support, mean_ci, paired_diff_ci,
)

ROOT = pathlib.Path(__file__).parent.parent
GOLD = ROOT / "src" / "evaluation_data"
REPORTS = ROOT / "eval" / "reports"


def config_hash() -> str:
    h = hashlib.sha256()
    for f in ["src/config/config.py", ".env.example", "requirements.txt"]:
        p = ROOT / f
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def corpus_inventory() -> dict:
    pdfs = sorted((ROOT / "documents").rglob("*.pdf"))
    cats = {}
    for p in pdfs:
        cats[p.parent.name] = cats.get(p.parent.name, 0) + 1
    kb = ROOT / "documents" / "primary_kb"
    kb_n = sum(1 for _ in kb.glob("*.md")) if kb.exists() else 0
    return {"num_pdfs": len(pdfs), "by_category": cats, "primary_kb_md": kb_n}


def static_truncation_estimate() -> dict:
    """Chars/4 token estimate for worst/median prompt assemblies (see AUDIT.md §4)."""
    worst = 900 + 5 * 2120 + 1500 + 5 * 2 * 600
    median = 900 + 5 * 720 + 500 + 2 * 2 * 400
    num_ctx = 4096
    return {
        "num_ctx": num_ctx,
        "worst_case_est_tokens": worst // 4,
        "median_case_est_tokens": median // 4,
        "worst_case_silent_truncation_likely": worst // 4 > num_ctx,
        "note": "chars/4 heuristic; tokenizer-based budgeter is P1.7",
    }


def cmd_static() -> dict:
    gold = json.loads((GOLD / "gold_v1.json").read_text(encoding="utf-8"))
    dev = json.loads((GOLD / "dev.json").read_text(encoding="utf-8"))
    test = json.loads((GOLD / "test.json").read_text(encoding="utf-8"))
    by_lang, by_intent, answerable = {}, {}, 0
    for it in gold:
        by_lang[it["language"]] = by_lang.get(it["language"], 0) + 1
        by_intent[it["intent"]] = by_intent.get(it["intent"], 0) + 1
        answerable += bool(it.get("answerable"))
    return {
        "kind": "static-baseline",
        "config_hash": config_hash(),
        "corpus": corpus_inventory(),
        "gold": {"total": len(gold), "dev": len(dev), "test": len(test),
                 "by_language": by_lang, "by_intent": by_intent,
                 "answerable": answerable, "unanswerable": len(gold) - answerable},
        "truncation": static_truncation_estimate(),
        "coverage_gaps": [
            "chunk-level 0/1/2 relevance labels: not yet collected (needs retrieval run)",
            "human review + kappa: pending (P0.2 remainder)",
            "runtime metrics (latency/VRAM/Recall/nDCG): need target HW + deps",
        ],
    }


def score_run(run_path: pathlib.Path, split: str) -> dict:
    gold = {g["id"]: g for g in json.loads((GOLD / f"{split}.json").read_text(encoding="utf-8"))}
    run = json.loads(run_path.read_text(encoding="utf-8"))
    per_item = []
    for entry in run:
        g = gold.get(entry["id"])
        if g is None:
            continue
        ans = entry.get("answer", "")
        ret = entry.get("retrieved_ids", [])
        ev = entry.get("evidence_texts", [])
        rel = entry.get("relevant_ids", [])  # graded relevance optional
        graded = entry.get("graded_relevance", {})
        nug = nugget_coverage(ans, g.get("nuggets", []))
        cite = citation_stats(ans, ret)
        lang = language_fidelity(g["question"], ans, g.get("language", "en"))
        num = numeric_support(ans, ev)
        rec = {"id": entry["id"], "language": g.get("language"), "intent": g.get("intent"),
               "answerable": g.get("answerable"), "proxy_nugget_coverage": nug,
               "proxy_lang_fidelity": lang, **cite, **num,
               "latency_ms": entry.get("latency_ms"),
               "abstained": bool(entry.get("abstained", False))}
        if rel or graded:
            rec["recall_at_5"] = recall_at_k(ret, rel or list(graded), 5)
            rec["recall_at_10"] = recall_at_k(ret, rel or list(graded), 10)
            rec["mrr"] = mrr(ret, rel or list(graded))
            if graded:
                rec["ndcg_at_10"] = ndcg_at_k(ret, graded, 10)
        per_item.append(rec)

    def agg(key, where=lambda r: True):
        return mean_ci([r[key] for r in per_item if key in r and r[key] is not None and where(r)])

    report = {
        "kind": "run-report", "split": split, "n_scored": len(per_item),
        "overall": {
            "proxy_nugget_coverage": agg("proxy_nugget_coverage"),
            "proxy_lang_fidelity": agg("proxy_lang_fidelity"),
            "citation_precision": agg("citation_precision"),
            "citation_recall": agg("citation_recall"),
            "numeric_supported_rate": agg("numeric_supported_rate"),
        },
        "slices": {},
    }
    for dim in ("language", "intent"):
        for val in sorted({r[dim] for r in per_item}):
            report["slices"][f"{dim}={val}"] = {
                "n": sum(1 for r in per_item if r[dim] == val),
                "proxy_nugget_coverage": agg("proxy_nugget_coverage", lambda r, v=val: r[dim] == v),
            }
    if any("recall_at_5" in r for r in per_item):
        report["overall"]["recall_at_5"] = agg("recall_at_5")
        report["overall"]["recall_at_10"] = agg("recall_at_10")
        report["overall"]["mrr"] = agg("mrr")
    lats = [r["latency_ms"] for r in per_item if r["latency_ms"] is not None]
    if lats:
        lats_sorted = sorted(lats)
        report["efficiency"] = {"n": len(lats_sorted),
                                "p50_ms": lats_sorted[len(lats_sorted) // 2],
                                "p95_ms": lats_sorted[int(0.95 * (len(lats_sorted) - 1))]}
    return {"report": report, "per_item": per_item}


def to_markdown(obj: dict) -> str:
    lines = ["# Eval report", "", f"kind: `{obj.get('kind')}`"]
    if obj.get("kind") == "static-baseline":
        lines += [f"config_hash: `{obj['config_hash']}`",
                  f"corpus PDFs: {obj['corpus']['num_pdfs']} (+{obj['corpus']['primary_kb_md']} KB .md)",
                  f"gold: {obj['gold']['total']} (dev {obj['gold']['dev']}, test {obj['gold']['test']})",
                  f"truncation worst-case ~{obj['truncation']['worst_case_est_tokens']} tok "
                  f"(silent truncation likely: {obj['truncation']['worst_case_silent_truncation_likely']})",
                  "", "## Coverage gaps"] + [f"- {g}" for g in obj["coverage_gaps"]]
    else:
        r = obj["report"]
        lines.append(f"split: `{r['split']}`, scored: {r['n_scored']}")
        for k, v in r["overall"].items():
            lines.append(f"- {k}: {v['mean']:.3f} [{v['lo']:.3f}, {v['hi']:.3f}]")
        lines.append("\n## Slices")
        for k, v in r["slices"].items():
            m = v["proxy_nugget_coverage"]
            lines.append(f"- {k} (n={v['n']}): nugget {m['mean']:.3f} [{m['lo']:.3f}, {m['hi']:.3f}]")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--run", type=str, default=None)
    ap.add_argument("--split", type=str, default="dev", choices=["dev", "test"])
    ap.add_argument("--gate", type=str, default=None,
                    help="baseline JSON to compare against; exits 1 on regression > tol")
    ap.add_argument("--tol", type=float, default=0.02)
    args = ap.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)

    if args.static:
        obj = cmd_static()
        (REPORTS / "baseline.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        (REPORTS / "baseline.md").write_text(to_markdown(obj), encoding="utf-8")
        print(json.dumps(obj, ensure_ascii=False, indent=2)[:2000])
        print(f"\nwrote {REPORTS/'baseline.json'}")
        return

    if args.run:
        out = score_run(pathlib.Path(args.run), args.split)
        obj = {"kind": out["report"]["kind"], "report": out["report"]}
        (REPORTS / "report.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        (REPORTS / "report.md").write_text(to_markdown(obj), encoding="utf-8")
        (REPORTS / "per_item.json").write_text(json.dumps(out["per_item"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(to_markdown(obj))
        if args.gate:
            base = json.loads(pathlib.Path(args.gate).read_text(encoding="utf-8"))
            base_rep = base.get("report", base)
            cur = obj["report"]["overall"]
            failed = False
            for k, v in cur.items():
                b = (base_rep.get("overall", base_rep) or {}).get(k)
                if isinstance(b, dict) and v["mean"] < b["mean"] - args.tol:
                    print(f"GATE FAIL: {k} {v['mean']:.3f} < baseline {b['mean']:.3f} - tol")
                    failed = True
            raise SystemExit(1 if failed else 0)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
