"""
Scatter 4 — "Strategic exposure" (partner HHI × product HHI, per CN chapter).

X-axis: Herfindahl-Hirschman Index on export partners (0-10000)
Y-axis: Herfindahl-Hirschman Index on CN 8-digit products within the chapter
        (0-10000)
Points: up to 10 CN chapters (28, 29, 30, 31, 32, 33, 34, 35, 38, 39)
References: 1500 ('moderately concentrated'), 2500 ('highly concentrated')
            applied on both axes as threshold lines.

Signal strength: fraction of chapters sitting in the 'highly concentrated'
zone (HHI > 2500 on at least one axis). More chapters in red = more
strategic exposure across the export portfolio.

Data sourced directly from the Comext parquet — the aggregation here is
specific enough that caching a separate JSON per scatter is cleaner than
bending the existing trade.json shape.

  Parquet: /home/jme/comext-etl/comext_export.parquet
    schema: period, declarant (=EU), partner, product_nc (CN8),
            cpa2015, chapter_cn, flow (1=import, 2=export), value_in_euros

We filter to:
  - flow = 2 (exports)
  - partner != 'EU27'  (extra-EU only)
  - period in the most recent full rolling 3 months available
  - chapter_cn in the target list
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from analysis.scatters.base import (
    ScatterData,
    ScatterPoint,
    CN_CHAPTER_LABELS,
    normalise_count,
)

logger = logging.getLogger("iris.scatters.concentration")

TARGET_CHAPTERS = ["28", "29", "30", "31", "32", "33", "34", "35", "38", "39"]
HHI_MODERATE = 1500
HHI_HIGH = 2500


def _hhi(shares_pct: list[float]) -> float:
    """HHI from a list of percentage shares (0-100). 0 = fully diversified,
    10000 = single actor."""
    return sum(s * s for s in shares_pct)


def compute(month: str, config: dict) -> ScatterData:
    """Compute concentration HHIs for export chapters.

    `config` keys:
      - parquet_path: Path to comext_export.parquet (defaults to env or
        standard sibling path)
      - window_months: int, how many trailing months to aggregate (default 3)
      - cache_dir: Path to data/cache/{month}/ for saving the raw
        aggregation (concentration_raw.json)
    """
    import pandas as pd

    parquet_path = Path(
        config.get("parquet_path", "/home/jme/comext-etl/comext_export.parquet")
    )
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet missing at {parquet_path}")

    window = int(config.get("window_months", 3))
    cache_dir = Path(config["cache_dir"])

    df = pd.read_parquet(parquet_path)
    # Narrow filters (string dtypes for partner/chapter — cheap).
    df = df[(df["flow"] == 2) & (df["partner"] != "EU27")]
    df["chapter_cn"] = df["chapter_cn"].astype(str)
    df = df[df["chapter_cn"].isin(TARGET_CHAPTERS)]

    # Pick the trailing `window` months relative to the edition month.
    try:
        edition_ts = pd.Timestamp(f"{month}-01") + pd.offsets.MonthEnd(0)
    except Exception:
        edition_ts = df["period"].max()
    window_start = edition_ts - pd.DateOffset(months=window - 1)
    df = df[(df["period"] >= window_start) & (df["period"] <= edition_ts)]

    if df.empty:
        raise RuntimeError(
            f"No export rows for chapters {TARGET_CHAPTERS} in the rolling "
            f"{window} months ending {edition_ts.date()}."
        )

    points: list[ScatterPoint] = []
    n_high = 0
    raw_dump: dict = {}
    for chap in TARGET_CHAPTERS:
        sub = df[df["chapter_cn"] == chap]
        if sub.empty:
            logger.info("concentration: chapter %s has no rows in window", chap)
            continue

        total = float(sub["value_in_euros"].sum())
        if total <= 0:
            continue

        # Partner HHI
        partner_val = sub.groupby("partner")["value_in_euros"].sum()
        partner_share = (partner_val / total * 100.0).tolist()
        hhi_partner = _hhi(partner_share)

        # Product (CN8) HHI
        product_val = sub.groupby("product_nc")["value_in_euros"].sum()
        product_share = (product_val / total * 100.0).tolist()
        hhi_product = _hhi(product_share)

        # Top partner / top product for annotations
        top_partner = partner_val.idxmax()
        top_partner_share = float(partner_val.max() / total * 100.0)
        top_product = product_val.idxmax()
        top_product_share = float(product_val.max() / total * 100.0)

        points.append(
            ScatterPoint(
                label=chap,
                x=round(hhi_partner, 0),
                y=round(hhi_product, 0),
                annotations={
                    "chapter_cn": chap,
                    "chapter_name": CN_CHAPTER_LABELS.get(chap, chap),
                    "hhi_partners": round(hhi_partner, 0),
                    "hhi_products_cn8": round(hhi_product, 0),
                    "top_partner": top_partner,
                    "top_partner_share_pct": round(top_partner_share, 1),
                    "top_product_cn8": str(top_product),
                    "top_product_share_pct": round(top_product_share, 1),
                    "n_partners": int(len(partner_val)),
                    "n_products_cn8": int(len(product_val)),
                    "total_value_eur_bn": round(total / 1e9, 2),
                },
            )
        )
        raw_dump[chap] = {
            "total_eur_bn": round(total / 1e9, 2),
            "hhi_partner": round(hhi_partner, 0),
            "hhi_product": round(hhi_product, 0),
            "top_partner_share_pct": round(top_partner_share, 1),
            "top_product_share_pct": round(top_product_share, 1),
        }
        if hhi_partner > HHI_HIGH or hhi_product > HHI_HIGH:
            n_high += 1

    # Persist the raw aggregation for reproducibility / later LLM consumption.
    (cache_dir).mkdir(parents=True, exist_ok=True)
    (cache_dir / "concentration_raw.json").write_text(
        json.dumps(
            {
                "edition_month": month,
                "window_months": window,
                "window_end": edition_ts.strftime("%Y-%m"),
                "chapters": raw_dump,
            },
            indent=2,
        )
    )

    sig = normalise_count(n_high, len(points)) if points else 0.0
    sig_expl = (
        f"{n_high} of {len(points)} chapters sit in the 'highly concentrated' "
        f"zone (HHI > {HHI_HIGH} on at least one axis). Higher share = more "
        f"strategic exposure across the export portfolio."
    )

    year = int(month.split("-")[0])

    return ScatterData(
        scatter_id="concentration",
        title="Strategic exposure: partner vs product concentration by CN chapter",
        x_axis_label="HHI on export partners (0 = diversified, 10000 = one partner)",
        y_axis_label="HHI on CN 8-digit products (0 = diversified, 10000 = one product)",
        points=points,
        reference_lines={
            "x_thresholds": [
                {"value": HHI_MODERATE, "label": "moderately concentrated"},
                {"value": HHI_HIGH, "label": "highly concentrated"},
            ],
            "y_thresholds": [
                {"value": HHI_MODERATE, "label": "moderately concentrated"},
                {"value": HHI_HIGH, "label": "highly concentrated"},
            ],
        },
        signal_strength=sig,
        signal_explanation=sig_expl,
        metadata={
            "source": "Comext EU parquet (extra-EU27 exports, flow=2)",
            "window_months": window,
            "window_end": edition_ts.strftime("%Y-%m"),
            "edition_month": month,
            "year": year,
            "hhi_thresholds": {"moderate": HHI_MODERATE, "high": HHI_HIGH},
        },
    )
