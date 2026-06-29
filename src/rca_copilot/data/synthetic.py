"""Synthetic dataset for the RCA Copilot demo.

SYNTHETIC DATA ONLY. No real company, patient, GMP, batch, deviation, CAPA, or
assay data is used or represented here. Batch IDs, lot numbers and personnel are
fictional and generated for demonstration purposes.

The product is a synthetic viral vector (VV-Demo-A); the key release metric is
infectious harvest titer in PFU/mL (plaque assay), with in-process pH and
osmolality recorded per batch. Realistic scales: titer ~5e5 PFU/mL, pH ~7.0,
osmolality ~500 mOsm/kg.

The data is curated to tell one coherent investigation story:

  Batches XX0007 (Jul-2025) and XX0008 (Aug-2025) show low harvest titer. A cell
  culture media/feed lot changeover (change control CC-2025-014) landed just
  before XX0007, and several supporting records (historical deviations, an open
  CAPA, process signals and an assay investigation) cluster around the
  *Material* and *Method* fishbone categories. The Measurement records, by
  contrast, indicate the plaque titer assay itself was in control — so it should
  rank lower. The point of the demo is to *prioritize candidate causes by
  evidence*, not to confirm any of them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# --- Demo constants ---------------------------------------------------------

SEED = 42
N_BATCHES = 12
BATCH_PREFIX = "XX"
AFFECTED_BATCHES = ["XX0007", "XX0008"]

#: Lower spec limit on infectious harvest titer (PFU/mL). Below this is
#: out-of-spec (OOS); between LSL and the lower control limit is out-of-trend.
LSL_TITER = 4.0e5

#: Baseline batches used to establish CPV control limits (in-control history).
BASELINE_BATCHES = [f"{BATCH_PREFIX}000{i}" for i in range(1, 7)]  # XX0001..XX0006


@dataclass(frozen=True)
class Dataset:
    """Bundle of all synthetic tables plus the normalized evidence view."""

    batches: pd.DataFrame
    deviations: pd.DataFrame
    capas: pd.DataFrame
    change_controls: pd.DataFrame
    assay_investigations: pd.DataFrame
    process_signals: pd.DataFrame
    evidence: pd.DataFrame  # normalized union of all supporting records


# --- Generators (Phase 1) ---------------------------------------------------


def _batch_id(n: int) -> str:
    return f"{BATCH_PREFIX}{n:04d}"


def generate_batches(seed: int = SEED) -> pd.DataFrame:
    """Monthly campaign of infectious harvest titer results; XX0007/XX0008 run low.

    Titer is in PFU/mL (plaque assay, ~5e5 baseline). In-process pH (~7.0) and
    osmolality (~500 mOsm/kg) are recorded per batch; the affected batches drift
    off-target (low pH, elevated osmolality) consistent with the media-lot story.
    """
    rng = np.random.default_rng(seed)
    # Anchor on the month start so the +14d offset lands mid-month: the campaign
    # runs Jan-2025 → Dec-2025, putting XX0007 in Jul and XX0008 in Aug to match
    # the investigation story and the deviation/change-control record dates.
    dates = pd.date_range("2025-01-01", periods=N_BATCHES, freq="MS") + pd.Timedelta(days=14)

    titer = np.round(rng.normal(5.0e5, 0.22e5, N_BATCHES), -3)
    low = {"XX0007": 3.62e5, "XX0008": 3.74e5}  # the triggering excursion
    rows = []
    for i in range(1, N_BATCHES + 1):
        bid = _batch_id(i)
        rows.append(
            {
                "batch_id": bid,
                "date": dates[i - 1].normalize(),
                "product": "VV-Demo-A",
                "harvest_titer_pfu_per_ml": low.get(bid, float(titer[i - 1])),
                "ph_at_harvest": round(float(rng.normal(7.0, 0.05)), 2),
                "osmolality_mosm_kg": round(float(rng.normal(500, 8))),
                "step_yield_pct": round(float(rng.normal(78, 3)), 1),
                "viable_cell_density_e6": round(float(rng.normal(14.5, 0.8)), 1),
            }
        )
    df = pd.DataFrame(rows)
    # Keep in-control batches within the validated harvest-pH band so the only
    # batches that break trend on the pH control chart are the excursion ones.
    df["ph_at_harvest"] = df["ph_at_harvest"].clip(lower=6.95, upper=7.05)
    # Make the excursion physically consistent: low titer tracks low VCD, a
    # depressed harvest pH and elevated osmolality (the media-lot fingerprint).
    affected = df.batch_id.isin(AFFECTED_BATCHES)
    df.loc[affected, "viable_cell_density_e6"] = [11.2, 11.9]
    df.loc[affected, "step_yield_pct"] = [69.4, 71.1]
    df.loc[affected, "ph_at_harvest"] = [6.85, 6.88]
    df.loc[affected, "osmolality_mosm_kg"] = [528, 521]
    return df


def generate_deviations(seed: int = SEED) -> pd.DataFrame:
    """Historical process deviations, fictional."""
    rows = [
        # Clustered around the Material / media story (recent, on affected batches)
        ("DEV-2025-051", "2025-07-18", "XX0007", "Material (Raw Materials)",
         "Cell culture media / feed lot", "Major",
         "Low viable cell density observed in production bioreactor post media lot changeover."),
        ("DEV-2025-058", "2025-08-20", "XX0008", "Material (Raw Materials)",
         "Cell culture media / feed lot", "Major",
         "Repeat low-titer harvest on second batch using same media lot M-2301."),
        # Method category, recent
        ("DEV-2025-049", "2025-07-19", "XX0007", "Method (Process)",
         "Feed strategy", "Minor",
         "Feed bolus addition delayed ~6h vs. process setpoint on day 7."),
        # Older / unrelated historical noise across categories
        ("DEV-2025-012", "2025-02-11", "XX0002", "Machine (Equipment)",
         "pH / DO probes", "Minor", "DO probe drift flagged during calibration check."),
        ("DEV-2025-023", "2025-03-22", "XX0003", "Measurement (Analytical)",
         "Titer assay (plaque)", "Minor", "Plaque assay miscount flagged; plate re-read by second analyst, result valid."),
        ("DEV-2025-034", "2025-05-09", "XX0005", "Man (Personnel)",
         "Shift handover", "Minor", "Incomplete shift handover note for feed schedule."),
        ("DEV-2024-118", "2024-11-30", "XX0001", "Environment (Facility)",
         "HVAC / temperature", "Minor", "Transient HVAC alarm in suite, no product impact assessed."),
    ]
    return pd.DataFrame(
        rows,
        columns=["deviation_id", "date", "batch_id", "category", "subcategory",
                 "severity", "title"],
    ).assign(date=lambda d: pd.to_datetime(d["date"]))


def generate_capas(seed: int = SEED) -> pd.DataFrame:
    """CAPA records linked to deviations, fictional."""
    rows = [
        ("CAPA-2025-019", "DEV-2025-051", "Open", "Material (Raw Materials)",
         "Cell culture media / feed lot",
         "Investigate media lot M-2301 supplier CoA and amino acid profile vs. prior lot."),
        ("CAPA-2025-007", "DEV-2025-012", "Closed", "Machine (Equipment)",
         "pH / DO probes", "Revised probe calibration frequency."),
    ]
    return pd.DataFrame(
        rows,
        columns=["capa_id", "deviation_id", "status", "category", "subcategory", "title"],
    )


def generate_change_controls(seed: int = SEED) -> pd.DataFrame:
    """Change controls, fictional. The media lot changeover is the key signal."""
    rows = [
        ("CC-2025-014", "2025-06-20", "Material (Raw Materials)",
         "Cell culture media / feed lot", "Implemented",
         "Cell culture media lot changeover (Lot M-2207 -> M-2301), new supplier sublot."),
        ("CC-2025-009", "2025-04-02", "Machine (Equipment)",
         "Chromatography skid", "Implemented",
         "Anion-exchange (AEX) chromatography skid firmware update."),
        ("CC-2025-021", "2025-09-05", "Method (Process)",
         "Harvest / clarification", "Planned",
         "Proposed depth filter train change (not yet implemented)."),
    ]
    return pd.DataFrame(
        rows,
        columns=["change_control_id", "date", "category", "subcategory", "status", "title"],
    ).assign(date=lambda d: pd.to_datetime(d["date"]))


def generate_assay_investigations(seed: int = SEED) -> pd.DataFrame:
    """Analytical / OOS-OOT assay investigations, fictional.

    The plaque titer assay investigation *clears* the assay (in control), which
    should push the Measurement category down the priority list — a realistic
    outcome that the evidence-weighting must reflect.
    """
    rows = [
        ("AINV-2025-033", "2025-07-22", "XX0007", "Titer assay (plaque)",
         "Measurement (Analytical)", "Titer assay (plaque)", "Cleared",
         "Plaque assay re-test and system suitability passed; low titer confirmed as real, not analytical."),
        ("AINV-2025-040", "2025-08-23", "XX0008", "Cell count",
         "Measurement (Analytical)", "Cell count / viability", "Cleared",
         "Cell counter cross-check within tolerance; low VCD confirmed as real."),
    ]
    return pd.DataFrame(
        rows,
        columns=["assay_investigation_id", "date", "batch_id", "assay", "category",
                 "subcategory", "outcome", "title"],
    ).assign(date=lambda d: pd.to_datetime(d["date"]))


def generate_process_signals(seed: int = SEED) -> pd.DataFrame:
    """Out-of-trend process parameter signals, fictional."""
    rows = [
        ("PS-2025-071", "2025-07-17", "XX0007", "Method (Process)",
         "Cell culture parameters", "VCD_peak_e6", 11.2, 14.5, True,
         "Peak viable cell density below historical band on day 7."),
        ("PS-2025-072", "2025-07-17", "XX0007", "Material (Raw Materials)",
         "Cell culture media / feed lot", "glucose_consumption_g", 18.0, 28.0, True,
         "Reduced glucose consumption rate consistent with poor culture growth."),
        ("PS-2025-073", "2025-07-18", "XX0007", "Material (Raw Materials)",
         "Cell culture media / feed lot", "osmolality_mosm_kg", 528.0, 500.0, True,
         "Elevated harvest osmolality above historical band, consistent with media lot shift."),
        ("PS-2025-079", "2025-08-19", "XX0008", "Method (Process)",
         "Cell culture parameters", "VCD_peak_e6", 11.9, 14.5, True,
         "Peak VCD again below band on repeat batch."),
        ("PS-2025-080", "2025-08-20", "XX0008", "Material (Raw Materials)",
         "Cell culture media / feed lot", "osmolality_mosm_kg", 521.0, 500.0, True,
         "Elevated osmolality again on repeat batch using the same media lot M-2301."),
        ("PS-2025-055", "2025-05-08", "XX0005", "Machine (Equipment)",
         "Bioreactor control", "DO_pct", 41.0, 40.0, False,
         "Minor DO setpoint oscillation, within control."),
    ]
    return pd.DataFrame(
        rows,
        columns=["process_signal_id", "date", "batch_id", "category", "subcategory",
                 "parameter", "value", "expected", "out_of_trend", "title"],
    ).assign(date=lambda d: pd.to_datetime(d["date"]))


# --- Normalization ----------------------------------------------------------

#: Base weight per record type, used by the rule-based fishbone scorer.
RECORD_WEIGHTS = {
    "change_control": 3.0,
    "process_signal": 2.5,
    "deviation": 2.0,
    "assay_investigation": 1.5,
    "capa": 1.0,
}

_SEVERITY_MULTIPLIER = {"Critical": 2.0, "Major": 1.5, "Minor": 1.0}


def _normalize(
    deviations: pd.DataFrame,
    capas: pd.DataFrame,
    change_controls: pd.DataFrame,
    assay_investigations: pd.DataFrame,
    process_signals: pd.DataFrame,
) -> pd.DataFrame:
    """Union all supporting records into one evidence table.

    Columns: record_id, record_type, date, batch_id, category, subcategory,
    base_weight, severity_mult, outcome, title.
    """
    frames = []

    d = deviations.copy()
    d["record_type"] = "deviation"
    d["record_id"] = d["deviation_id"]
    d["base_weight"] = RECORD_WEIGHTS["deviation"]
    d["severity_mult"] = d["severity"].map(_SEVERITY_MULTIPLIER).fillna(1.0)
    d["outcome"] = None
    frames.append(d)

    c = capas.copy()
    c["record_type"] = "capa"
    c["record_id"] = c["capa_id"]
    c["date"] = pd.NaT
    c["batch_id"] = None
    c["base_weight"] = RECORD_WEIGHTS["capa"]
    c["severity_mult"] = 1.0
    c["outcome"] = c["status"]
    frames.append(c)

    cc = change_controls.copy()
    cc["record_type"] = "change_control"
    cc["record_id"] = cc["change_control_id"]
    cc["batch_id"] = None
    cc["base_weight"] = RECORD_WEIGHTS["change_control"]
    cc["severity_mult"] = 1.0
    cc["outcome"] = cc["status"]
    frames.append(cc)

    a = assay_investigations.copy()
    a["record_type"] = "assay_investigation"
    a["record_id"] = a["assay_investigation_id"]
    a["base_weight"] = RECORD_WEIGHTS["assay_investigation"]
    a["severity_mult"] = 1.0
    frames.append(a)

    ps = process_signals.copy()
    ps["record_type"] = "process_signal"
    ps["record_id"] = ps["process_signal_id"]
    ps["base_weight"] = RECORD_WEIGHTS["process_signal"]
    ps["severity_mult"] = 1.0
    ps["outcome"] = ps["out_of_trend"].map({True: "Out of trend", False: "In control"})
    frames.append(ps)

    cols = ["record_id", "record_type", "date", "batch_id", "category",
            "subcategory", "base_weight", "severity_mult", "outcome", "title"]
    out = pd.concat([f[cols] for f in frames], ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out


def load_dataset(seed: int = SEED) -> Dataset:
    """Build the full synthetic dataset (Phase 1 entry point)."""
    deviations = generate_deviations(seed)
    capas = generate_capas(seed)
    change_controls = generate_change_controls(seed)
    assay_investigations = generate_assay_investigations(seed)
    process_signals = generate_process_signals(seed)
    evidence = _normalize(
        deviations, capas, change_controls, assay_investigations, process_signals
    )
    return Dataset(
        batches=generate_batches(seed),
        deviations=deviations,
        capas=capas,
        change_controls=change_controls,
        assay_investigations=assay_investigations,
        process_signals=process_signals,
        evidence=evidence,
    )
