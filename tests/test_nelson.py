"""Tests for Nelson rule detection (rules 1-3)."""

from rca_copilot.cpv import compute_control_limits, summarize_violations
from rca_copilot.data.synthetic import AFFECTED_BATCHES, load_dataset
from rca_copilot.nelson import detect_nelson


def test_rule1_flags_points_beyond_3sigma():
    # mean 0, sigma 1 -> anything with |x| > 3 violates rule 1.
    res = detect_nelson([0, 0.5, -2.9, 3.5, -4.0], mean=0.0, sigma=1.0)
    assert res.violations[1] == {3, 4}
    assert res.violations[2] == set()
    assert res.violations[3] == set()


def test_rule2_flags_nine_in_a_row_same_side():
    values = [1] * 9 + [-1]  # nine points above the mean of 0
    res = detect_nelson(values, mean=0.0, sigma=10.0)  # large sigma -> no rule 1
    assert res.violations[2] == set(range(9))
    assert res.violations[1] == set()


def test_rule2_run_of_eight_does_not_trigger():
    values = [1] * 8 + [-1]
    res = detect_nelson(values, mean=0.0, sigma=10.0)
    assert res.violations[2] == set()


def test_rule3_flags_six_monotonic_points():
    res = detect_nelson([1, 2, 3, 4, 5, 6], mean=10.0, sigma=100.0)
    assert res.violations[3] == {0, 1, 2, 3, 4, 5}


def test_rule3_break_on_equal_value():
    # 5 increasing then a flat step -> no run of 6.
    res = detect_nelson([1, 2, 3, 4, 5, 5], mean=10.0, sigma=100.0)
    assert res.violations[3] == set()


def test_demo_data_flags_affected_batches_as_rule1():
    ds = load_dataset()
    limits = compute_control_limits(ds.batches)
    summary = summarize_violations(ds.batches, limits)
    assert set(summary["batch_id"]) == set(AFFECTED_BATCHES)
    assert all("Rule 1" in r for r in summary["rules"])
