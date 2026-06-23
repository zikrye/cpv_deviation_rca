"""Tests for CPV limits + deterministic signal detection (Phases 2-3)."""

from rca_copilot.cpv import compute_control_limits
from rca_copilot.data.synthetic import AFFECTED_BATCHES, LSL_TITER, load_dataset
from rca_copilot.signals import detect_low_titer_signals


def test_control_limits_from_baseline_are_in_control():
    ds = load_dataset()
    limits = compute_control_limits(ds.batches)
    # Baseline mean should sit near the 5.0 g/L target, well above the LSL.
    assert 4.5 < limits.mean < 5.5
    assert limits.lcl > LSL_TITER  # in-control LCL sits above the spec floor


def test_only_affected_batches_signal():
    ds = load_dataset()
    limits = compute_control_limits(ds.batches)
    signals = detect_low_titer_signals(ds.batches, limits)
    flagged = {s.batch_id for s in signals}
    assert flagged == set(AFFECTED_BATCHES)


def test_low_titer_is_out_of_spec():
    ds = load_dataset()
    limits = compute_control_limits(ds.batches)
    signals = {s.batch_id: s for s in detect_low_titer_signals(ds.batches, limits)}
    # Both affected batches are below the lower spec limit -> OOS.
    assert signals["XX0007"].rule == "OOS"
    assert signals["XX0007"].value < LSL_TITER
