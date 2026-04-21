"""
Comext Parquet reader for Iris — extracts extra-EU27 trade flows.

Contract:
  - read_parquet(month, cache_dir) → Path (trade.json or trade_unavailable.json)
  - Reads 3 Parquet files from $COMEXT_DATA_PATH (fact + partner_dim + product_dim)
  - Filters: declarant='EU', partner != 'EU27' (extra-EU only)
  - Splits flow=1 (imports) and flow=2 (exports)
  - Aggregates for target month + YoY month + YTD window
  - Writes trade.json with structured totals, ranked partners, chapter breakdown
  - Iris NEVER queries PostgreSQL or runs the Comext ETL pipeline

If COMEXT_DATA_PATH is unset, parquet is missing, or the month is not yet
loaded (Eurostat ~45-day lag): writes trade_unavailable.json with explicit reason.
"""

import json
import logging
import os
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

logger = logging.getLogger("iris.fetchers.comext")

FACT_FILE = "comext_export.parquet"
PARTNER_DIM = "partner_dim.parquet"
PRODUCT_DIM = "product_dim.parquet"
TOP_N_PARTNERS = 10
INTRA_EU_PARTNER = "EU27"


def read_parquet(month: str, cache_dir: Path) -> Path:
    """Read Comext Parquet files for the given month and write trade.json."""
    comext_path = os.environ.get("COMEXT_DATA_PATH")
    if not comext_path:
        logger.warning("COMEXT_DATA_PATH not set. Trade sections will be skipped.")
        return _write_unavailable(cache_dir, "COMEXT_DATA_PATH environment variable not set")

    parquet_dir = Path(comext_path)
    fact_path = parquet_dir / FACT_FILE
    if not fact_path.exists():
        return _write_unavailable(cache_dir, f"{FACT_FILE} not found at {parquet_dir}")

    target_period = _month_to_period(month)
    prev_period = _yoy_period(target_period)

    logger.info(f"Reading {fact_path.name} ({fact_path.stat().st_size / 1e6:.0f} MB)…")
    fact = pq.read_table(
        fact_path,
        columns=["period", "declarant", "partner", "chapter_cn", "flow",
                 "value_in_euros", "quantity_in_kg"],
    ).to_pandas()

    # Extra-EU27 scope: declarant='EU' (already aggregated upstream), exclude intra-EU
    fact = fact[(fact["declarant"] == "EU") & (fact["partner"] != INTRA_EU_PARTNER)]

    available = fact["period"].unique()
    if target_period not in available:
        latest = max(available) if len(available) else None
        latest_str = latest.strftime("%Y-%m") if latest is not None else "none"
        return _write_unavailable(
            cache_dir,
            f"Month {month} not yet loaded in Comext (Eurostat ~45-day lag). "
            f"Latest available: {latest_str}",
        )

    partner_labels = _load_partner_labels(parquet_dir)
    chapter_labels = _load_chapter_labels(parquet_dir)

    trade = {
        "month": month,
        "source_file": FACT_FILE,
        "scope": "Extra-EU27 trade (declarant=EU, partner ≠ EU27), Comext CN 15/22/24/25–39 subset",
        "flows": {
            "exports": _aggregate_flow(fact, flow=2, target=target_period,
                                        previous=prev_period,
                                        partners=partner_labels, chapters=chapter_labels),
            "imports": _aggregate_flow(fact, flow=1, target=target_period,
                                        previous=prev_period,
                                        partners=partner_labels, chapters=chapter_labels),
        },
    }

    out = cache_dir / "trade.json"
    out.write_text(json.dumps(trade, indent=2, default=str), encoding="utf-8")
    logger.info(f"Trade data written to {out}")
    return out


def _aggregate_flow(fact, flow, target, previous, partners, chapters):
    """Aggregate a single flow direction for target month + YoY + YTD."""
    flow_df = fact[fact["flow"] == flow]
    current = flow_df[flow_df["period"] == target]
    prev = flow_df[flow_df["period"] == previous]

    target_year = target.year
    ytd_cur = flow_df[(flow_df["period"].dt.year == target_year) &
                      (flow_df["period"] <= target)]
    ytd_prev = flow_df[(flow_df["period"].dt.year == target_year - 1) &
                       (flow_df["period"].dt.month <= target.month)]

    cur_val = float(current["value_in_euros"].sum())
    cur_vol = float(current["quantity_in_kg"].sum())
    prev_val = float(prev["value_in_euros"].sum())
    prev_vol = float(prev["quantity_in_kg"].sum())

    # Top-N partner ranking (by value_in_euros)
    cur_by_partner = current.groupby("partner")["value_in_euros"].sum().sort_values(ascending=False)
    prev_by_partner = prev.groupby("partner")["value_in_euros"].sum()
    total = float(cur_by_partner.sum())

    by_partner = []
    for rank, (code, value) in enumerate(cur_by_partner.head(TOP_N_PARTNERS).items(), 1):
        prev_v = float(prev_by_partner.get(code, 0.0))
        by_partner.append({
            "rank": rank,
            "partner": code,
            "label": partners.get(code, code),
            "value_eur_bn": round(value / 1e9, 2),
            "previous_year_value_eur_bn": round(prev_v / 1e9, 2),
            "yoy_pct": _pct(value, prev_v),
            "share_pct": _pct_of_total(value, total),
        })

    # Chapter (sub-sector) breakdown
    cur_by_chapter = current.groupby("chapter_cn")["value_in_euros"].sum().sort_values(ascending=False)
    prev_by_chapter = prev.groupby("chapter_cn")["value_in_euros"].sum()
    by_chapter = {}
    for ch, value in cur_by_chapter.items():
        prev_v = float(prev_by_chapter.get(ch, 0.0))
        by_chapter[ch] = {
            "label": chapters.get(ch, f"Chapter {ch}"),
            "value_eur_bn": round(value / 1e9, 2),
            "previous_year_value_eur_bn": round(prev_v / 1e9, 2),
            "yoy_pct": _pct(value, prev_v),
        }

    return {
        "current": {
            "value_eur_bn": round(cur_val / 1e9, 2),
            "volume_kt": round(cur_vol / 1e6, 1),
            "period": target.strftime("%Y-%m"),
        },
        "previous_year": {
            "value_eur_bn": round(prev_val / 1e9, 2),
            "volume_kt": round(prev_vol / 1e6, 1),
            "period": previous.strftime("%Y-%m"),
            "delta_pct_value": _pct(cur_val, prev_val),
            "delta_pct_volume": _pct(cur_vol, prev_vol),
        },
        "ytd": {
            "current_value_eur_bn": round(float(ytd_cur["value_in_euros"].sum()) / 1e9, 2),
            "previous_year_value_eur_bn": round(float(ytd_prev["value_in_euros"].sum()) / 1e9, 2),
            "delta_pct_value": _pct(float(ytd_cur["value_in_euros"].sum()),
                                     float(ytd_prev["value_in_euros"].sum())),
            "current_volume_kt": round(float(ytd_cur["quantity_in_kg"].sum()) / 1e6, 1),
            "previous_year_volume_kt": round(float(ytd_prev["quantity_in_kg"].sum()) / 1e6, 1),
            "delta_pct_volume": _pct(float(ytd_cur["quantity_in_kg"].sum()),
                                      float(ytd_prev["quantity_in_kg"].sum())),
            "window_months": target.month,
        },
        "by_partner": by_partner,
        "by_chapter": by_chapter,
    }


def _pct(cur, prev):
    if prev is None or prev == 0 or cur is None:
        return None
    return round((cur - prev) / prev * 100, 1)


def _pct_of_total(v, total):
    if total is None or total == 0:
        return None
    return round(v / total * 100, 1)


def _month_to_period(month_str):
    """'2025-12' → Timestamp at last day of month."""
    return pd.Timestamp(month_str) + pd.offsets.MonthEnd(0)


def _yoy_period(period):
    return period - pd.DateOffset(years=1)


def _load_partner_labels(parquet_dir):
    df = pd.read_parquet(parquet_dir / PARTNER_DIM, columns=["partner_code", "label_en"])
    return dict(zip(df["partner_code"].astype(str), df["label_en"].fillna("").astype(str)))


def _load_chapter_labels(parquet_dir):
    df = pd.read_parquet(parquet_dir / PRODUCT_DIM,
                         columns=["product_code", "label_en", "level"])
    chapters = df[df["level"] == "chapter"]
    out = {}
    for code, label in zip(chapters["product_code"].astype(str),
                            chapters["label_en"].fillna("").astype(str)):
        short = label.split(";")[0].strip()
        out[code] = short.capitalize() if short else f"Chapter {code}"
    return out


def _write_unavailable(cache_dir: Path, reason: str) -> Path:
    out = cache_dir / "trade_unavailable.json"
    out.write_text(
        json.dumps({
            "status": "unavailable",
            "reason": reason,
            "sections_affected": ["trade_exports", "trade_imports"],
        }, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Trade unavailable: {reason}")
    return out
