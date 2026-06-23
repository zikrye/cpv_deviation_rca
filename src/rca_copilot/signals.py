"""Deterministic signal detection (Phase 3).

A plain rule engine — no ML, no LLM. A batch raises a signal when its harvest
titer is out-of-spec (< LSL) or out-of-trend (< lower control limit). The rules
are explicit and auditable, which is the point in a GMP-adjacent context.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from rca_copilot.cpv import METRIC, ControlLimits


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


def detect_low_titer_signals(batches: pd.DataFrame, limits: ControlLimits) -> list[Signal]:
    """Return one signal per batch that breaches LSL or LCL (LSL takes priority)."""
    signals: list[Signal] = []
    for _, row in batches.sort_values("date").iterrows():
        value = float(row[METRIC])
        if value < limits.lsl:
            signals.append(
                Signal(
                    batch_id=row["batch_id"], metric=METRIC, value=value, rule="OOS",
                    threshold=limits.lsl,
                    description=(
                        f"Harvest titer {value:.2f} g/L below lower spec limit "
                        f"{limits.lsl:.2f} g/L."
                    ),
                )
            )
        elif value < limits.lcl:
            signals.append(
                Signal(
                    batch_id=row["batch_id"], metric=METRIC, value=value, rule="OOT",
                    threshold=limits.lcl,
                    description=(
                        f"Harvest titer {value:.2f} g/L below lower control limit "
                        f"{limits.lcl:.2f} g/L."
                    ),
                )
            )
    return signals
