"""Continued Process Verification (CPV) charting (Phase 2).

Control limits are established from an in-control *baseline* set of batches (not
the full series) so the excursion batches do not inflate the limits — this is
how a real CPV control chart is run.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from rca_copilot.data.synthetic import BASELINE_BATCHES, LSL_TITER
from rca_copilot.nelson import RULE_DESCRIPTIONS, NelsonResult, detect_nelson

METRIC = "harvest_titer_g_per_l"


@dataclass(frozen=True)
class ControlLimits:
    mean: float
    sigma: float
    ucl: float  # mean + 3 sigma
    lcl: float  # mean - 3 sigma
    lsl: float  # lower spec limit


def compute_control_limits(
    batches: pd.DataFrame, baseline: list[str] | None = None
) -> ControlLimits:
    baseline = baseline or BASELINE_BATCHES
    base = batches[batches["batch_id"].isin(baseline)][METRIC]
    mean = float(base.mean())
    sigma = float(base.std(ddof=1))
    return ControlLimits(
        mean=round(mean, 3),
        sigma=round(sigma, 3),
        ucl=round(mean + 3 * sigma, 3),
        lcl=round(mean - 3 * sigma, 3),
        lsl=LSL_TITER,
    )


def detect_violations(batches: pd.DataFrame, limits: ControlLimits) -> NelsonResult:
    """Nelson rule 1/2/3 violations on the time-ordered titer series."""
    b = batches.sort_values("date")
    return detect_nelson(b[METRIC].tolist(), limits.mean, limits.sigma)


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
                "value": round(float(b.loc[i, METRIC]), 2),
                "rules": ", ".join(f"Rule {r}" for r in rules),
                "description": "; ".join(RULE_DESCRIPTIONS[r] for r in rules),
            }
        )
    return pd.DataFrame(rows, columns=["batch_id", "value", "rules", "description"])


def cpv_chart(batches: pd.DataFrame, limits: ControlLimits) -> go.Figure:
    """Run chart of harvest titer with control/spec limits and Nelson labels.

    Points violating Nelson rule 1/2/3 are ringed in red and tagged with their
    rule numbers (e.g. ``R1`` or ``R1,R3``); hover shows the rule descriptions.
    """
    b = batches.sort_values("date").reset_index(drop=True)
    res = detect_violations(batches, limits)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=b["batch_id"],
            y=b[METRIC],
            mode="lines+markers",
            name="Harvest titer",
            marker=dict(size=10, color="#1f77b4"),
            line=dict(color="#1f77b4"),
            hovertemplate="%{x}<br>Titer: %{y:.2f} g/L<extra></extra>",
        )
    )

    vidx = res.violating_indices()
    if vidx:
        fig.add_trace(
            go.Scatter(
                x=[b.loc[i, "batch_id"] for i in vidx],
                y=[b.loc[i, METRIC] for i in vidx],
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
                    "<br>".join(RULE_DESCRIPTIONS[r] for r in res.rules_for(i))
                    for i in vidx
                ],
                hovertemplate="%{x}: %{y:.2f} g/L<br>%{customdata}<extra>Nelson</extra>",
            )
        )

    def _hline(y: float, label: str, dash: str, color: str) -> None:
        fig.add_hline(y=y, line_dash=dash, line_color=color,
                      annotation_text=label, annotation_position="right")

    _hline(limits.mean, f"Mean {limits.mean:.2f}", "solid", "#2ca02c")
    _hline(limits.ucl, f"UCL {limits.ucl:.2f}", "dash", "#7f7f7f")
    _hline(limits.lcl, f"LCL {limits.lcl:.2f}", "dash", "#7f7f7f")
    _hline(limits.lsl, f"LSL {limits.lsl:.2f}", "dot", "#d62728")

    fig.update_layout(
        title="CPV — Harvest Titer by Batch (synthetic)",
        xaxis_title="Batch",
        yaxis_title="Harvest titer (g/L)",
        height=440,
        margin=dict(l=40, r=120, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
