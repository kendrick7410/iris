"""
Scatter-plot analytics for Iris monthly report.

Each submodule implements one scatter per the Phase A spec. All modules
expose the same contract:

    compute(month: str, config: dict) -> ScatterData

See `base.py` for the shared dataclasses and `context-prep/cms-design.md`
(not yet updated for this feature; see scripts/build_scatters.py docstring)
for the phase plan.
"""
from analysis.scatters.base import ScatterData, ScatterPoint
from analysis.scatters import cu_trade, price_volume, trajectory, concentration

SCATTERS = {
    "cu_trade": cu_trade,
    "price_volume": price_volume,
    "trajectory": trajectory,
    "concentration": concentration,
}

__all__ = ["ScatterData", "ScatterPoint", "SCATTERS"]
