"""Nelson rule detection for control charts.

Implements the first three Nelson rules — the ones that matter for a single-batch
low-titer excursion story:

  * Rule 1 — one point beyond 3σ from the mean (outside the control limits).
  * Rule 2 — nine points in a row on the same side of the mean (sustained shift).
  * Rule 3 — six points in a row steadily increasing or decreasing (a trend).

Detection is on the time-ordered value series using the *baseline* mean and σ
(the same statistics that set the CPV control limits). Points exactly on the
mean break a Rule-2 run; equal consecutive values break a Rule-3 run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

RULE_DESCRIPTIONS: dict[int, str] = {
    1: "1 point beyond 3σ (outside control limits)",
    2: "9 points in a row on one side of the mean (shift)",
    3: "6 points in a row steadily increasing or decreasing (trend)",
}

# Run-length thresholds per rule (standard Nelson values).
_RULE2_RUN = 9
_RULE3_RUN = 6


@dataclass(frozen=True)
class NelsonResult:
    """Violations keyed by rule number -> set of point indices (time order)."""

    violations: dict[int, set[int]] = field(default_factory=dict)

    def rules_for(self, idx: int) -> list[int]:
        """Rule numbers violated at point ``idx``, ascending."""
        return sorted(r for r, idxs in self.violations.items() if idx in idxs)

    def violating_indices(self) -> list[int]:
        """All point indices that violate at least one rule, ascending."""
        out: set[int] = set()
        for idxs in self.violations.values():
            out |= idxs
        return sorted(out)

    def any(self) -> bool:
        return any(self.violations.values())


def _rule1(values: Sequence[float], mean: float, sigma: float) -> set[int]:
    if sigma <= 0:
        return set()
    limit = 3 * sigma
    return {i for i, v in enumerate(values) if abs(v - mean) > limit}


def _rule2(values: Sequence[float], mean: float) -> set[int]:
    """Runs of >= 9 consecutive points on the same side of the mean."""
    sides = [1 if v > mean else (-1 if v < mean else 0) for v in values]
    out: set[int] = set()
    n, i = len(values), 0
    while i < n:
        if sides[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and sides[j + 1] == sides[i]:
            j += 1
        if j - i + 1 >= _RULE2_RUN:
            out.update(range(i, j + 1))
        i = j + 1
    return out


def _rule3(values: Sequence[float]) -> set[int]:
    """Runs of >= 6 consecutive strictly increasing or decreasing points."""
    out: set[int] = set()
    n, i = len(values), 0
    while i < n - 1:
        if values[i + 1] > values[i]:
            direction = 1
        elif values[i + 1] < values[i]:
            direction = -1
        else:
            i += 1
            continue
        j = i
        while j + 1 < n and (
            (direction == 1 and values[j + 1] > values[j])
            or (direction == -1 and values[j + 1] < values[j])
        ):
            j += 1
        if j - i + 1 >= _RULE3_RUN:
            out.update(range(i, j + 1))
        i = j  # resume from the end of this monotonic run
    return out


def detect_nelson(
    values: Sequence[float],
    mean: float,
    sigma: float,
    rules: Iterable[int] = (1, 2, 3),
) -> NelsonResult:
    """Detect Nelson rule violations on a time-ordered value series."""
    rules = set(rules)
    violations: dict[int, set[int]] = {}
    if 1 in rules:
        violations[1] = _rule1(values, mean, sigma)
    if 2 in rules:
        violations[2] = _rule2(values, mean)
    if 3 in rules:
        violations[3] = _rule3(values)
    return NelsonResult(violations=violations)
