"""Minimal tracing (P0.4): stdlib-only JSONL spans, OTel-optional.

Every pipeline stage should emit a span: name, t0/t1, attributes
(router decision, retrieval scores, tokens, truncation flags...).
No personal data in attributes. If opentelemetry is installed, spans are
mirrored there; otherwise the JSONL log is the record (self-hosted
Langfuse/Phoenix can ingest it later — P0.4 remainder).

Usage:
    from src.utils.tracing import span, get_trace_path
    with span("retrieve", {"top_k": 5}) as s:
        ...
        s.set("num_docs", len(docs))
"""
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = Path(os.getenv("GA_RAG_TRACE_DIR", BASE_DIR / "logs" / "traces"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

try:
    from opentelemetry import trace as _otel_trace  # type: ignore
    _OTEL = _otel_trace.get_tracer("ga-rag")
except Exception:
    _OTEL = None


class Span:
    def __init__(self, name: str, attrs: dict = None):
        self.name = name
        self.attrs = dict(attrs or {})
        self.trace_id = os.getenv("GA_RAG_TRACE_ID", uuid.uuid4().hex[:16])
        self.t0 = time.time()

    def set(self, key: str, value):
        self.attrs[key] = value

    def _write(self):
        rec = {"trace_id": self.trace_id, "span": self.name,
               "t_ms": round((time.time() - self.t0) * 1000, 1), "attrs": self.attrs}
        try:
            with open(LOG_DIR / "trace.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def done(self):
        self._write()
        return self.attrs


@contextmanager
def span(name: str, attrs: dict = None):
    s = Span(name, attrs)
    if _OTEL is not None:
        with _OTEL.start_as_current_span(name, attributes={k: str(v) for k, v in s.attrs.items()}):
            yield s
            s.done()
    else:
        try:
            yield s
        finally:
            s.done()


def get_trace_path() -> Path:
    return LOG_DIR / "trace.jsonl"
