"""Draft investigation support summary (Phase 8).

By default this produces a *deterministic, template-based* summary built purely
from the scored evidence — no network, no model, fully reproducible for the demo.
An optional Claude-backed path can be enabled later; it must use the same
compliance framing.

Guardrails enforced here:
  * Output is always labelled a "draft investigation support summary".
  * It lists "candidate cause(s)" with "evidence-based priority", never a
    confirmed root cause.
  * It always ends with "requires SME / QA review".
  * Every candidate cites source record IDs.
"""

from __future__ import annotations

import pandas as pd

from rca_copilot.data.synthetic import Dataset
from rca_copilot.signals import Signal

# Banned phrases that must never appear in any generated summary.
BANNED_PHRASES = (
    "confirmed by ai",
    "ai determines root cause",
    "ai makes batch disposition",
    "root cause is",
    "root cause confirmed",
)


def _assert_compliant(text: str) -> str:
    low = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in low:
            raise ValueError(f"Generated summary contained banned phrase: {phrase!r}")
    if "requires sme" not in low and "sme / qa review" not in low:
        raise ValueError("Generated summary missing required SME/QA review disclaimer.")
    return text


def draft_summary(
    dataset: Dataset,
    signals: list[Signal],
    fishbone_scores: pd.DataFrame,
    top_n: int = 3,
) -> str:
    """Build the deterministic draft summary (Phase 8 default path)."""
    batches = ", ".join(sorted({s.batch_id for s in signals})) or "—"
    rules = ", ".join(sorted({s.severity for s in signals})) or "—"

    lines = [
        "### Draft investigation support summary",
        "_Evidence-based priorities for investigation. Not a root cause "
        "determination. Requires SME / QA review._",
        "",
        f"**Signal:** Low harvest titer flagged on batch(es) **{batches}** "
        f"({rules}).",
        "",
        "**Candidate causes (by evidence-based priority):**",
    ]

    top = fishbone_scores.head(top_n)
    for i, (_, row) in enumerate(top.iterrows(), start=1):
        lines.append(
            f"{i}. **{row['category']} → {row['subcategory']}** "
            f"(priority: {row['priority']}, score {row['score']:.2f}, "
            f"{row['evidence_count']} record(s)). "
            f"Sources: {row['source_ids']}."
        )

    lines += [
        "",
        "**Suggested next steps for the investigation team:**",
        "- Review the cited source records above with process SMEs.",
        "- Confirm or rule out each candidate cause through the formal "
        "deviation/CAPA process.",
        "",
        "_This is an investigation support draft only and **requires SME / QA "
        "review**. The tool does not confirm root cause or make batch "
        "disposition decisions._",
    ]
    return _assert_compliant("\n".join(lines))


def draft_summary_llm(*args, **kwargs) -> str:  # pragma: no cover - optional path
    """Optional Claude-backed summary (Phase 8, not enabled by default).

    Intended implementation: pass the scored evidence + retrieved snippets to
    Claude with a system prompt that enforces the same compliance framing, then
    run the result through `_assert_compliant`. Falls back to the deterministic
    summary until wired up.
    """
    return draft_summary(*args, **kwargs)
