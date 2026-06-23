"""Tests for fishbone scoring + compliance guardrails (Phases 5, 8)."""

import pytest

from rca_copilot.cpv import compute_control_limits
from rca_copilot.data.synthetic import load_dataset
from rca_copilot.llm import BANNED_PHRASES, draft_summary
from rca_copilot.scoring import score_fishbone
from rca_copilot.signals import detect_low_titer_signals


def test_material_media_is_top_candidate():
    """The curated story should surface Material → media/feed lot as #1."""
    fb = score_fishbone(load_dataset())
    top = fb.iloc[0]
    assert top["category"] == "Material (Raw Materials)"
    assert top["subcategory"] == "Cell culture media / feed lot"
    assert top["priority"] == "High"


def test_cleared_assay_ranks_below_implicating_evidence():
    """The titer-assay branch was cleared, so it must not outrank Material."""
    fb = score_fishbone(load_dataset())
    scores = {(r.category, r.subcategory): r.score for r in fb.itertuples()}
    material = scores[("Material (Raw Materials)", "Cell culture media / feed lot")]
    assay = scores.get(("Measurement (Analytical)", "Titer assay (HPLC)"), 0.0)
    assert material > assay


def test_every_branch_cites_source_ids():
    fb = score_fishbone(load_dataset())
    assert (fb["source_ids"].str.len() > 0).all()


def test_summary_is_compliant_and_cites_sources():
    ds = load_dataset()
    limits = compute_control_limits(ds.batches)
    signals = detect_low_titer_signals(ds.batches, limits)
    text = draft_summary(ds, signals, score_fishbone(ds))

    low = text.lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in low
    assert "requires sme / qa review" in low
    assert "candidate cause" in low
    assert "CC-2025-014" in text  # the key change-control source is cited


def test_summary_rejects_banned_content(monkeypatch):
    """The guardrail must raise if a banned phrase ever slips in."""
    from rca_copilot import llm

    def _bad(*a, **k):
        return "The root cause is the media lot. requires SME / QA review."

    monkeypatch.setattr(llm, "draft_summary", _bad)
    # Direct guardrail check:
    with pytest.raises(ValueError):
        llm._assert_compliant("AI determines root cause. requires SME / QA review.")
