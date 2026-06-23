"""Local RAG retrieval over the synthetic record corpus (Phase 7).

Optional Chroma-backed semantic retrieval with a zero-dependency keyword
fallback so the demo always runs. Retrieval returns supporting record snippets
(with IDs) that can be cited in the draft summary — it never invents content.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from rca_copilot.data.synthetic import Dataset


@dataclass(frozen=True)
class Retrieved:
    record_id: str
    record_type: str
    text: str
    score: float


def build_corpus(dataset: Dataset) -> pd.DataFrame:
    """One document per supporting record: id, type, and a searchable text blob."""
    ev = dataset.evidence.copy()
    ev["text"] = (
        ev["category"] + " | " + ev["subcategory"] + " | " + ev["title"].fillna("")
        + ev["outcome"].fillna("").map(lambda s: f" | {s}" if s else "")
    )
    return ev[["record_id", "record_type", "text"]]


def _keyword_search(corpus: pd.DataFrame, query: str, k: int) -> list[Retrieved]:
    terms = {t for t in query.lower().split() if len(t) > 2}
    rows = []
    for _, r in corpus.iterrows():
        text = str(r["text"]).lower()
        overlap = sum(1 for t in terms if t in text)
        if overlap:
            rows.append(Retrieved(r["record_id"], r["record_type"], r["text"], float(overlap)))
    rows.sort(key=lambda x: x.score, reverse=True)
    return rows[:k]


def retrieve(dataset: Dataset, query: str, k: int = 5) -> list[Retrieved]:
    """Retrieve top-k records for a query.

    Uses Chroma if installed; otherwise falls back to keyword overlap. Both paths
    return the same `Retrieved` shape, so callers don't branch.
    """
    corpus = build_corpus(dataset)
    try:
        import chromadb  # noqa: F401  (optional dependency)
    except ImportError:
        return _keyword_search(corpus, query, k)

    # TODO(phase-7): persist a Chroma collection of `corpus` and query embeddings.
    # Until that is wired up, behave identically to the keyword fallback so the
    # demo is deterministic.
    return _keyword_search(corpus, query, k)
