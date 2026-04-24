"""
Scatter 3 — "The long trajectory" (crisis onset vs current, by country).

X-axis: production index, January 2020, as % of 2014-2019 average
Y-axis: production index, current month (edition month), as % of 2014-2019 average
Points: 7 top chemical producers (DE, FR, IT, NL, ES, BE, PL)
Reference: diagonal y = x (no movement since the crisis onset)

Signal strength = max(|distance to diagonal|) normalised; one country far
from the diagonal is already a story.

Data sources:
  - data/cache/{month}/production.json — current month index per country (I21)
  - data/baselines/precrisis_by_country.json — 2014-2019 avg per country (I21)
  - data/baselines/jan2020_by_country.json   — Jan 2020 index per country (I21)

Both baselines are fetched lazily (see data/fetchers/eurostat.py extensions)
and cached. They are global, not per-edition, so re-runs are cheap.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from analysis.scatters.base import (
    ScatterData,
    ScatterPoint,
    COUNTRY_NAMES,
    TOP7_COUNTRIES,
    normalise_max_abs,
)

logger = logging.getLogger("iris.scatters.trajectory")


def _load_current_production_by_country(cache_dir: Path, month: str) -> dict[str, float]:
    """Return {country: index_value} for the edition month, from production.json."""
    prod_path = cache_dir / "production.json"
    if not prod_path.exists():
        raise FileNotFoundError(f"Missing {prod_path}; run the pipeline fetcher first.")
    data = json.loads(prod_path.read_text())
    by_country = data.get("by_country", {})
    out: dict[str, float] = {}
    for ctry, series in by_country.items():
        if ctry not in TOP7_COUNTRIES:
            continue
        # Pick the value for the edition month if present, else the latest.
        if month in series and series[month] is not None:
            out[ctry] = float(series[month])
            continue
        # Fall back to the most recent non-null month.
        months_sorted = sorted((m for m, v in series.items() if v is not None))
        if months_sorted:
            out[ctry] = float(series[months_sorted[-1]])
    return out


def compute(month: str, config: dict) -> ScatterData:
    """Build the Scatter 3 payload.

    `config` supports:
      - cache_dir: Path to data/cache/{month}/
      - baselines_dir: Path to data/baselines/
    """
    cache_dir = Path(config["cache_dir"])
    baselines_dir = Path(config.get("baselines_dir", "data/baselines"))

    precrisis_path = baselines_dir / "precrisis_by_country.json"
    jan2020_path = baselines_dir / "jan2020_by_country.json"
    if not precrisis_path.exists():
        raise FileNotFoundError(
            f"Missing {precrisis_path}; run "
            "data.fetchers.eurostat.fetch_precrisis_by_country(Path('data/baselines')) first."
        )
    if not jan2020_path.exists():
        raise FileNotFoundError(
            f"Missing {jan2020_path}; run "
            "data.fetchers.eurostat.fetch_jan2020_by_country(Path('data/baselines')) first."
        )

    precrisis = json.loads(precrisis_path.read_text())["precrisis_avg_i21_by_country"]
    jan2020 = json.loads(jan2020_path.read_text())["jan_2020_i21_by_country"]
    current = _load_current_production_by_country(cache_dir, month)

    points: list[ScatterPoint] = []
    distances: list[float] = []
    for ctry in TOP7_COUNTRIES:
        if ctry not in precrisis or ctry not in jan2020 or ctry not in current:
            logger.warning(
                "trajectory: skipping %s (precrisis=%s jan2020=%s current=%s)",
                ctry,
                precrisis.get(ctry),
                jan2020.get(ctry),
                current.get(ctry),
            )
            continue
        base = precrisis[ctry]
        if base is None or base == 0:
            continue
        x = 100.0 * jan2020[ctry] / base
        y = 100.0 * current[ctry] / base
        # Distance to diagonal y = x, signed: positive = above the diagonal
        # (country is higher today than at crisis onset).
        delta = y - x
        distances.append(delta)
        points.append(
            ScatterPoint(
                label=ctry,
                x=round(x, 1),
                y=round(y, 1),
                annotations={
                    "country_name": COUNTRY_NAMES.get(ctry, ctry),
                    "precrisis_i21": round(base, 1),
                    "jan_2020_i21": round(jan2020[ctry], 1),
                    "current_i21": round(current[ctry], 1),
                    "delta_from_diagonal_pp": round(delta, 1),
                },
            )
        )

    # Signal strength: max absolute distance to the diagonal, capped at 25pp.
    # Above 25pp the movement is very marked (e.g. Germany's structural shift
    # post 2022 would be around this range).
    sig = normalise_max_abs(distances, cap=25.0) if distances else 0.0
    if distances:
        max_abs = max(distances, key=abs)
        sig_expl = (
            f"Max distance to the diagonal: {max_abs:+.1f} pp "
            f"(capped at 25pp for normalisation). Higher = more structural drift "
            f"between Jan 2020 and today."
        )
    else:
        sig_expl = "No usable data points."

    year = int(month.split("-")[0])

    return ScatterData(
        scatter_id="trajectory",
        title="From crisis onset to now: chemical production by country",
        x_axis_label="Production index, Jan 2020 (% of 2014-2019 average)",
        y_axis_label=f"Production index, {month} (% of 2014-2019 average)",
        points=points,
        reference_lines={"diagonal": True, "x_ref": 100.0, "y_ref": 100.0},
        signal_strength=sig,
        signal_explanation=sig_expl,
        metadata={
            "unit": "index, 2021=100 normalised to 2014-2019 pre-crisis mean",
            "source": "Eurostat sts_inpr_m (I21, SCA), 2014-2019 baseline converted via I15 overlap",
            "edition_month": month,
            "year": year,
        },
    )
