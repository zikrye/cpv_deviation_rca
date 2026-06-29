"""Deterministic signal detection (Phase 3).

A plain rule engine — no ML, no LLM. A batch raises a signal when its infectious
harvest titer (PFU/mL) is out-of-spec (< LSL) or out-of-trend (< lower control
limit). The rules are explicit and auditable, the point in a GMP-adjacent context.

The comparison is done in log10 space — titer is log-normal and the CPV limits
are log10 PFU/mL (see ``cpv``) — but ``Signal.value``/``threshold`` and the
human-readable text are reported in linear PFU/mL.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from rca_copilot.cpv import METRIC, ControlLimits, to_linear


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
        log_value = math.log10(value)
        if log_value < limits.lsl:
            signals.append(
                Signal(
                    batch_id=row["batch_id"], metric=METRIC, value=value, rule="OOS",
                    threshold=to_linear(limits.lsl),
                    description=(
                        f"Harvest titer {value:.2e} PFU/mL below lower spec limit "
                        f"{to_linear(limits.lsl):.2e} PFU/mL."
                    ),
                )
            )
        elif log_value < limits.lcl:
            signals.append(
                Signal(
                    batch_id=row["batch_id"], metric=METRIC, value=value, rule="OOT",
                    threshold=to_linear(limits.lcl),
                    description=(
                        f"Harvest titer {value:.2e} PFU/mL below lower control limit "
                        f"{to_linear(limits.lcl):.2e} PFU/mL."
                    ),
                )
            )
    return signals
