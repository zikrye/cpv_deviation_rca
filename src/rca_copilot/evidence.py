"""Evidence cards (Phase 6).

Turns scored evidence records into compact, citable cards for the UI. Every card
carries its source record ID so each claim is traceable.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from rca_copilot.scoring import score_evidence
from rca_copilot.data.synthetic import Dataset

_TYPE_LABEL = {
    "change_control": "Change Control",
    "process_signal": "Process Signal",
    "deviation": "Deviation",
    "assay_investigation": "Assay Investigation",
    "capa": "CAPA",
}


@dataclass(frozen=True)
class EvidenceCard:
    record_id: str
    record_type: str
    type_label: str
    date: str
    batch_id: str | None
    category: str
    subcategory: str
    outcome: str | None
    title: str
    score: float

    @property
    def citation(self) -> str:
        return f"[{self.record_id}]"


def evidence_for(dataset: Dataset, category: str, subcategory: str) -> list[EvidenceCard]:
    """Return evidence cards for one fishbone branch, highest score first."""
    ev = score_evidence(dataset)
    sub = ev[(ev["category"] == category) & (ev["subcategory"] == subcategory)]
    sub = sub.sort_values("score", ascending=False)

    cards: list[EvidenceCard] = []
    for _, r in sub.iterrows():
        date = r["date"]
        cards.append(
            EvidenceCard(
                record_id=r["record_id"],
                record_type=r["record_type"],
                type_label=_TYPE_LABEL.get(r["record_type"], r["record_type"]),
                date="" if pd.isna(date) else pd.Timestamp(date).date().isoformat(),
                batch_id=r.get("batch_id") if pd.notna(r.get("batch_id")) else None,
                category=r["category"],
                subcategory=r["subcategory"],
                outcome=r.get("outcome"),
                title=r["title"],
                score=round(float(r["score"]), 2),
            )
        )
    return cards
