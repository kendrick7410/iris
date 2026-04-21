"""
Indicator analysis module for Iris.

Contract:
  - build_fiches(cache_dir, month) → list of fiche Paths in processed dir
  - Reads raw cache JSONs from data/cache/YYYY-MM/
  - Computes YoY, pre-crisis delta, YTD averages, sector/country breakdowns
  - Emits fiche JSONs per system.md §10 schema to data/processed/YYYY-MM/fiches/

Each fiche is self-contained: the LLM rédacteur receives it as-is.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger("iris.analysis")

SECTION_TYPE_MAP = {
    "production": "output",
    "prices": "prices",
    "turnover": "sales",
}

SECTOR_LABELS = {
    "C": "Total manufacturing",
    "C20": "Chemicals",
    "C21": "Pharmaceuticals",
    "C24": "Basic metals",
    "C29": "Motor vehicles",
}

COUNTRY_NAMES = {
    "DE": "Germany", "FR": "France", "IT": "Italy",
    "NL": "Netherlands", "ES": "Spain", "BE": "Belgium", "PL": "Poland",
}

CHART_IDS = {
    "output": ["output_index", "output_yoy_country"],
    "prices": ["prices_index", "prices_yoy_country"],
    "sales": ["turnover_index", "turnover_yoy_country"],
}


def _pct_change(current, previous):
    """Compute percentage change, rounded to 1 decimal."""
    if previous is None or previous == 0 or current is None:
        return None
    return round((current - previous) / previous * 100, 1)


def _find_latest_period(data: dict, target_month: str) -> str:
    """Find the latest available period in data, up to target_month."""
    available = sorted(data.keys())
    candidates = [p for p in available if p <= target_month]
    return candidates[-1] if candidates else None


def _compute_ytd(data: dict, year: str) -> float:
    """Compute year-to-date average for all months of the given year."""
    months = [v for k, v in data.items() if k.startswith(year) and v is not None]
    return round(sum(months) / len(months), 1) if months else None


def _build_sts_fiche(cache_data: dict, month: str, section_type: str,
                     precrisis: dict = None) -> dict:
    """Build a fiche for an STS dataset (production, prices, turnover)."""
    eu27 = cache_data.get("eu27", {})
    by_country_raw = cache_data.get("by_country", {})
    by_sector_raw = cache_data.get("by_sector", {})

    # Find the latest available period
    latest = _find_latest_period(eu27, month)
    if latest is None:
        logger.warning(f"No data available for {section_type} up to {month}")
        return None

    yoy_period = _compute_yoy_month(latest)
    current_val = eu27.get(latest)
    prev_val = eu27.get(yoy_period)

    if current_val is None:
        logger.warning(f"No value for {section_type} at {latest}")
        return None

    # Period metadata
    year, month_num = latest.split("-")
    month_num = int(month_num)
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]

    if month_num == 1:
        window = month_names[0] + f" {year}"
        ytd = None
    else:
        window = f"{month_names[0]}-{month_names[month_num-1]} {year}"
        ytd_current = _compute_ytd(eu27, year)
        ytd_prev = _compute_ytd(eu27, str(int(year) - 1))
        ytd = {
            "current_avg": ytd_current,
            "previous_year_avg": ytd_prev,
            "delta_pct": _pct_change(ytd_current, ytd_prev),
        } if ytd_current and ytd_prev else None

    # Pre-crisis benchmark (production only)
    pre_crisis_avg = None
    if precrisis and section_type == "output":
        pc_val = precrisis.get("precrisis_avg_i21")
        if pc_val:
            pre_crisis_avg = {
                "value": pc_val,
                "base": "2014-2019 average, I15 converted to I21",
                "delta_pct": _pct_change(current_val, pc_val),
            }

    # Country breakdown
    by_country = {}
    for geo in ["DE", "FR", "IT", "NL", "ES", "BE", "PL"]:
        geo_data = by_country_raw.get(geo, {})
        c = geo_data.get(latest)
        p = geo_data.get(yoy_period)
        if c is not None:
            by_country[geo] = {
                "current": c,
                "previous_year": p,
                "yoy_pct": _pct_change(c, p),
            }

    # Sector benchmarks
    by_sector = {}
    for nace, label in SECTOR_LABELS.items():
        nace_data = by_sector_raw.get(nace, {})
        c = nace_data.get(latest)
        p = nace_data.get(yoy_period)
        if c is not None:
            by_sector[nace] = {
                "label": label,
                "current": c,
                "previous_year": p,
                "yoy_pct": _pct_change(c, p),
            }

    dataset_code = cache_data.get("dataset", "unknown")

    fiche = {
        "section_type": section_type,
        "period": {
            "month": latest,
            "publication_date": date.today().isoformat(),
            "window": window,
            "window_months": month_num,
            "window_ordinal": _ordinal(month_num) if month_num > 1 else None,
        },
        "data": {
            "current": {
                "value": current_val,
                "unit": "index 2021=100",
                "period": latest,
                "s_adj": cache_data.get("s_adj", "SCA"),
            },
            "previous_year": {
                "value": prev_val,
                "period": yoy_period,
                "delta_pct": _pct_change(current_val, prev_val),
            },
            "pre_crisis_avg": pre_crisis_avg,
            "ytd": ytd,
            "by_country": by_country if by_country else None,
            "by_sector": by_sector if by_sector else None,
            "source": f"Cefic analysis based on Eurostat data ({dataset_code}, {year})",
        },
        "charts": CHART_IDS.get(section_type, []),
        "editorial_context": {
            "latest_structural_break": "March 2022",
            "notable_events": [],
            "pre_crisis_reference": "2014-2019 average",
        },
    }

    # Note latency if latest != target month
    if latest != month:
        fiche["period"]["note"] = (
            f"Latest available data: {latest}. "
            f"Target month {month} not yet published by Eurostat."
        )

    return fiche


def _compute_yoy_month(period: str) -> str:
    y, m = period.split("-")
    return f"{int(y)-1}-{m}"


def _ordinal(n: int) -> str:
    words = {1: "first", 2: "first two", 3: "first three", 4: "first four",
             5: "first five", 6: "first six", 7: "first seven", 8: "first eight",
             9: "first nine", 10: "first ten", 11: "first eleven", 12: None}
    return words.get(n, f"first {n}")


def build_fiches(cache_dir: Path, month: str) -> list:
    """Build all indicator fiches from cached data.

    Returns list of paths to generated fiche JSONs.
    """
    processed_dir = cache_dir.parent.parent / "processed" / month / "fiches"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Load pre-crisis baseline if available
    baselines_file = cache_dir.parent.parent / "baselines" / "precrisis_i21.json"
    precrisis = None
    if baselines_file.exists():
        precrisis = json.loads(baselines_file.read_text(encoding="utf-8"))

    produced = []

    for cache_name, section_type in SECTION_TYPE_MAP.items():
        cache_file = cache_dir / f"{cache_name}.json"
        if not cache_file.exists():
            logger.info(f"No cache for {cache_name}, skipping {section_type}")
            continue

        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        fiche = _build_sts_fiche(cache_data, month, section_type, precrisis)

        if fiche is None:
            logger.warning(f"Could not build fiche for {section_type}")
            continue

        out = processed_dir / f"{section_type}.json"
        out.write_text(json.dumps(fiche, indent=2), encoding="utf-8")
        logger.info(f"Fiche {section_type} saved to {out}")
        produced.append(out)

    # Check trade availability
    trade_marker = cache_dir / "trade_unavailable.json"
    if trade_marker.exists():
        logger.info("Trade data unavailable — trade sections skipped")

    return produced
