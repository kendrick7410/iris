"""
Scatter 2 — "Demand issue or price issue" (Price × Volume by country, NACE C20).

X-axis: YoY producer price change (%), chemical industry NACE C20
Y-axis: YoY production volume change (%), chemical industry NACE C20
Points: 7 top producers (DE, FR, IT, NL, ES, BE, PL)
References: x = 0, y = 0 (the four quadrants are directly interpretable)

Signal strength: fraction of countries outside the central cluster
(|price YoY| > 3% OR |volume YoY| > 3%). More extremes = more story.

Data sources (already produced by the main monthly pipeline):
  - data/cache/{month}/production.json  (sts_inpr_m, I21, SCA, by_country)
  - data/cache/{month}/prices.json      (sts_inppd_m, I21, NSA, by_country)

YoY anchor = the same calendar month, one year earlier.
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
    normalise_count,
)

logger = logging.getLogger("iris.scatters.price_volume")


EXTREME_THRESHOLD = 3.0  # |YoY %| above which a country is 'extreme'


def _yoy_month(month: str) -> str:
    y, m = month.split("-")
    return f"{int(y) - 1}-{m}"


def _yoy(series: dict, target_month: str, anchor_month: str) -> float | None:
    cur = series.get(target_month)
    prev = series.get(anchor_month)
    if cur is None or prev is None or prev == 0:
        return None
    return round(100.0 * (cur - prev) / prev, 2)


def _quadrant(price_yoy: float, volume_yoy: float) -> str:
    """Human-readable quadrant label."""
    if price_yoy >= 0 and volume_yoy >= 0:
        return "prices up, volumes up (healthy expansion)"
    if price_yoy >= 0 and volume_yoy < 0:
        return "prices up, volumes down (demand weakness)"
    if price_yoy < 0 and volume_yoy >= 0:
        return "prices down, volumes up (market-share push)"
    return "prices down, volumes down (both-sides contraction)"


def compute(month: str, config: dict) -> ScatterData:
    cache_dir = Path(config["cache_dir"])
    prod_path = cache_dir / "production.json"
    prices_path = cache_dir / "prices.json"
    for p in (prod_path, prices_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {p}; run the main Eurostat fetchers first "
                "(data.fetchers.eurostat.fetch_production / fetch_prices)."
            )

    prod = json.loads(prod_path.read_text())
    prices = json.loads(prices_path.read_text())
    prod_by_country = prod.get("by_country", {})
    prices_by_country = prices.get("by_country", {})

    anchor = _yoy_month(month)
    points: list[ScatterPoint] = []
    n_extreme = 0
    for ctry in TOP7_COUNTRIES:
        price_series = prices_by_country.get(ctry, {})
        volume_series = prod_by_country.get(ctry, {})
        price_yoy = _yoy(price_series, month, anchor)
        volume_yoy = _yoy(volume_series, month, anchor)
        if price_yoy is None or volume_yoy is None:
            logger.info(
                "price_volume: skipping %s (price=%s volume=%s)",
                ctry, price_yoy, volume_yoy,
            )
            continue
        points.append(
            ScatterPoint(
                label=ctry,
                x=round(float(price_yoy), 1),
                y=round(float(volume_yoy), 1),
                annotations={
                    "country_name": COUNTRY_NAMES.get(ctry, ctry),
                    "nace": "C20",
                    "month": month,
                    "yoy_anchor": anchor,
                    "price_yoy_pct": round(float(price_yoy), 1),
                    "volume_yoy_pct": round(float(volume_yoy), 1),
                    "price_index_current": round(float(price_series.get(month, 0)), 1),
                    "volume_index_current": round(float(volume_series.get(month, 0)), 1),
                    "quadrant": _quadrant(price_yoy, volume_yoy),
                },
            )
        )
        if abs(price_yoy) > EXTREME_THRESHOLD or abs(volume_yoy) > EXTREME_THRESHOLD:
            n_extreme += 1

    sig = normalise_count(n_extreme, len(points)) if points else 0.0
    sig_expl = (
        f"{n_extreme} of {len(points)} countries outside |{EXTREME_THRESHOLD:.0f}%| YoY "
        f"on either axis. Higher share = more polarised country-level story."
    )

    year = int(month.split("-")[0])

    return ScatterData(
        scatter_id="price_volume",
        title="Demand issue or price issue: country-level chemical price vs volume YoY",
        x_axis_label=f"Producer price (NACE C20), YoY change vs {anchor} (%)",
        y_axis_label=f"Production volume (NACE C20), YoY change vs {anchor} (%)",
        points=points,
        reference_lines={"x_ref": 0.0, "y_ref": 0.0},
        signal_strength=sig,
        signal_explanation=sig_expl,
        metadata={
            "source": "Eurostat sts_inpr_m + sts_inppd_m (NACE C20, country-level)",
            "yoy_anchor": anchor,
            "edition_month": month,
            "year": year,
            "extreme_threshold_pct": EXTREME_THRESHOLD,
        },
    )
