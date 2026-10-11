"""Index manifest (P0.5): prevents silent embedder/index mismatch.

Manifest records {embedding model+dim, chunker version, parser version,
corpus hash} at ingest time. Query path refuses to serve on mismatch
unless GA_RAG_ALLOW_MANIFEST_MISMATCH=1 (escape hatch for dev).

Stdlib-only so `make baseline` and tests run without torch.
"""
import hashlib
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
MANIFEST_PATH = BASE_DIR / "data" / "index_manifest.json"

CHUNKER_VERSION = "recursive-600-90+v1"  # processor.py RecursiveCharacterTextSplitter(600/90)
PARSER_VERSION = "pdfplumber+pypdf-fallback+v1"


def _read_config_values() -> dict:
    """Parse (not import) config.py so this works without torch installed."""
    text = (BASE_DIR / "src" / "config" / "config.py").read_text(encoding="utf-8")
    import re
    m = re.search(r'"model_name":\s*"([^"]+)"', text)
    dim = re.search(r'"embedding_dimension":\s*(\d+)', text)
    return {"embedding_model": m.group(1) if m else "UNKNOWN",
            "embedding_dimension": int(dim.group(1)) if dim else -1}


def corpus_hash(documents_dir: Path = None, sample_bytes: int = 65536) -> str:
    """Hash of PDF inventory (names+sizes) + metadata.json. Cheap; full re-hash in P1."""
    documents_dir = documents_dir or (BASE_DIR / "documents")
    h = hashlib.sha256()
    for p in sorted(documents_dir.rglob("*.pdf")):
        h.update(f"{p.relative_to(documents_dir)}:{p.stat().st_size}\n".encode())
    meta = documents_dir / "metadata.json"
    if meta.exists():
        h.update(meta.read_bytes()[:sample_bytes])
    return h.hexdigest()[:16]


def expected_manifest() -> dict:
    cfg = _read_config_values()
    return {**cfg, "chunker_version": CHUNKER_VERSION,
            "parser_version": PARSER_VERSION, "corpus_hash": corpus_hash()}


def write_manifest(path: Path = MANIFEST_PATH) -> dict:
    man = expected_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(man, indent=2), encoding="utf-8")
    return man


def check_manifest(path: Path = MANIFEST_PATH) -> dict:
    """Returns {ok, expected, stored, mismatches}. Raises RuntimeError on mismatch
    unless GA_RAG_ALLOW_MANIFEST_MISMATCH=1."""
    exp = expected_manifest()
    if not path.exists():
        write_manifest(path)
        return {"ok": True, "expected": exp, "stored": exp, "mismatches": [],
                "note": "no prior manifest; wrote current config as baseline"}
    stored = json.loads(path.read_text(encoding="utf-8"))
    bad = [k for k in exp if stored.get(k) != exp[k]]
    if bad and os.getenv("GA_RAG_ALLOW_MANIFEST_MISMATCH", "") != "1":
        raise RuntimeError(
            f"Index manifest mismatch on {bad}: stored={stored} expected={exp}. "
            "Re-ingest with the current config, or set GA_RAG_ALLOW_MANIFEST_MISMATCH=1.")
    return {"ok": not bad, "expected": exp, "stored": stored, "mismatches": bad}
