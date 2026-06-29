"""Fishbone (Ishikawa) schema for a bioprocess low-titer investigation (Phase 4).

Classic 6M categories adapted to upstream/downstream biomanufacturing. The
synthetic supporting records map onto these exact category / subcategory labels
so the scorer (Phase 5) can aggregate evidence per branch.
"""

from __future__ import annotations

FISHBONE: dict[str, list[str]] = {
    "Material (Raw Materials)": [
        "Cell culture media / feed lot",
        "Buffer / reagent lot",
        "Resin / consumables",
        "Water for injection (WFI)",
    ],
    "Method (Process)": [
        "Cell culture parameters",
        "Feed strategy",
        "Harvest / clarification",
        "Process hold times",
    ],
    "Machine (Equipment)": [
        "Bioreactor control",
        "pH / DO probes",
        "Pumps / mass flow",
        "Chromatography skid",
    ],
    "Measurement (Analytical)": [
        "Titer assay (plaque)",
        "Cell count / viability",
        "Bioburden / endotoxin",
        "Calibration",
    ],
    "Man (Personnel)": [
        "Operator technique",
        "Training / qualification",
        "Shift handover",
        "Procedure adherence",
    ],
    "Environment (Facility)": [
        "HVAC / temperature",
        "Cleanroom classification",
        "Utilities",
        "Contamination control",
    ],
}

CATEGORIES = list(FISHBONE.keys())


def all_subcategories() -> list[tuple[str, str]]:
    """Flatten to (category, subcategory) pairs."""
    return [(cat, sub) for cat, subs in FISHBONE.items() for sub in subs]
