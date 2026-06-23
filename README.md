# Biotech Deviation RCA Copilot

A polished Streamlit demo of a **CPV-triggered, AI-assisted fishbone Root Cause
Analysis (RCA) support workflow** for biotech/pharma manufacturing.

> ⚠️ **Investigation support tool only. Synthetic data only.** This app does not
> determine final root cause and does not make batch disposition decisions. All
> outputs are *evidence-based priorities* and *draft investigation support
> summaries* that **require SME / QA review**.

## The workflow it demonstrates

1. **CPV chart** — harvest titer by batch; control limits from an in-control
   baseline. Batches `XX0007` and `XX0008` run low.
2. **Deterministic signal** — a transparent rule (titer < LSL ⇒ OOS, < LCL ⇒
   OOT) raises a low-titer process deviation signal.
3. **Fishbone RCA view** — interactive 6M Ishikawa breakdown.
4. **Evidence-based prioritization** — fishbone branches are ranked by weighted
   evidence drawn from synthetic historical deviations, CAPAs, change controls,
   assay investigations, and process signals. Every priority cites source
   record IDs.

In the bundled story, a media/feed lot changeover (`CC-2025-014`) just before
the excursion makes **Material → Cell culture media / feed lot** the top
candidate cause, while a *cleared* titer-assay investigation keeps the
Measurement branch appropriately low.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # core + pytest

streamlit run app/streamlit_app.py   # the demo
python scripts/demo.py               # headless walkthrough
pytest -q                            # tests
```

## Build phases

| Phase | Status | Module |
|------|--------|--------|
| 1 Synthetic data | ✅ | `data/synthetic.py` |
| 2 CPV chart | ✅ | `cpv.py` |
| 3 Signal detection | ✅ | `signals.py` |
| 4 Fishbone schema | ✅ | `fishbone.py` |
| 5 Rule-based scoring | ✅ | `scoring.py` |
| 6 Evidence cards | ✅ | `evidence.py` |
| 7 Local RAG | 🟡 stub w/ keyword fallback | `rag.py` (`pip install -e ".[rag]"`) |
| 8 Optional LLM summary | 🟡 deterministic default | `llm.py` (`pip install -e ".[llm]"`) |
| 9 Evaluation / demo | ✅ | `tests/`, `scripts/demo.py` |
