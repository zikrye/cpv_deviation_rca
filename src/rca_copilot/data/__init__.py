"""Synthetic data layer (Phase 1).

All record IDs are stable across runs (seeded generation) so that every claim in
the UI can cite a concrete source record ID.
"""

from rca_copilot.data.synthetic import (
    AFFECTED_BATCHES,
    LSL_TITER,
    Dataset,
    load_dataset,
)

__all__ = ["AFFECTED_BATCHES", "LSL_TITER", "Dataset", "load_dataset"]
