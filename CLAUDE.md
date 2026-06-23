# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Streamlit demo (built for a biotech/pharma data-scientist interview) of a
**CPV-triggered, AI-assisted fishbone RCA support workflow**. It detects a
low-titer process deviation on synthetic batches and prioritizes fishbone
candidate causes by weighted, citable evidence.

## Non-negotiable domain framing

These constraints are the point of the demo — preserve them in any code or copy:

- **Synthetic data only.** Never introduce real company, patient, GMP, batch,
  deviation, CAPA, or assay data. All IDs/lots/personnel are fictional.
- This is an **investigation support tool**. It must **never** claim to
  determine final root cause or make batch disposition decisions.
- Use the approved vocabulary: *evidence-based priority*, *candidate cause*,
  *draft investigation support summary*, *requires SME / QA review*.
- Avoid: *confirmed by AI*, *AI determines root cause*, *AI makes batch
  disposition*. These are enforced at runtime by `llm.BANNED_PHRASES` /
  `llm._assert_compliant` — any generated summary must pass that guardrail.
- Every major claim should cite a **source record ID** (e.g. `CC-2025-014`).

## Commands

```bash
pip install -e ".[dev]"                 # install + pytest (Python 3.9+)
streamlit run app/streamlit_app.py      # run the demo UI
python scripts/demo.py                  # headless end-to-end walkthrough
pytest -q                               # all tests
pytest tests/test_scoring.py::test_material_media_is_top_candidate  # single test
```

Optional extras: `pip install -e ".[rag]"` (Chroma), `pip install -e ".[llm]"`
(Anthropic). The app runs fully without either.

## Architecture

Pipeline of pure functions in `src/rca_copilot/`, orchestrated by the Streamlit
app. Data flows one direction; the UI is a thin presentation layer over it:

```
data/synthetic.load_dataset()  →  Dataset (typed tables + normalized `evidence`)
        │
   cpv.compute_control_limits → ControlLimits   (baseline batches only)
        │                                         │
   signals.detect_low_titer_signals(batches, limits) → [Signal]
        │
   scoring.score_fishbone(dataset)  → ranked (category, subcategory, score, source_ids)
        │
   evidence.evidence_for(cat, sub)  → [EvidenceCard]   (per-branch drill-down)
        │
   llm.draft_summary(...)           → compliant draft text
```

Key design decisions a change must respect:

- **`Dataset.evidence` is the scoring substrate.** Each record type
  (deviation/CAPA/change control/assay investigation/process signal) is
  generated as its own realistic table, then `_normalize()` unions them into one
  evidence table with a common schema (`record_id, record_type, category,
  subcategory, base_weight, severity_mult, outcome, ...`). Scoring and evidence
  cards both read this normalized view — so add new evidence by extending a
  generator **and** ensuring its `category`/`subcategory` match the fishbone
  schema labels exactly.
- **Fishbone labels are the join key.** `fishbone.FISHBONE` (6M categories →
  subcategories) defines canonical strings. Synthetic records map onto these
  exact labels; `score_fishbone` drops any (category, subcategory) not in the
  schema. A typo in a label silently removes evidence from the ranking.
- **Scoring is deliberately transparent rule-based math** (no ML/LLM):
  `score = base_weight × severity_mult × proximity × outcome_factor`, summed per
  branch. Cleared assay investigations are down-weighted so they exonerate
  rather than implicate their branch. Keep it auditable.
- **The data is curated to tell one story** (see the module docstring in
  `synthetic.py`): media lot changeover → Material is the top candidate. Tests
  in `tests/test_scoring.py` assert this ordering — changing weights or records
  may require updating those expectations.
- **CPV limits come from `BASELINE_BATCHES` only**, not the full series, so the
  excursion batches don't inflate the limits (real control-chart behavior).
- **Determinism matters** (seeded generation, `@st.cache_data`): the demo must
  produce identical output every run. Don't add nondeterminism to the data or
  scoring path.

## Conventions

- `src/` layout; tests get `src` on the path via `pyproject.toml`
  (`[tool.pytest.ini_options] pythonpath`). The Streamlit app and `scripts/`
  insert `src` manually since they run as scripts, not installed entry points.
- All modules use `from __future__ import annotations` so modern type-hint
  syntax works on Python 3.9 (the only interpreter available in this env).
