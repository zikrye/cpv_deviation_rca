"""Deterministic signal detection (Phase 3).

A plain rule engine — no ML, no LLM. A batch raises a signal when the charted
metric is out-of-spec (beyond LSL/USL) or out-of-trend (beyond a control limit).
The rules are explicit and auditable, the point in a GMP-adjacent context.

Detection is metric-aware: the metric and its conventions ride on
``limits.spec``. Comparisons happen in the metric's charting space (log10 for
titer, linear for pH/osmolality), but ``Signal.value``/``threshold`` and the
human-readable text are reported in natural units.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from rca_copilot.cpv import ControlLimits, chart_value, natural_value


@dataclass(frozen=True)
class Signal:
    batch_id: str
    metric: str
    value: float
    rule: str  # "OOS" or "OOT"
    threshold: float
    description: str

    @property
    def severity(self) -> str:
        return "OOS (out-of-spec)" if self.rule == "OOS" else "OOT (out-of-trend)"


def detect_signals(batches: pd.DataFrame, limits: ControlLimits) -> list[Signal]:
    """Return one signal per batch breaching a spec (OOS) or control (OOT) limit.

    Spec limits take priority over control limits; both sides are checked so a
    high osmolality flags just like a low titer.
    """
    spec = limits.spec
    unit = f" {spec.unit}" if spec.unit else ""
    signals: list[Signal] = []
    for _, row in batches.sort_values("date").iterrows():
        value = float(row[spec.column])
        cv = chart_value(value, spec)

        rule = limit_cv = side = limit_name = None
        if limits.lsl is not None and cv < limits.lsl:
            rule, limit_cv, side, limit_name = "OOS", limits.lsl, "below", "lower spec limit"
        elif limits.usl is not None and cv > limits.usl:
            rule, limit_cv, side, limit_name = "OOS", limits.usl, "above", "upper spec limit"
        elif cv < limits.lcl:
            rule, limit_cv, side, limit_name = "OOT", limits.lcl, "below", "lower control limit"
        elif cv > limits.ucl:
            rule, limit_cv, side, limit_name = "OOT", limits.ucl, "above", "upper control limit"
        else:
            continue

        threshold = natural_value(limit_cv, spec)
        signals.append(
            Signal(
                batch_id=row["batch_id"], metric=spec.column, value=value, rule=rule,
                threshold=threshold,
                description=(
                    f"{spec.label} {value:{spec.fmt}}{unit} {side} {limit_name} "
                    f"{threshold:{spec.fmt}}{unit}."
                ),
            )
        )
    return signals


def detect_low_titer_signals(batches: pd.DataFrame, limits: ControlLimits) -> list[Signal]:
    """Backward-compatible alias — works for any metric carried by ``limits``."""
    return detect_signals(batches, limits)
