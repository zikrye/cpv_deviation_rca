"""Continued Process Verification (CPV) charting (Phase 2).

Control limits are established from an in-control *baseline* set of batches (not
the full series) so the excursion batches do not inflate the limits — this is
how a real CPV control chart is run.

The chart is metric-aware via :class:`MetricSpec`. Infectious titer is
log-normally distributed, so titer is charted and limited in **log10 PFU/mL**
(the convention for plaque/TCID50 control charts) — limits are symmetric in log
space and the Nelson rules operate on the log10 series — with a one-sided lower
spec (low titer is the failure). pH and osmolality are charted on a **linear**
scale with **two-sided** spec limits (pH can drift either way; osmolality drifts
high). The underlying batch data always stays in natural linear units; only this
module transforms it. A ``ControlLimits`` carries its ``MetricSpec`` plus limit
values in that metric's charting space (log10 for titer, linear otherwise); use
:func:`natural_value` / :func:`to_linear` to recover natural units for copy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from rca_copilot.data.synthetic import BASELINE_BATCHES, LSL_TITER
from rca_copilot.nelson import RULE_DESCRIPTIONS, NelsonResult, detect_nelson

METRIC = "harvest_titer_pfu_per_ml"
TITER_UNIT = "PFU/mL"


@dataclass(frozen=True)
class MetricSpec:
    """A charted CPV parameter and its display / control-chart conventions."""

    column: str
    label: str               # e.g. "Harvest titer"
    unit: str                # e.g. "PFU/mL" ("" for unitless pH)
    log_scale: bool          # chart/limits in log10 (titer) vs linear (pH, osmo)
    lsl: float | None = None  # lower spec limit, in natural units
    usl: float | None = None  # upper spec limit, in natural units
    fmt: str = ".2f"         # d3/printf format for a value in natural units
    input_step: float = 0.1  # step for the Streamlit number input


TITER_SPEC = MetricSpec(
    column=METRIC, label="Harvest titer", unit=TITER_UNIT, log_scale=True,
    lsl=LSL_TITER, fmt=".2e", input_step=1.0e4,
)
PH_SPEC = MetricSpec(
    column="ph_at_harvest", label="Harvest pH", unit="", log_scale=False,
    lsl=6.90, usl=7.10, fmt=".2f", input_step=0.01,
)
OSMO_SPEC = MetricSpec(
    column="osmolality_mosm_kg", label="Osmolality", unit="mOsm/kg", log_scale=False,
    lsl=480.0, usl=515.0, fmt=".0f", input_step=1.0,
)

#: Charted metrics keyed by their batch-table column.
METRIC_SPECS = {s.column: s for s in (TITER_SPEC, PH_SPEC, OSMO_SPEC)}


def to_linear(log10_value: float) -> float:
    """Convert a log10 PFU/mL value back to linear PFU/mL (titer convenience)."""
    return 10 ** log10_value


def chart_value(value: float, spec: MetricSpec) -> float:
    """Map a natural-unit value into the metric's charting space (log10 or linear)."""
    return math.log10(value) if spec.log_scale else value


def natural_value(chart_v: float, spec: MetricSpec) -> float:
    """Inverse of :func:`chart_value`: charting space back to natural units."""
    return 10 ** chart_v if spec.log_scale else chart_v


def _chart_series(batches: pd.DataFrame, spec: MetricSpec) -> pd.Series:
    """The metric column mapped into charting space, index-aligned to ``batches``."""
    s = batches[spec.column].astype(float)
    return np.log10(s) if spec.log_scale else s


@dataclass(frozen=True)
class ControlLimits:
    """Control + spec limits in the metric's charting space (see ``spec``)."""

    mean: float
    sigma: float
    ucl: float  # mean + 3 sigma
    lcl: float  # mean - 3 sigma
    lsl: float | None  # lower spec limit (None if not specified)
    usl: float | None  # upper spec limit (None if not specified)
    spec: MetricSpec


def compute_control_limits(
    batches: pd.DataFrame,
    spec: MetricSpec = TITER_SPEC,
    baseline: list[str] | None = None,
) -> ControlLimits:
    baseline = baseline or BASELINE_BATCHES
    base = _chart_series(batches[batches["batch_id"].isin(baseline)], spec)
    mean = float(base.mean())
    sigma = float(base.std(ddof=1))

    def _spec_limit(v: float | None) -> float | None:
        return None if v is None else round(chart_value(v, spec), 3)

    return ControlLimits(
        mean=round(mean, 3),
        sigma=round(sigma, 3),
        ucl=round(mean + 3 * sigma, 3),
        lcl=round(mean - 3 * sigma, 3),
        lsl=_spec_limit(spec.lsl),
        usl=_spec_limit(spec.usl),
        spec=spec,
    )


def detect_violations(batches: pd.DataFrame, limits: ControlLimits) -> NelsonResult:
    """Nelson rule 1/2/3 violations on the time-ordered (charting-space) series."""
    b = batches.sort_values("date")
    return detect_nelson(_chart_series(b, limits.spec).tolist(), limits.mean, limits.sigma)


def summarize_violations(batches: pd.DataFrame, limits: ControlLimits) -> pd.DataFrame:
    """One row per violating batch: batch_id, value, rules, descriptions.

    Useful for rendering a textual call-out alongside the chart.
    """
    b = batches.sort_values("date").reset_index(drop=True)
    res = detect_violations(batches, limits)
    rows = []
    for i in res.violating_indices():
        rules = res.rules_for(i)
        rows.append(
            {
                "batch_id": b.loc[i, "batch_id"],
                "value": round(float(b.loc[i, limits.spec.column]), 2),
                "rules": ", ".join(f"Rule {r}" for r in rules),
                "description": "; ".join(RULE_DESCRIPTIONS[r] for r in rules),
            }
        )
    return pd.DataFrame(rows, columns=["batch_id", "value", "rules", "description"])


def cpv_chart(batches: pd.DataFrame, limits: ControlLimits) -> go.Figure:
    """Run chart of the metric carried by ``limits`` with control/spec limits.

    Titer is plotted in log10; pH/osmolality on a linear scale. Points violating
    Nelson rule 1/2/3 are ringed in red and tagged with their rule numbers (e.g.
    ``R1`` or ``R1,R3``); hover shows the rule descriptions.
    """
    spec = limits.spec
    b = batches.sort_values("date").reset_index(drop=True)
    res = detect_violations(batches, limits)
    y = _chart_series(b, spec).tolist()                 # charting space
    natural = b[spec.column].astype(float).tolist()     # natural units (hover)
    dates = [pd.Timestamp(d).strftime("%d-%b-%Y") for d in b["date"]]  # fill date
    unit_sfx = f" {spec.unit}" if spec.unit else ""

    # customdata columns — main: [natural, date]; violation: [natural, desc, date].
    if spec.log_scale:
        main_hover = (
            f"%{{x}}<br>{spec.label}: %{{y:.3f}} log₁₀ {spec.unit} "
            f"(%{{customdata[0]:{spec.fmt}}} {spec.unit})"
            "<br>Fill date: %{customdata[1]}<extra></extra>"
        )
        viol_hover = (
            f"%{{x}}: %{{y:.3f}} log₁₀ (%{{customdata[0]:{spec.fmt}}} {spec.unit})"
            "<br>Fill date: %{customdata[2]}"
            "<br>%{customdata[1]}<extra>Nelson</extra>"
        )
    else:
        main_hover = (
            f"%{{x}}<br>{spec.label}: %{{y:{spec.fmt}}}{unit_sfx}"
            "<br>Fill date: %{customdata[1]}<extra></extra>"
        )
        viol_hover = (
            f"%{{x}}: %{{y:{spec.fmt}}}{unit_sfx}"
            "<br>Fill date: %{customdata[2]}"
            "<br>%{customdata[1]}<extra>Nelson</extra>"
        )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=b["batch_id"],
            y=y,
            mode="lines+markers",
            name=spec.label,
            marker=dict(size=10, color="#1f77b4"),
            line=dict(color="#1f77b4"),
            customdata=[[natural[i], dates[i]] for i in range(len(b))],
            hovertemplate=main_hover,
        )
    )

    vidx = res.violating_indices()
    if vidx:
        fig.add_trace(
            go.Scatter(
                x=[b.loc[i, "batch_id"] for i in vidx],
                y=[y[i] for i in vidx],
                mode="markers+text",
                name="Nelson rule violation",
                marker=dict(
                    size=18, symbol="circle-open",
                    line=dict(color="#d62728", width=3), color="#d62728",
                ),
                text=[",".join(f"R{r}" for r in res.rules_for(i)) for i in vidx],
                textposition="bottom center",
                textfont=dict(color="#d62728", size=12),
                customdata=[
                    [natural[i],
                     "<br>".join(RULE_DESCRIPTIONS[r] for r in res.rules_for(i)),
                     dates[i]]
                    for i in vidx
                ],
                hovertemplate=viol_hover,
            )
        )

    def _hline(yv: float, label: str, dash: str, color: str) -> None:
        fig.add_hline(y=yv, line_dash=dash, line_color=color,
                      annotation_text=label, annotation_position="right")

    def _lbl(name: str, chart_v: float) -> str:
        if spec.log_scale:
            return f"{name} {chart_v:.2f} ({natural_value(chart_v, spec):.1e})"
        return f"{name} {natural_value(chart_v, spec):{spec.fmt}}{unit_sfx}"

    _hline(limits.mean, _lbl("Mean", limits.mean), "solid", "#2ca02c")
    _hline(limits.ucl, _lbl("UCL", limits.ucl), "dash", "#7f7f7f")
    _hline(limits.lcl, _lbl("LCL", limits.lcl), "dash", "#7f7f7f")
    if limits.lsl is not None:
        _hline(limits.lsl, _lbl("LSL", limits.lsl), "dot", "#d62728")
    if limits.usl is not None:
        _hline(limits.usl, _lbl("USL", limits.usl), "dot", "#d62728")

    if spec.log_scale:
        yaxis_title = f"{spec.label} (log₁₀ {spec.unit})"
        tickformat = ".2f"
    else:
        yaxis_title = f"{spec.label}{(' (' + spec.unit + ')') if spec.unit else ''}"
        tickformat = spec.fmt

    fig.update_layout(
        title=f"CPV — {spec.label} by Batch (synthetic)",
        xaxis_title="Batch",
        yaxis_title=yaxis_title,
        yaxis_tickformat=tickformat,
        height=440,
        margin=dict(l=40, r=150, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
