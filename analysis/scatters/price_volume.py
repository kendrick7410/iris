"""
Scatter 2 — "Demand issue or price issue" (Price × Volume by sub-sector).

X-axis: YoY producer price change (%), NACE 4-digit chemical sub-sector
Y-axis: YoY production volume change (%), same NACE detail
Points: up to 10 sub-sectors (C2011, C2013, C2014, C2015, C2016, C2020,
        C2030, C2051, C2059, C2060). Sub-sectors that do not publish at
        NACE 4-digit in Eurostat are dropped and logged.
References: x = 0, y = 0 (the four quadrants are directly interpretable)

Signal strength: fraction of sub-sectors outside the central cluster
(|price YoY| > 3% OR |volume YoY| > 3%). More extremes = more story.

Data source:
  - data/cache/{month}/subsectors.json
      {
        "month": "2026-02",
        "yoy_month": "2025-02",
        "price_yoy_by_sector": {"C2011": 1.2, ...},
        "volume_yoy_by_sector": {"C2011": -2.0, ...}
      }
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from analysis.scatters.base import (
    ScatterData,
    ScatterPoint,
    NACE4_CHEMICAL_SUBSECTORS,
    normalise_count,
)

logger = logging.getLogger("iris.scatters.price_volume")


EXTREME_THRESHOLD = 3.0  # |YoY %| above which a sub-sector is 'extreme'


def compute(month: str, config: dict) -> ScatterData:
    cache_dir = Path(config["cache_dir"])
    subs_path = cache_dir / "subsectors.json"
    if not subs_path.exists():
        raise FileNotFoundError(
            f"Missing {subs_path}; run "
            "data.fetchers.eurostat.fetch_subsectors(month, cache_dir) first."
        )

    data = json.loads(subs_path.read_text())
    prices = data.get("price_yoy_by_sector", {})
    volumes = data.get("volume_yoy_by_sector", {})

    points: list[ScatterPoint] = []
    n_extreme = 0
    for code in NACE4_CHEMICAL_SUBSECTORS:
        x = prices.get(code)
        y = volumes.get(code)
        if x is None or y is None:
            logger.info("price_volume: skipping %s (price=%s volume=%s)", code, x, y)
            continue
        points.append(
            ScatterPoint(
                label=code[1:],  # display without the leading 'C'
                x=round(float(x), 1),
                y=round(float(y), 1),
                annotations={
                    "nace4": code,
                    "sector_name": NACE4_CHEMICAL_SUBSECTORS[code],
                    "price_yoy_pct": round(float(x), 1),
                    "volume_yoy_pct": round(float(y), 1),
                    "quadrant": _quadrant(x, y),
                },
            )
        )
        if abs(x) > EXTREME_THRESHOLD or abs(y) > EXTREME_THRESHOLD:
            n_extreme += 1

    sig = normalise_count(n_extreme, len(points)) if points else 0.0
    sig_expl = (
        f"{n_extreme} of {len(points)} sub-sectors outside |{EXTREME_THRESHOLD:.0f}%| YoY "
        f"on either axis. Higher share = more polarised sector-level story."
    )

    year = int(month.split("-")[0])

    return ScatterData(
        scatter_id="price_volume",
        title="Demand issue or price issue: sub-sector YoY price vs volume",
        x_axis_label="Producer price, YoY change (%)",
        y_axis_label="Production volume, YoY change (%)",
        points=points,
        reference_lines={"x_ref": 0.0, "y_ref": 0.0},
        signal_strength=sig,
        signal_explanation=sig_expl,
        metadata={
            "source": "Eurostat sts_inpr_m + sts_inppd_m (NACE 4-digit, EU27, I21, SCA/NSA)",
            "yoy_anchor": data.get("yoy_month"),
            "edition_month": month,
            "year": year,
            "extreme_threshold_pct": EXTREME_THRESHOLD,
        },
    )


def _quadrant(price_yoy: float, volume_yoy: float) -> str:
    """Human-readable quadrant label."""
    if price_yoy >= 0 and volume_yoy >= 0:
        return "prices up, volumes up (healthy expansion)"
    if price_yoy >= 0 and volume_yoy < 0:
        return "prices up, volumes down (demand weakness)"
    if price_yoy < 0 and volume_yoy >= 0:
        return "prices down, volumes up (market-share push)"
    return "prices down, volumes down (both-sides contraction)"
