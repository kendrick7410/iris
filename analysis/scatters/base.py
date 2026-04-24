"""
Common data structures for the 4 analytical scatters.

The shape is deliberately simple so Phase B (LLM-based scatter picker) can
read `signal_strength` and `signal_explanation` off the JSON payload
without having to replay the scatter's internal computation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class ScatterPoint:
    """One plotted point.

    `annotations` is free-form metadata the chart template can surface and
    the LLM can reference (e.g. raw yoy, underlying totals, flags). Keep it
    JSON-serialisable (str, float, int, list, dict).
    """
    label: str
    x: float
    y: float
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScatterData:
    """Full payload for one scatter.

    `reference_lines` is a dict with any subset of:
      - `x_ref`: float      -> vertical line at that X
      - `y_ref`: float      -> horizontal line at that Y
      - `diagonal`: bool    -> if True, draw y = x (Scatter 3)
      - `x_thresholds`: list[{value, label}]   -> extra vertical references
      - `y_thresholds`: list[{value, label}]   -> extra horizontal references

    `signal_strength` is a scalar in [0, 1] where higher = more story.
    Phase B ranks scatters by this number.
    """
    scatter_id: str
    title: str
    x_axis_label: str
    y_axis_label: str
    points: list[ScatterPoint]
    reference_lines: dict[str, Any] = field(default_factory=dict)
    signal_strength: float = 0.0
    signal_explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scatter_id": self.scatter_id,
            "title": self.title,
            "x_axis_label": self.x_axis_label,
            "y_axis_label": self.y_axis_label,
            "points": [asdict(p) for p in self.points],
            "reference_lines": self.reference_lines,
            "signal_strength": round(float(self.signal_strength), 4),
            "signal_explanation": self.signal_explanation,
            "metadata": self.metadata,
        }

    def to_json_file(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        return path


# ── Signal-strength helpers ───────────────────────────────────────────────

def clip01(x: float) -> float:
    """Clamp a value into [0, 1]."""
    if x != x:  # NaN guard
        return 0.0
    return max(0.0, min(1.0, float(x)))


def normalise_stdev(values: list[float], cap: float) -> float:
    """Return std-deviation of `values` divided by `cap`, clipped to [0, 1].

    `cap` is the value above which the dispersion is considered 'very strong'.
    Each scatter chooses its own cap; the number is documented at the call site.
    """
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    stdev = var ** 0.5
    return clip01(stdev / cap)


def normalise_count(n_hit: int, n_total: int) -> float:
    """Return the fraction of hits, clipped to [0, 1]."""
    if n_total <= 0:
        return 0.0
    return clip01(n_hit / n_total)


def normalise_max_abs(values: list[float], cap: float) -> float:
    """Return max(|v|) / cap, clipped."""
    if not values:
        return 0.0
    return clip01(max(abs(v) for v in values) / cap)


# ── Country labels (shared across country-level scatters) ─────────────────

COUNTRY_NAMES = {
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "NL": "Netherlands",
    "ES": "Spain",
    "BE": "Belgium",
    "PL": "Poland",
}
TOP7_COUNTRIES = ["DE", "FR", "IT", "NL", "ES", "BE", "PL"]


# ── NACE4 sub-sector labels (shared across sector-level scatters) ─────────

NACE4_CHEMICAL_SUBSECTORS = {
    "C2011": "Industrial gases",
    "C2013": "Inorganic basic chemicals",
    "C2014": "Organic basic chemicals",
    "C2015": "Fertilisers",
    "C2016": "Plastics in primary forms",
    "C2020": "Pesticides and agrochemicals",
    "C2030": "Paints and coatings",
    "C2051": "Explosives",
    "C2059": "Other chemical products",
    "C2060": "Man-made fibres",
}


# ── CN chapter labels (Scatter 4) ─────────────────────────────────────────

CN_CHAPTER_LABELS = {
    "28": "Inorganic chemicals",
    "29": "Organic chemicals",
    "30": "Pharmaceutical products",
    "31": "Fertilisers",
    "32": "Dyes, pigments, paints",
    "33": "Essential oils, cosmetics",
    "34": "Soaps, detergents, waxes",
    "35": "Albuminoidal, glues",
    "38": "Miscellaneous chemicals",
    "39": "Plastics",
}
