"""Enrich trade fiches with partner_drilldown (CN8) and historical_series (60 months).

Pattern 23 (key-partner symmetry) + Pattern 24 (long-arc context).
Reads the canonical Comext parquet directly, writes enriched fiches in place.

Usage:
    python -m analysis.enrich_fiches 2026-02
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyarrow.parquet as pq

logger = logging.getLogger("iris.analysis.enrich_fiches")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARQUET_PATH = Path("/home/jme/comext-etl/comext_export.parquet")

STRUCTURAL_PARTNERS = ["US", "CN", "GB"]
TOP_PARTNERS_CHART = ["US", "GB", "CN", "CH"]   # lines on the 60m chart
HISTORICAL_MONTHS = 60
NEGLIGIBLE_VOLUME_EUR = 0.1e9                   # < €0.1 bn = skipped

FLOW_EXPORTS = 2
FLOW_IMPORTS = 1


def _load_parquet() -> pd.DataFrame:
    t = pq.read_table(str(PARQUET_PATH), columns=[
        "period", "declarant", "partner", "flow",
        "product_nc", "value_in_euros",
    ])
    df = t.to_pandas()
    df = df[(df["declarant"] == "EU") & (df["partner"] != "EU27")]
    df["period_ym"] = df["period"].dt.strftime("%Y-%m")
    return df


def _truncate_cn8_label(label: str, limit: int = 55) -> str:
    """§5.10: head noun only, drop parentheticals, cap at ~55 chars."""
    if not label:
        return ""
    head = label.split("(")[0].strip(" ,;").rstrip(".")
    if len(head) <= limit:
        return head
    return head[:limit - 1].rstrip() + "…"


def _cn8_catalog(df: pd.DataFrame) -> Dict[str, str]:
    """Return a CN8 -> label map from the parquet's product_nc column.

    Comext stores the CN8 code as product_nc; descriptive labels are not in
    this parquet snapshot. For the MVP, we show the code alone when no
    external label source is wired (follow-up: join with Comext nomenclature).
    """
    return {}


def _partner_cn8_drilldown(
    df: pd.DataFrame,
    partner: str,
    flow: int,
    current_month: str,
    prev_month: str,
) -> Optional[Dict]:
    """Compute CN8-level drill-down for one partner, current vs previous year."""
    p_current = df[(df["partner"] == partner) & (df["flow"] == flow)
                   & (df["period_ym"] == current_month)]
    p_prev = df[(df["partner"] == partner) & (df["flow"] == flow)
                & (df["period_ym"] == prev_month)]

    period_b_value = float(p_current["value_in_euros"].sum()) / 1e9
    period_a_value = float(p_prev["value_in_euros"].sum()) / 1e9

    if period_b_value < NEGLIGIBLE_VOLUME_EUR / 1e9 and period_a_value < NEGLIGIBLE_VOLUME_EUR / 1e9:
        return {"skipped": True, "reason": "negligible_volume"}

    delta_value = period_b_value - period_a_value
    delta_pct = (delta_value / period_a_value * 100) if period_a_value > 0 else None

    # CN8-level aggregation
    cur_by_cn8 = p_current.groupby("product_nc")["value_in_euros"].sum() / 1e9
    prev_by_cn8 = p_prev.groupby("product_nc")["value_in_euros"].sum() / 1e9
    all_cn8 = set(cur_by_cn8.index) | set(prev_by_cn8.index)
    diff = pd.DataFrame({
        "current": [cur_by_cn8.get(c, 0.0) for c in all_cn8],
        "previous": [prev_by_cn8.get(c, 0.0) for c in all_cn8],
    }, index=list(all_cn8))
    diff["delta"] = diff["current"] - diff["previous"]
    diff["delta_pct"] = diff.apply(
        lambda r: (r["delta"] / r["previous"] * 100) if r["previous"] > 0 else None,
        axis=1,
    )

    def _rows(d: pd.DataFrame, sort_key: str, asc: bool, n: int = 3) -> List[Dict]:
        top = d.sort_values(sort_key, ascending=asc).head(n)
        return [{
            "cn8": str(idx),
            "label": f"{idx} (CN8)",
            "value_current_eur_bn": round(float(row["current"]), 3),
            "value_previous_eur_bn": round(float(row["previous"]), 3),
            "delta_eur_bn": round(float(row["delta"]), 3),
            "delta_pct": round(float(row["delta_pct"]), 1)
                         if row["delta_pct"] is not None and pd.notna(row["delta_pct"]) else None,
        } for idx, row in top.iterrows()]

    top_movers_up = _rows(diff, "delta", asc=False, n=3)
    top_movers_down = _rows(diff, "delta", asc=True, n=3)
    largest_current = _rows(diff, "current", asc=False, n=3)

    # Products explaining 50% of the net variation (by |delta|)
    diff["abs_delta"] = diff["delta"].abs()
    net_variation = abs(diff["delta"].sum())
    total_abs = diff["abs_delta"].sum()
    target_base = net_variation if net_variation > 0.05 else total_abs  # fallback to gross

    explain_products: List[Dict] = []
    cumulative = 0.0
    if target_base > 0:
        for idx, row in diff.sort_values("abs_delta", ascending=False).iterrows():
            cumulative += row["abs_delta"]
            explain_products.append({
                "cn8": str(idx),
                "label": f"{idx} (CN8)",
                "delta_eur_bn": round(float(row["delta"]), 3),
                "cumulative_share_pct": round(cumulative / target_base * 100, 1),
            })
            if cumulative / target_base >= 0.50:
                break

    return {
        "partner": partner,
        "period_b_value_eur_bn": round(period_b_value, 3),
        "period_a_value_eur_bn": round(period_a_value, 3),
        "delta_eur_bn": round(delta_value, 3),
        "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
        "window": f"{current_month} vs {prev_month}",
        "top_movers_up": top_movers_up,
        "top_movers_down": top_movers_down,
        "largest_products_current": largest_current,
        "explain_50pct_variation": {
            "product_count": len(explain_products),
            "cumulative_share": round(cumulative / target_base, 3) if target_base else 0,
            "base": "net_variation" if net_variation > 0.05 else "gross_variation",
            "products": explain_products,
        },
    }


def _historical_balance_series(df: pd.DataFrame, months: int = HISTORICAL_MONTHS) -> List[Dict]:
    agg = df.groupby(["period_ym", "flow"])["value_in_euros"].sum().unstack(fill_value=0)
    agg = agg.rename(columns={FLOW_IMPORTS: "imports", FLOW_EXPORTS: "exports"})
    agg["balance"] = agg["exports"] - agg["imports"]
    window = sorted(agg.index)[-months:]
    return [{"period": p, "value_eur_bn": round(agg.loc[p, "balance"] / 1e9, 3)}
            for p in window]


def _historical_exports_by_partner(df: pd.DataFrame, months: int = HISTORICAL_MONTHS) -> Dict:
    x = df[df["flow"] == FLOW_EXPORTS]
    by = x.groupby(["period_ym", "partner"])["value_in_euros"].sum().unstack(fill_value=0) / 1e9
    window = sorted(by.index)[-months:]
    out: Dict[str, List[Dict]] = {}
    for p in TOP_PARTNERS_CHART:
        if p in by.columns:
            out[p] = [{"period": mo, "value_eur_bn": round(float(by.loc[mo, p]), 3)}
                      for mo in window]
        else:
            out[p] = []
    other_cols = [c for c in by.columns if c not in TOP_PARTNERS_CHART]
    if other_cols:
        other = by[other_cols].sum(axis=1)
        out["OTHER"] = [{"period": mo, "value_eur_bn": round(float(other.loc[mo]), 3)}
                        for mo in window]
    return out


def _prev_month(ym: str) -> str:
    y, m = ym.split("-")
    y, m = int(y), int(m)
    return f"{y - 1:04d}-{m:02d}"


def _cache_monthly_series(month: str, cache_file: str) -> Optional[List[Dict]]:
    """Read the EU27 monthly series from data/cache/{month}/{cache_file}.json.

    Returns a chronological list of {period, value} or None if unavailable.
    """
    fp = PROJECT_ROOT / "data" / "cache" / month / f"{cache_file}.json"
    if not fp.exists():
        return None
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
        eu = d.get("eu27") or {}
        if not isinstance(eu, dict) or not eu:
            return None
        return [{"period": p, "value": round(float(v), 2)}
                for p, v in sorted(eu.items()) if v is not None]
    except Exception:
        return None


# Cache file -> fiche section mapping for the monthly index series
_INDEX_SECTIONS = [
    ("output",  "production"),   # fiche section_type / cache filename
    ("prices",  "prices"),
    ("sales",   "turnover"),
]


def enrich(month: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                        datefmt="%Y-%m-%dT%H:%M:%S", stream=sys.stderr)
    logger.info(f"Enriching fiches for {month}")
    df = _load_parquet()
    prev = _prev_month(month)

    historical = {
        "trade_balance_monthly": _historical_balance_series(df),
        "exports_by_partner_monthly": _historical_exports_by_partner(df),
    }

    fiches_dir = PROJECT_ROOT / "data" / "processed" / month / "fiches"

    # Index fiches (output / prices / sales): add monthly_series from cache
    for section_type, cache_file in _INDEX_SECTIONS:
        fp = fiches_dir / f"{section_type}.json"
        if not fp.exists():
            continue
        series = _cache_monthly_series(month, cache_file)
        fiche = json.loads(fp.read_text(encoding="utf-8"))
        if series:
            fiche["data"]["monthly_series"] = series
            fp.write_text(json.dumps(fiche, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"  {section_type}: monthly_series ({len(series)} points)")
        else:
            logger.warning(f"  {section_type}: no monthly_series available (cache missing)")

    for section_type, flow in (("trade_exports", FLOW_EXPORTS),
                                ("trade_imports", FLOW_IMPORTS)):
        fp = fiches_dir / f"{section_type}.json"
        if not fp.exists():
            logger.warning(f"Fiche not found: {fp}, skipping")
            continue
        fiche = json.loads(fp.read_text(encoding="utf-8"))

        drilldown = {}
        for partner in STRUCTURAL_PARTNERS:
            entry = _partner_cn8_drilldown(df, partner, flow, month, prev)
            drilldown[partner] = entry

        fiche["data"]["partner_drilldown"] = drilldown
        fiche["data"]["historical_series"] = historical
        fp.write_text(json.dumps(fiche, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"  {section_type}: partner_drilldown x{len(drilldown)} + historical_series x{len(historical)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m analysis.enrich_fiches YYYY-MM", file=sys.stderr)
        sys.exit(64)
    enrich(sys.argv[1])
