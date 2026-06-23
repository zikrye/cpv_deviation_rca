"""Rule-based fishbone scoring (Phase 5).

Transparent, deterministic weighting — every priority is a sum of citable
evidence records, never a black box. Score components:

  record score = base_weight x severity_mult x proximity x outcome_factor

  * base_weight   - per record type (change control > process signal > deviation ...)
  * severity_mult - deviation severity (Critical 2.0 / Major 1.5 / Minor 1.0)
  * proximity     - 1.5 if the record references an affected batch or falls within
                    the excursion window, else 1.0 (recency / relevance)
  * outcome_factor- assay investigations with outcome "Cleared" are down-weighted
                    (x0.4): they tend to *exonerate* their branch rather than
                    implicate it.

The output is an "evidence-based priority", explicitly NOT a confirmed root
cause. Final determination requires SME / QA review.
"""

from __future__ import annotations

import pandas as pd

from rca_copilot.data.synthetic import AFFECTED_BATCHES, Dataset
from rca_copilot.fishbone import FISHBONE

PROXIMITY_BONUS = 1.5
CLEARED_FACTOR = 0.4


def _proximity(row: pd.Series, window: tuple[pd.Timestamp, pd.Timestamp] | None) -> float:
    if row.get("batch_id") in AFFECTED_BATCHES:
        return PROXIMITY_BONUS
    date = row.get("date")
    if window is not None and pd.notna(date) and window[0] <= date <= window[1]:
        return PROXIMITY_BONUS
    return 1.0


def _outcome_factor(row: pd.Series) -> float:
    if row.get("record_type") == "assay_investigation" and row.get("outcome") == "Cleared":
        return CLEARED_FACTOR
    return 1.0


def score_evidence(dataset: Dataset) -> pd.DataFrame:
    """Add a per-record `score` column to the normalized evidence table."""
    ev = dataset.evidence.copy()

    # Excursion window: a 60-day lookback before the earliest affected batch
    # through the latest affected batch — captures the media changeover etc.
    affected = dataset.batches[dataset.batches.batch_id.isin(AFFECTED_BATCHES)]["date"]
    window = None
    if not affected.empty:
        window = (affected.min() - pd.Timedelta(days=60), affected.max() + pd.Timedelta(days=7))

    ev["proximity"] = ev.apply(lambda r: _proximity(r, window), axis=1)
    ev["outcome_factor"] = ev.apply(_outcome_factor, axis=1)
    ev["score"] = (
        ev["base_weight"] * ev["severity_mult"] * ev["proximity"] * ev["outcome_factor"]
    ).round(3)
    return ev


def score_fishbone(dataset: Dataset) -> pd.DataFrame:
    """Aggregate evidence into per-subcategory priorities.

    Returns one row per (category, subcategory) that has supporting evidence,
    sorted by score descending. Columns: category, subcategory, score,
    evidence_count, source_ids, priority (High/Medium/Low rank).
    """
    ev = score_evidence(dataset)
    valid_subs = {(c, s) for c, subs in FISHBONE.items() for s in subs}

    grouped = (
        ev.groupby(["category", "subcategory"])
        .agg(
            score=("score", "sum"),
            evidence_count=("record_id", "count"),
            source_ids=("record_id", lambda s: ", ".join(sorted(s))),
        )
        .reset_index()
    )
    # Keep only branches that exist in the fishbone schema.
    grouped = grouped[
        grouped.apply(lambda r: (r["category"], r["subcategory"]) in valid_subs, axis=1)
    ]
    grouped["score"] = grouped["score"].round(2)
    grouped = grouped.sort_values("score", ascending=False).reset_index(drop=True)

    # Tertile-ish priority label for the UI.
    def _label(rank: int, total: int) -> str:
        if rank == 0:
            return "High"
        if rank < max(2, total // 3):
            return "Medium"
        return "Low"

    grouped["priority"] = [
        _label(i, len(grouped)) for i in range(len(grouped))
    ]
    return grouped


def category_rollup(fishbone_scores: pd.DataFrame) -> pd.DataFrame:
    """Roll subcategory scores up to category level for the headline chart."""
    return (
        fishbone_scores.groupby("category")
        .agg(score=("score", "sum"), evidence_count=("evidence_count", "sum"))
        .reset_index()
        .sort_values("score", ascending=False)
        .reset_index(drop=True)
    )
