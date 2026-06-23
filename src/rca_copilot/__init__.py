"""Biotech Deviation RCA Copilot.

An *investigation support* tool that demonstrates a CPV-triggered, AI-assisted
fishbone Root Cause Analysis workflow on **synthetic data only**.

This package never determines a final root cause and never makes batch
disposition decisions. All outputs are draft investigation support summaries
that require SME / QA review.
"""

__version__ = "0.1.0"

# Compliance framing used throughout the UI and generated text.
DISCLAIMER = (
    "Investigation support tool only. Outputs are evidence-based priorities and "
    "draft investigation support summaries that **require SME / QA review**. "
    "This tool does not confirm root cause or make batch disposition decisions. "
    "All data shown is synthetic."
)
