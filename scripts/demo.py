"""Headless walkthrough of the full pipeline (Phase 9 / demo script).

Runs Phases 1-8 in the terminal without Streamlit — handy for the interview
talk-track and for sanity-checking the data story.

    python scripts/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rca_copilot.cpv import compute_control_limits
from rca_copilot.data.synthetic import load_dataset
from rca_copilot.llm import draft_summary
from rca_copilot.scoring import score_fishbone
from rca_copilot.signals import detect_low_titer_signals


def main() -> None:
    ds = load_dataset()
    limits = compute_control_limits(ds.batches)
    print(f"CPV limits: mean={limits.mean}  LCL={limits.lcl}  LSL={limits.lsl}\n")

    signals = detect_low_titer_signals(ds.batches, limits)
    print("Signals:")
    for s in signals:
        print(f"  - {s.batch_id}: {s.severity} — {s.description}")

    print("\nFishbone priorities (evidence-based):")
    fb = score_fishbone(ds)
    for _, r in fb.head(5).iterrows():
        print(f"  [{r['priority']:>6}] {r['score']:>5.2f}  "
              f"{r['category']} → {r['subcategory']}  ({r['source_ids']})")

    print("\n" + "=" * 70)
    print(draft_summary(ds, signals, fb))


if __name__ == "__main__":
    main()
