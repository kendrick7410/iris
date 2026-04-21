"""
Comext Parquet reader for Iris — extracts extra-EU27 trade flows.

Contract:
  - read_parquet(month, cache_dir) → Path (trade.json or trade_unavailable.json)
  - Reads 3 Parquet files from $COMEXT_DATA_PATH (fact + partner_dim + product_dim)
  - Reads SubstanceId.csv from $COMEXT_DATA_PATH/data/upload/ for CN→NACE4 mapping
  - Filters: declarant='EU', partner != 'EU27' (extra-EU only)
  - Splits flow=1 (imports) and flow=2 (exports)
  - Aggregates for target month + YoY month + YTD window + five-year window
  - For key partners (US, CN, GB): CN 8-digit drill-down top-5 codes
  - Writes trade.json with enriched partner / NACE / drill-down payloads
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
SUBSTANCE_CSV = "data/upload/SubstanceId.csv"
TOP_N_PARTNERS = 10
TOP_N_NACE_PER_PARTNER = 3
TOP_N_CN8_DRILL_DOWN = 5
KEY_PARTNERS = ("US", "CN", "GB")
DRILL_DOWN_MIN_COVERAGE = 0.50   # Pattern 21 trigger: top-5 must explain ≥ 50% of delta
INTRA_EU_PARTNER = "EU27"
FIVE_YEARS = 5
MONTHLY_HISTORY_MONTHS = 36       # 3 years — covers N-2 for D5 + 12m Z-score for D3

NACE4_LABELS = {
    "2011": "Industrial gases",
    "2012": "Dyes and pigments",
    "2013": "Other inorganic basic chemicals",
    "2014": "Other organic basic chemicals",
    "2015": "Fertilisers and nitrogen compounds",
    "2016": "Plastics in primary forms",
    "2017": "Synthetic rubber in primary forms",
    "2020": "Pesticides and other agrochemical products",
    "2030": "Paints, varnishes and coatings",
    "2041": "Soap and detergents",
    "2042": "Perfumes and toilet preparations",
    "2051": "Explosives",
    "2052": "Glues",
    "2053": "Essential oils",
    "2059": "Other chemical products",
    "2060": "Man-made fibres",
    "2110": "Basic pharmaceutical products",
}


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
        columns=["period", "declarant", "partner", "product_nc", "chapter_cn", "flow",
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
    cn_to_nace = _load_cn_to_nace(parquet_dir)
    product_labels = _load_product_labels(parquet_dir)
    five_year_start = _five_year_start(target_period)

    trade = {
        "month": month,
        "source_file": FACT_FILE,
        "scope": "Extra-EU27 trade (declarant=EU, partner ≠ EU27), Comext CN 15/22/24/25–39 subset",
        "key_partners": list(KEY_PARTNERS),
        "five_year_start": five_year_start.strftime("%Y-%m"),
        "flows": {
            "exports": _aggregate_flow(
                fact, flow=2, target=target_period, previous=prev_period,
                five_year_start=five_year_start,
                partners=partner_labels, chapters=chapter_labels,
                cn_to_nace=cn_to_nace, product_labels=product_labels,
            ),
            "imports": _aggregate_flow(
                fact, flow=1, target=target_period, previous=prev_period,
                five_year_start=five_year_start,
                partners=partner_labels, chapters=chapter_labels,
                cn_to_nace=cn_to_nace, product_labels=product_labels,
            ),
        },
        "monthly_history": {
            "exports": _monthly_history(fact, flow=2, target=target_period,
                                         months=MONTHLY_HISTORY_MONTHS),
            "imports": _monthly_history(fact, flow=1, target=target_period,
                                         months=MONTHLY_HISTORY_MONTHS),
        },
    }

    out = cache_dir / "trade.json"
    out.write_text(json.dumps(trade, indent=2, default=str), encoding="utf-8")
    logger.info(f"Trade data written to {out}")
    return out


def _aggregate_flow(fact, flow, target, previous, five_year_start,
                     partners, chapters, cn_to_nace, product_labels):
    """Aggregate a single flow direction for target month + YoY + YTD +
    five-year window, with top-NACE and CN-8 drill-down for key partners."""
    flow_df = fact[fact["flow"] == flow]
    current = flow_df[flow_df["period"] == target]
    prev = flow_df[flow_df["period"] == previous]

    target_year = target.year
    ytd_cur = flow_df[(flow_df["period"].dt.year == target_year) &
                      (flow_df["period"] <= target)]
    ytd_prev = flow_df[(flow_df["period"].dt.year == target_year - 1) &
                       (flow_df["period"].dt.month <= target.month)]

    # Five-year window rows — used for both aggregate stats and drill-down
    window_df = flow_df[(flow_df["period"] >= five_year_start) &
                         (flow_df["period"] <= target)]
    start_month_df = flow_df[flow_df["period"] == five_year_start]

    cur_val = float(current["value_in_euros"].sum())
    cur_vol = float(current["quantity_in_kg"].sum())
    prev_val = float(prev["value_in_euros"].sum())
    prev_vol = float(prev["quantity_in_kg"].sum())
    start_val = float(start_month_df["value_in_euros"].sum())
    start_vol = float(start_month_df["quantity_in_kg"].sum())

    # Top-N partner ranking (by value_in_euros)
    cur_by_partner = current.groupby("partner")["value_in_euros"].sum().sort_values(ascending=False)
    prev_by_partner = prev.groupby("partner")["value_in_euros"].sum()
    total = float(cur_by_partner.sum())

    # Pre-compute five-year-start partner values for 5-yr delta per partner
    start_by_partner = start_month_df.groupby("partner")["value_in_euros"].sum()
    start_by_partner_vol = start_month_df.groupby("partner")["quantity_in_kg"].sum()

    by_partner = []
    for rank, (code, value) in enumerate(cur_by_partner.head(TOP_N_PARTNERS).items(), 1):
        prev_v = float(prev_by_partner.get(code, 0.0))
        start_v = float(start_by_partner.get(code, 0.0))
        cur_vol_p = float(current[current["partner"] == code]["quantity_in_kg"].sum())
        start_vol_p = float(start_by_partner_vol.get(code, 0.0))

        entry = {
            "rank": rank,
            "partner": code,
            "label": partners.get(code, code),
            "value_eur_bn": round(value / 1e9, 2),
            "previous_year_value_eur_bn": round(prev_v / 1e9, 2),
            "yoy_pct": _pct(value, prev_v),
            "share_pct": _pct_of_total(value, total),
            "five_year_delta_pct_value":  _pct(value, start_v),
            "five_year_delta_pct_volume": _pct(cur_vol_p, start_vol_p),
        }

        # Top 3 NACE per partner — on the target month
        partner_current = current[current["partner"] == code].copy()
        partner_current["nace4"] = partner_current["product_nc"].map(cn_to_nace)
        nace_agg = (partner_current.dropna(subset=["nace4"])
                     .groupby("nace4")["value_in_euros"].sum()
                     .sort_values(ascending=False))
        partner_total = float(nace_agg.sum())
        entry["top_nace"] = [
            {
                "nace4": nace,
                "label": NACE4_LABELS.get(nace, f"NACE {nace}"),
                "value_eur_bn": round(v / 1e9, 2),
                "share_of_partner_pct": _pct_of_total(v, partner_total),
            }
            for nace, v in nace_agg.head(TOP_N_NACE_PER_PARTNER).items()
        ]

        # CN 8-digit drill-down — key partners only, if concentration ≥ 50%
        if code in KEY_PARTNERS:
            drill = _drill_down_cn8(window_df, start_month_df, current,
                                     partner=code, product_labels=product_labels)
            if drill:
                entry["drill_down"] = drill

        by_partner.append(entry)

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
        "five_year_window": {
            "start": five_year_start.strftime("%Y-%m"),
            "end": target.strftime("%Y-%m"),
            "value_eur_bn_start": round(start_val / 1e9, 2),
            "value_eur_bn_end":   round(cur_val / 1e9, 2),
            "delta_pct_value":    _pct(cur_val, start_val),
            "volume_kt_start":    round(start_vol / 1e6, 1),
            "volume_kt_end":      round(cur_vol / 1e6, 1),
            "delta_pct_volume":   _pct(cur_vol, start_vol),
        },
        "by_partner": by_partner,
        "by_chapter": by_chapter,
    }


def _monthly_history(fact, flow, target, months):
    """Emit the monthly value_eur_bn series for EU27 total and top-10 partners
    over the trailing `months` window ending at `target`.

    Consumed by `analysis.anomaly_detector` for Z-score (D3) and N-2 (D5) checks.
    Both years of the YoY comparison must sit inside the returned window.
    """
    import pandas as pd
    start = target - pd.DateOffset(months=months - 1)
    window = fact[(fact["flow"] == flow) & (fact["period"] >= start) &
                  (fact["period"] <= target)]

    # EU27 total (value sum / period)
    eu27_total = (window.groupby("period")["value_in_euros"].sum() / 1e9).round(2)
    eu27_total_dict = {p.strftime("%Y-%m"): float(v) for p, v in eu27_total.items()}

    # Top-10 partners in the target month, then their monthly series over the window
    target_slice = window[window["period"] == target]
    top_partners = (target_slice.groupby("partner")["value_in_euros"].sum()
                    .sort_values(ascending=False).head(TOP_N_PARTNERS).index)
    by_partner = {}
    for code in top_partners:
        series = (window[window["partner"] == code]
                  .groupby("period")["value_in_euros"].sum() / 1e9).round(2)
        by_partner[str(code)] = {p.strftime("%Y-%m"): float(v) for p, v in series.items()}

    return {
        "window_months": months,
        "eu27_total": eu27_total_dict,
        "by_partner": by_partner,
    }


def _drill_down_cn8(window_df, start_df, current_df, partner, product_labels):
    """Return top-5 CN 8-digit codes driving the change between five-year-start
    and current month for a given partner, if they cover ≥ 50% of the delta.

    Returns None when the concentration threshold is not met — in which case
    Pattern 21 does not apply and the fiche should skip the drill-down.
    """
    start_part = start_df[start_df["partner"] == partner]
    cur_part = current_df[current_df["partner"] == partner]

    start_by_cn = start_part.groupby("product_nc")["value_in_euros"].sum()
    cur_by_cn = cur_part.groupby("product_nc")["value_in_euros"].sum()

    all_codes = set(start_by_cn.index) | set(cur_by_cn.index)
    deltas = []
    for code in all_codes:
        d = float(cur_by_cn.get(code, 0.0)) - float(start_by_cn.get(code, 0.0))
        if d != 0:
            deltas.append((code, d))

    total_delta = sum(d for _, d in deltas)
    if total_delta == 0:
        return None

    # Sort by absolute contribution, pick top-N
    deltas_abs_sorted = sorted(deltas, key=lambda x: abs(x[1]), reverse=True)
    top_n = deltas_abs_sorted[:TOP_N_CN8_DRILL_DOWN]
    top_n_abs_sum = sum(abs(d) for _, d in top_n)
    total_abs = sum(abs(d) for _, d in deltas_abs_sorted)
    coverage = top_n_abs_sum / total_abs if total_abs else 0.0

    if coverage < DRILL_DOWN_MIN_COVERAGE:
        return None

    return {
        "window": f'{window_df["period"].min().strftime("%Y-%m") if len(window_df) else "?"}'
                  f'..{window_df["period"].max().strftime("%Y-%m") if len(window_df) else "?"}',
        "delta_total_eur_bn": round(total_delta / 1e9, 2),
        "covers_pct_of_delta": round(coverage * 100, 1),
        "cn8_codes": [
            {
                "code": code,
                "label_short": _truncate_40(product_labels.get(code, f"CN {code}")),
                "contribution_eur_bn": round(d / 1e9, 3),
                "pct_of_delta": _pct_of_total(abs(d), total_abs),
            }
            for code, d in top_n
        ],
    }


def _truncate_40(label: str) -> str:
    """Apply system.md §5.8 truncation rule to a Comext product description."""
    if not label:
        return ""
    # Keep everything before the first parenthesis, comma, or semicolon
    for sep in ["(", ",", ";"]:
        idx = label.find(sep)
        if 0 < idx <= 80:
            label = label[:idx].strip()
            break
    if len(label) <= 40:
        return label
    cut = label[:37].rsplit(" ", 1)[0]
    return cut + "…"


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


def _five_year_start(period):
    """Return the month 5 years earlier (same calendar month)."""
    return period - pd.DateOffset(years=FIVE_YEARS)


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


def _load_product_labels(parquet_dir):
    """Load CN 8-digit → English label (for drill-down descriptions)."""
    df = pd.read_parquet(parquet_dir / PRODUCT_DIM,
                         columns=["product_code", "label_en", "level"])
    cn = df[df["level"] == "cn_code"]
    return dict(zip(cn["product_code"].astype(str), cn["label_en"].fillna("").astype(str)))


def _load_cn_to_nace(parquet_dir):
    """Load CN 8-digit → NACE 4-digit mapping from SubstanceId.csv.

    SubstanceId.csv lives in the comext-etl upload folder. We read it via
    the COMEXT_DATA_PATH symlink (parquet_dir is the data path root).
    Returns an empty dict if the file is unavailable — drill-down and
    top_nace will then be skipped gracefully.
    """
    csv_path = parquet_dir / SUBSTANCE_CSV
    if not csv_path.exists():
        logger.warning(f"SubstanceId.csv not found at {csv_path}. "
                       f"NACE 4-digit breakdown will be empty.")
        return {}
    try:
        df = pd.read_csv(csv_path, sep=";", skiprows=1, dtype=str).dropna()
        return dict(zip(df["CN2025"].astype(str), df["CPA2015"].str[:4].astype(str)))
    except Exception as e:
        logger.warning(f"Failed to parse SubstanceId.csv: {e}")
        return {}


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
