"""Biotech Deviation RCA Copilot — Streamlit demo entry point.

Run with:  streamlit run app/streamlit_app.py

Investigation support tool only. Synthetic data only. Does not determine final
root cause or make batch disposition decisions.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make `src/` importable when run via `streamlit run app/streamlit_app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import streamlit as st
import streamlit.components.v1 as components

from rca_copilot import DISCLAIMER
from rca_copilot.cpv import (
    METRIC,
    TITER_UNIT,
    compute_control_limits,
    cpv_chart,
    summarize_violations,
    to_linear,
)
from rca_copilot.data.synthetic import AFFECTED_BATCHES, load_dataset
from rca_copilot.nelson import RULE_DESCRIPTIONS
from rca_copilot.evidence import evidence_for
from rca_copilot.llm import draft_summary
from rca_copilot.scoring import score_fishbone
from rca_copilot.signals import detect_low_titer_signals
from rca_copilot.viz import fishbone_svg_html

st.set_page_config(page_title="Deviation RCA Copilot", page_icon="🧪", layout="wide")

TITER_TEST = "Titer (plaque assay, PFU/mL)"

#: Test label -> (batch column, display unit, number_input step, printf format).
TEST_SPECS = {
    TITER_TEST: (METRIC, TITER_UNIT, 1.0e4, "%.0f"),
    "pH": ("ph_at_harvest", "", 0.01, "%.2f"),
    "Osmolality": ("osmolality_mosm_kg", "mOsm/kg", 1.0, "%.0f"),
}
TESTS = list(TEST_SPECS)


def _fmt_result(test: str, value: float) -> str:
    """Format a result with the right precision/unit for its test."""
    unit = TEST_SPECS[test][1]
    if test == TITER_TEST:
        return f"{value:.2e} {unit}"
    if test == "Osmolality":
        return f"{value:.0f} {unit}"
    return f"{value:.2f}"


@st.cache_data
def _load():
    """Input-independent data: the synthetic dataset + evidence-based fishbone."""
    ds = load_dataset()
    fb = score_fishbone(ds)
    # Established control limits come from the in-control baseline history; they
    # are NOT recomputed when a new record arrives.
    limits = compute_control_limits(ds.batches)
    return ds, fb, limits


dataset, fb_scores, limits = _load()
batch_opts = dataset.batches.sort_values("date")["batch_id"].tolist()
_batch_rows = dataset.batches.set_index("batch_id")


def _recorded(batch_id: str, test: str) -> float:
    """Recorded value for a batch's selected test parameter (0.0 if unknown)."""
    col = TEST_SPECS[test][0]
    if batch_id in _batch_rows.index:
        return float(_batch_rows.loc[batch_id, col])
    return 0.0


# --- Sidebar: incoming deviation trigger ------------------------------------
if "dev_batch" not in st.session_state:
    st.session_state.dev_batch = AFFECTED_BATCHES[0]  # XX0007
    st.session_state.dev_test = TITER_TEST
    st.session_state.dev_result = _recorded(AFFECTED_BATCHES[0], TITER_TEST)


def _sync_result() -> None:
    """Prefill the result with the batch's recorded value for the chosen test."""
    st.session_state.dev_result = _recorded(
        st.session_state.dev_batch, st.session_state.dev_test
    )


with st.sidebar:
    st.header("Incoming deviation")
    st.caption("Simulates a LIMS/QMS record arriving for triage.")
    st.selectbox("Batch ID", batch_opts, key="dev_batch", on_change=_sync_result)
    st.selectbox("Test", TESTS, key="dev_test", on_change=_sync_result)
    _step, _fmt = TEST_SPECS[st.session_state.dev_test][2:]
    st.number_input("Result", key="dev_result", step=_step, format=_fmt)
    run = st.button("▶ Run RCA analysis", type="primary", use_container_width=True)
    st.caption(
        f"Spec floor (LSL) on titer: {to_linear(limits.lsl):.2e} {TITER_UNIT} "
        f"(log₁₀ {limits.lsl:.2f}). CPV is charted in log₁₀ PFU/mL."
    )

if run:
    st.session_state.rca = {
        "batch": st.session_state.dev_batch,
        "test": st.session_state.dev_test,
        "result": float(st.session_state.dev_result),
    }

# --- Header -----------------------------------------------------------------
st.title("🧪 Biotech Deviation RCA Copilot")
st.caption("CPV-triggered, AI-assisted fishbone RCA support — demo")
st.warning(DISCLAIMER, icon="⚠️")

rca = st.session_state.get("rca")
if not rca:
    st.info(
        "👈 Enter an incoming deviation in the sidebar and click "
        "**▶ Run RCA analysis** to triage it.",
        icon="🧫",
    )
    st.stop()

# Make the run feel like a triggered agent workflow.
if run:
    with st.spinner(
        "Triaging deviation — retrieving historical deviations, CAPAs, change "
        "controls and scoring fishbone…"
    ):
        time.sleep(1.1)

# Apply the incoming record to the series (only the titer test is modeled here).
is_titer = rca["test"] == TITER_TEST
batches = dataset.batches.copy()
if is_titer:
    batches.loc[batches["batch_id"] == rca["batch"], METRIC] = rca["result"]
signals = detect_low_titer_signals(batches, limits)

# --- Incoming record summary ------------------------------------------------
with st.container(border=True):
    st.markdown("#### Incoming deviation record")
    c1, c2, c3 = st.columns(3)
    c1.metric("Batch", rca["batch"])
    c2.metric("Test", rca["test"])
    c3.metric("Result", _fmt_result(rca["test"], rca["result"]))
    if not is_titer:
        st.caption(
            f"This CPV demo models titer only; '{rca['test']}' is recorded but the "
            "chart/signal below reflect the recorded harvest titer."
        )

# Gate: no signal -> no investigation triggered.
flagged = {s.batch_id: s for s in signals}
if rca["batch"] not in flagged and not signals:
    st.success(
        f"No deviation signal for {rca['batch']} at "
        f"{_fmt_result(rca['test'], rca['result'])} — "
        "result is within control/spec limits. No RCA triggered.",
        icon="✅",
    )
    st.stop()

# --- 1: CPV chart -----------------------------------------------------------
st.subheader("1 · Continued Process Verification (CPV)")
st.plotly_chart(cpv_chart(batches, limits), use_container_width=True)

nelson = summarize_violations(batches, limits)
if not nelson.empty:
    tags = ", ".join(f"{r.batch_id} ({r.rules})" for r in nelson.itertuples())
    st.markdown(f"**Nelson rule violations:** {tags}")
    with st.expander("What do the labels mean?"):
        for rule, desc in RULE_DESCRIPTIONS.items():
            st.markdown(f"- **R{rule}** — {desc}")
else:
    st.caption("No Nelson rule (1–3) violations detected.")

# --- 2: Deterministic signal ------------------------------------------------
st.subheader("2 · Deterministic deviation signal")
if rca["batch"] in flagged:
    s = flagged[rca["batch"]]
    st.error(f"**{s.batch_id} — {s.severity}**: {s.description}", icon="🚨")
else:
    st.success(
        f"{rca['batch']} is within limits — no low-titer signal for this record.",
        icon="✅",
    )
others = [s for s in signals if s.batch_id != rca["batch"]]
if others:
    with st.expander(f"Other flagged batches in the campaign ({len(others)})"):
        for s in others:
            st.markdown(f"- **{s.batch_id} — {s.severity}**: {s.description}")
st.caption("Rule-based detection (no ML): titer < LSL ⇒ OOS; titer < LCL ⇒ OOT.")

# --- 3: Fishbone priorities -------------------------------------------------
st.subheader("3 · Fishbone — evidence-based priority")
effect = f"Low harvest titer ({rca['batch']})" if is_titer else f"{rca['test']} deviation ({rca['batch']})"
components.html(fishbone_svg_html(fb_scores, effect), height=600, scrolling=False)
with st.expander("Priority table (all scored branches)"):
    st.dataframe(
        fb_scores[["category", "subcategory", "priority", "score", "evidence_count", "source_ids"]],
        hide_index=True,
        use_container_width=True,
    )

# --- 4: Evidence cards ------------------------------------------------------
st.subheader("4 · Evidence cards (candidate cause)")
options = [f"{r.category} → {r.subcategory}" for _, r in fb_scores.iterrows()]
choice = st.selectbox("Inspect a candidate cause branch:", options)
sel_cat, sel_sub = choice.split(" → ", 1)
cards = evidence_for(dataset, sel_cat, sel_sub)

if not cards:
    st.info("No supporting records for this branch.")
for c in cards:
    with st.container(border=True):
        head = f"**{c.type_label} {c.citation}** · score {c.score:.2f}"
        meta = " · ".join(filter(None, [c.date, c.batch_id, c.outcome]))
        st.markdown(head + (f"  \n_{meta}_" if meta else ""))
        st.write(c.title)

# --- 5: Draft summary -------------------------------------------------------
st.subheader("5 · Draft investigation support summary")
st.markdown(draft_summary(dataset, signals, fb_scores))
