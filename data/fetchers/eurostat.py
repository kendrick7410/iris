"""
Eurostat API fetcher for Iris.

Fetches 4 datasets: sts_inpr_m (production), sts_inppd_m (prices),
sts_intv_m (turnover), nama_10_gdp (GDP).

Contract:
  - fetch_production(month) → dict saved to cache/YYYY-MM/production.json
  - fetch_prices(month) → dict saved to cache/YYYY-MM/prices.json
  - fetch_turnover(month) → dict saved to cache/YYYY-MM/turnover.json
  - fetch_gdp(month) → dict saved to cache/YYYY-MM/gdp.json

Each function returns raw structured data with EU27 aggregate + country
breakdown + sector benchmarks. The analysis module transforms these into
fiches.

Critical note: Eurostat migrated STS indices from I15 (2015=100) to
I21 (2021=100). Recent data requires unit=I21. Pre-crisis baselines
(2014-2019) require unit=I15 with conversion factor.
"""

import json
import logging
import time
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger("iris.fetchers.eurostat")

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

TOP7_COUNTRIES = ["DE", "FR", "IT", "NL", "ES", "BE", "PL"]
BENCHMARK_NACE = ["C", "C20", "C21", "C24", "C29"]

# Dataset configs: (dataset_code, unit, s_adj)
DATASET_CONFIGS = {
    "production": ("sts_inpr_m", "I21", "SCA"),
    "prices":     ("sts_inppd_m", "I21", "NSA"),
    "turnover":   ("sts_intv_m", "I21", "SCA"),
}


def _api_call(dataset: str, params: dict, retries: int = 3) -> dict:
    """Call Eurostat API with retry on transient errors."""
    geo_params = params.pop("_geo_list", None)
    nace_params = params.pop("_nace_list", None)

    parts = [f"{k}={v}" for k, v in params.items()]
    if geo_params:
        parts.extend(f"geo={g}" for g in geo_params)
    if nace_params:
        parts.extend(f"nace_r2={n}" for n in nace_params)

    url = f"{BASE_URL}/{dataset}?{'&'.join(parts)}"

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait = 2 ** (attempt + 1)
            logger.warning(f"Eurostat API attempt {attempt+1}/{retries} failed: {e}. Retry in {wait}s.")
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                raise


def _parse_single_dim(data: dict) -> dict:
    """Parse response with single geo, single nace, multiple time periods."""
    vals = data.get("value", {})
    time_idx = data["dimension"]["time"]["category"]["index"]
    idx_to_time = {str(v): k for k, v in time_idx.items()}
    return {idx_to_time[k]: v for k, v in vals.items()}


def _parse_multi_dim(data: dict, varying_dim: str) -> dict:
    """Parse response with one varying dimension (geo or nace_r2) + time."""
    vals = data.get("value", {})
    if not vals:
        return {}

    dims = data["dimension"]
    d1_idx = dims[varying_dim]["category"]["index"]
    d2_idx = dims["time"]["category"]["index"]

    d1_labels = {v: k for k, v in d1_idx.items()}
    d2_labels = {v: k for k, v in d2_idx.items()}
    n_d2 = len(d2_idx)

    result = {}
    for flat_str, val in vals.items():
        flat = int(flat_str)
        i1 = flat // n_d2
        i2 = flat % n_d2
        key1 = d1_labels.get(i1, f"?{i1}")
        key2 = d2_labels.get(i2, f"?{i2}")
        result.setdefault(key1, {})[key2] = val
    return result


def _compute_yoy_month(target_month: str) -> str:
    """Given '2026-02', return '2025-02'."""
    y, m = target_month.split("-")
    return f"{int(y)-1}-{m}"


def _fetch_sts_dataset(name: str, month: str) -> dict:
    """Fetch a single STS dataset with EU27 + countries + sectors."""
    dataset, unit, s_adj = DATASET_CONFIGS[name]
    # One month buffer before YoY anchor to cover publication lag:
    # if latest available is month-1, its YoY reference is yoy_month-1.
    y, m = _compute_yoy_month(month).split("-")
    since_m = int(m) - 1
    since_y = int(y) if since_m >= 1 else int(y) - 1
    since_m = since_m if since_m >= 1 else 12
    since_month = f"{since_y}-{since_m:02d}"

    result = {"dataset": dataset, "month": month, "unit": unit, "s_adj": s_adj}

    # EU27 aggregate
    logger.info(f"Fetching {name} EU27 aggregate...")
    eu27_data = _api_call(dataset, {
        "geo": "EU27_2020", "nace_r2": "C20",
        "unit": unit, "s_adj": s_adj,
        "sinceTimePeriod": since_month,
    })
    result["eu27"] = _parse_single_dim(eu27_data)

    # Country breakdown
    logger.info(f"Fetching {name} country breakdown...")
    country_data = _api_call(dataset, {
        "_geo_list": TOP7_COUNTRIES,
        "nace_r2": "C20", "unit": unit, "s_adj": s_adj,
        "sinceTimePeriod": since_month,
    })
    result["by_country"] = _parse_multi_dim(country_data, "geo")

    # Sector benchmarks
    logger.info(f"Fetching {name} sector benchmarks...")
    sector_data = _api_call(dataset, {
        "geo": "EU27_2020",
        "_nace_list": BENCHMARK_NACE,
        "unit": unit, "s_adj": s_adj,
        "sinceTimePeriod": since_month,
    })
    result["by_sector"] = _parse_multi_dim(sector_data, "nace_r2")

    return result


def fetch_production(month: str, cache_dir: Path) -> Path:
    """Fetch industrial production index and save to cache."""
    out = cache_dir / "production.json"
    data = _fetch_sts_dataset("production", month)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"Production data saved to {out}")
    return out


def fetch_prices(month: str, cache_dir: Path) -> Path:
    """Fetch producer price index and save to cache."""
    out = cache_dir / "prices.json"
    data = _fetch_sts_dataset("prices", month)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"Prices data saved to {out}")
    return out


def fetch_turnover(month: str, cache_dir: Path) -> Path:
    """Fetch turnover index and save to cache."""
    out = cache_dir / "turnover.json"
    data = _fetch_sts_dataset("turnover", month)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"Turnover data saved to {out}")
    return out


def fetch_gdp(month: str, cache_dir: Path) -> Path:
    """Fetch GDP data (annual) and save to cache."""
    out = cache_dir / "gdp.json"
    year = int(month.split("-")[0])

    logger.info("Fetching GDP...")
    gdp_data = _api_call("nama_10_gdp", {
        "geo": "EU27_2020", "unit": "CLV10_MEUR",
        "na_item": "B1GQ",
        "sinceTimePeriod": str(year - 3),
    })

    result = {"dataset": "nama_10_gdp", "month": month, "values": _parse_single_dim(gdp_data)}
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info(f"GDP data saved to {out}")
    return out


def fetch_precrisis_baseline(cache_dir: Path) -> Path:
    """Fetch 2014-2019 baseline for production (I15) and compute I21 conversion.

    This is run once and cached in data/baselines/precrisis_i21.json.
    """
    baselines_dir = cache_dir.parent.parent / "baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)
    out = baselines_dir / "precrisis_i21.json"

    if out.exists():
        logger.info(f"Pre-crisis baseline already cached at {out}")
        return out

    logger.info("Computing pre-crisis baseline (2014-2019, I15 → I21 conversion)...")

    # Fetch I15 for 2014-2019
    i15_data = _api_call("sts_inpr_m", {
        "geo": "EU27_2020", "nace_r2": "C20",
        "unit": "I15", "s_adj": "SCA",
        "sinceTimePeriod": "2014-01", "untilTimePeriod": "2019-12",
    })
    i15_values = _parse_single_dim(i15_data)
    i15_avg = sum(v for v in i15_values.values() if v) / len([v for v in i15_values.values() if v])

    # Fetch overlap year 2021 in both I15 and I21
    i15_2021 = _api_call("sts_inpr_m", {
        "geo": "EU27_2020", "nace_r2": "C20",
        "unit": "I15", "s_adj": "SCA",
        "sinceTimePeriod": "2021-01", "untilTimePeriod": "2021-12",
    })
    i21_2021 = _api_call("sts_inpr_m", {
        "geo": "EU27_2020", "nace_r2": "C20",
        "unit": "I21", "s_adj": "SCA",
        "sinceTimePeriod": "2021-01", "untilTimePeriod": "2021-12",
    })

    i15_vals = _parse_single_dim(i15_2021)
    i21_vals = _parse_single_dim(i21_2021)
    common = set(i15_vals.keys()) & set(i21_vals.keys())
    ratios = [i21_vals[m] / i15_vals[m] for m in common if i15_vals[m] and i21_vals[m]]
    conv_factor = sum(ratios) / len(ratios)

    precrisis_i21 = round(i15_avg * conv_factor, 1)

    result = {
        "precrisis_avg_i15": round(i15_avg, 1),
        "conversion_factor_i15_to_i21": round(conv_factor, 4),
        "precrisis_avg_i21": precrisis_i21,
        "months_used": len(i15_values),
        "overlap_year": 2021,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info(f"Pre-crisis baseline saved: {precrisis_i21} (I21)")
    return out


# ─────────────────────────────────────────────────────────────────────────
# Extensions for Phase A scatter analytics (analysis/scatters/).
#
# These fetchers reuse `_api_call` and the same TOP7_COUNTRIES list; they
# only add new endpoints and cached files. Nothing below touches the
# existing fetch_production / fetch_prices / fetch_turnover contract.
# ─────────────────────────────────────────────────────────────────────────

# NACE 4-digit chemical sub-sectors requested by Scatter 2.
NACE4_SUBSECTORS = [
    "C2011", "C2013", "C2014", "C2015", "C2016",
    "C2020", "C2030", "C2051", "C2059", "C2060",
]


def previous_full_quarter(edition_month: str) -> tuple[str, list[str]]:
    """Return ('YYYY-Qn', ['YYYY-MM', 'YYYY-MM', 'YYYY-MM']) for the latest
    quarter that fully elapsed before the edition month.

    Used to align quarterly indicators (BCS) with monthly trade aggregations
    on the same window. For a Feb 2026 edition the answer is Q4 2025
    (Oct/Nov/Dec 2025), not Q1 2026 which is still in progress.
    """
    y, m = (int(x) for x in edition_month.split("-"))
    if m <= 3:
        qy, q = y - 1, 4
    elif m <= 6:
        qy, q = y, 1
    elif m <= 9:
        qy, q = y, 2
    else:
        qy, q = y, 3
    end_month = q * 3
    months = [
        f"{qy}-{end_month - 2:02d}",
        f"{qy}-{end_month - 1:02d}",
        f"{qy}-{end_month:02d}",
    ]
    return f"{qy}-Q{q}", months


def fetch_bcs_cu(month: str, cache_dir: Path) -> Path:
    """Fetch BCS manufacturing capacity utilisation per country, pinned to
    the latest fully-elapsed quarter before the edition month.

    Saves data/cache/{month}/bcs.json with:
      {
        "dataset": "ei_bsin_q_r2",
        "indicator": "BS-ICU-PC",
        "note": "manufacturing total; NACE C20 not published per country",
        "latest_quarter": "YYYY-Qn",
        "quarter_months": ["YYYY-MM", "YYYY-MM", "YYYY-MM"],
        "cu_by_country": {"DE": 74.0, ...}
      }

    The quarter is the latest one that fully ended before `month`, so the
    cu_trade scatter can align its trade-balance window on the same 3
    months (the BCS Q1 forecast is intentionally skipped while Q1 is still
    in progress).
    """
    out = cache_dir / "bcs.json"
    logger.info("Fetching BCS capacity utilisation by country...")

    target_quarter, quarter_months = previous_full_quarter(month)

    year = int(target_quarter.split("-Q")[0])
    since_q = f"{year - 1}-Q1"

    data = _api_call("ei_bsin_q_r2", {
        "indic": "BS-ICU-PC",
        "s_adj": "SA",
        "_geo_list": TOP7_COUNTRIES,
        "sinceTimePeriod": since_q,
    })

    by_country_time = _parse_multi_dim(data, "geo")

    available = set()
    for series in by_country_time.values():
        available.update(k for k, v in series.items() if v is not None)
    if not available:
        raise RuntimeError("BCS returned no usable data for the top-7 countries.")
    if target_quarter not in available:
        # Fall back to the latest fully-elapsed quarter that BCS actually has.
        elapsed = [q for q in sorted(available) if q <= target_quarter]
        if not elapsed:
            raise RuntimeError(
                f"BCS has no quarter ≤ {target_quarter}; available: {sorted(available)}."
            )
        target_quarter = elapsed[-1]
        # Recompute the months for the chosen quarter.
        qy, qn = target_quarter.split("-Q")
        end_m = int(qn) * 3
        quarter_months = [
            f"{qy}-{end_m - 2:02d}",
            f"{qy}-{end_m - 1:02d}",
            f"{qy}-{end_m:02d}",
        ]

    cu_by_country: dict[str, float] = {}
    for ctry in TOP7_COUNTRIES:
        v = by_country_time.get(ctry, {}).get(target_quarter)
        if v is not None:
            cu_by_country[ctry] = round(float(v), 1)

    result = {
        "dataset": "ei_bsin_q_r2",
        "indicator": "BS-ICU-PC",
        "note": "manufacturing total; NACE C20 not published per country",
        "latest_quarter": target_quarter,
        "quarter_months": quarter_months,
        "cu_by_country": cu_by_country,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info(
        "BCS CU saved to %s (quarter=%s, %d countries)",
        out, target_quarter, len(cu_by_country),
    )
    return out


def fetch_subsectors(month: str, cache_dir: Path) -> Path:
    """Fetch NACE 4-digit chemical sub-sector YoY production + price change.

    Saves data/cache/{month}/subsectors.json with:
      {
        "month": "2026-02",
        "yoy_month": "2025-02",
        "price_yoy_by_sector": {"C2011": 1.2, ...},
        "volume_yoy_by_sector": {"C2011": -2.0, ...}
      }
    """
    out = cache_dir / "subsectors.json"
    logger.info("Fetching NACE 4-digit sub-sector production + prices...")

    yoy_month = _compute_yoy_month(month)

    # Eurostat API: fetch EU27 values across all target NACE codes, since
    # one month before the YoY anchor.
    y, m = yoy_month.split("-")
    since_m = int(m) - 1
    since_y = int(y) if since_m >= 1 else int(y) - 1
    since_m = since_m if since_m >= 1 else 12
    since_month = f"{since_y}-{since_m:02d}"

    def _yoy_map(dataset: str, unit: str, s_adj: str) -> dict[str, float]:
        raw = _api_call(dataset, {
            "geo": "EU27_2020",
            "_nace_list": NACE4_SUBSECTORS,
            "unit": unit, "s_adj": s_adj,
            "sinceTimePeriod": since_month,
        })
        by_nace = _parse_multi_dim(raw, "nace_r2")
        out_map: dict[str, float] = {}
        for code, series in by_nace.items():
            cur = series.get(month)
            prev = series.get(yoy_month)
            if cur is None or prev is None or prev == 0:
                continue
            out_map[code] = round(100.0 * (cur - prev) / prev, 2)
        return out_map

    prod_yoy = _yoy_map("sts_inpr_m", "I21", "SCA")
    price_yoy = _yoy_map("sts_inppd_m", "I21", "NSA")

    result = {
        "month": month,
        "yoy_month": yoy_month,
        "dataset_production": "sts_inpr_m (I21, SCA)",
        "dataset_prices": "sts_inppd_m (I21, NSA)",
        "nace_codes_requested": NACE4_SUBSECTORS,
        "volume_yoy_by_sector": prod_yoy,
        "price_yoy_by_sector": price_yoy,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info(
        "Sub-sector YoY saved to %s (volume=%d, prices=%d sectors)",
        out, len(prod_yoy), len(price_yoy),
    )
    return out


def fetch_precrisis_by_country(baselines_dir: Path) -> Path:
    """Compute 2014-2019 production average per country (I21 via I15 overlap).

    Saves data/baselines/precrisis_by_country.json. Cached forever — only
    re-run when the Eurostat revision policy materially changes.
    """
    baselines_dir.mkdir(parents=True, exist_ok=True)
    out = baselines_dir / "precrisis_by_country.json"
    if out.exists():
        logger.info("Precrisis-by-country baseline already at %s", out)
        return out

    logger.info("Computing precrisis-by-country baseline (2014-2019 I15 → I21)...")

    i15_averages: dict[str, float] = {}
    conversion_factors: dict[str, float] = {}

    for ctry in TOP7_COUNTRIES:
        i15_data = _api_call("sts_inpr_m", {
            "geo": ctry, "nace_r2": "C20",
            "unit": "I15", "s_adj": "SCA",
            "sinceTimePeriod": "2014-01", "untilTimePeriod": "2019-12",
        })
        i15_values = _parse_single_dim(i15_data)
        vals = [v for v in i15_values.values() if v is not None]
        if not vals:
            logger.warning("No I15 data for %s, skipping", ctry)
            continue
        i15_averages[ctry] = sum(vals) / len(vals)

        # Overlap year 2021 for country-specific conversion factor
        try:
            i15_2021 = _parse_single_dim(_api_call("sts_inpr_m", {
                "geo": ctry, "nace_r2": "C20", "unit": "I15", "s_adj": "SCA",
                "sinceTimePeriod": "2021-01", "untilTimePeriod": "2021-12",
            }))
            i21_2021 = _parse_single_dim(_api_call("sts_inpr_m", {
                "geo": ctry, "nace_r2": "C20", "unit": "I21", "s_adj": "SCA",
                "sinceTimePeriod": "2021-01", "untilTimePeriod": "2021-12",
            }))
            common = set(i15_2021) & set(i21_2021)
            ratios = [
                i21_2021[m] / i15_2021[m]
                for m in common
                if i15_2021.get(m) and i21_2021.get(m)
            ]
            if ratios:
                conversion_factors[ctry] = sum(ratios) / len(ratios)
            else:
                conversion_factors[ctry] = 1.0
        except Exception as exc:
            logger.warning("Conversion factor for %s failed (%s); using 1.0", ctry, exc)
            conversion_factors[ctry] = 1.0

    precrisis_i21 = {
        ctry: round(i15_averages[ctry] * conversion_factors.get(ctry, 1.0), 1)
        for ctry in i15_averages
    }
    result = {
        "source": "Eurostat sts_inpr_m I15 2014-2019 with country-level I15→I21 overlap (2021)",
        "overlap_year": 2021,
        "precrisis_avg_i21_by_country": precrisis_i21,
        "conversion_factor_by_country": {k: round(v, 4) for k, v in conversion_factors.items()},
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Precrisis-by-country baseline saved: %s", precrisis_i21)
    return out


def fetch_jan2020_by_country(baselines_dir: Path) -> Path:
    """Fetch the Jan 2020 production index per country (I21 direct, SCA).

    Saves data/baselines/jan2020_by_country.json.
    """
    baselines_dir.mkdir(parents=True, exist_ok=True)
    out = baselines_dir / "jan2020_by_country.json"
    if out.exists():
        logger.info("Jan 2020 baseline already at %s", out)
        return out

    logger.info("Fetching Jan 2020 production index per country...")
    data = _api_call("sts_inpr_m", {
        "_geo_list": TOP7_COUNTRIES,
        "nace_r2": "C20", "unit": "I21", "s_adj": "SCA",
        "sinceTimePeriod": "2020-01", "untilTimePeriod": "2020-01",
    })
    by_country = _parse_multi_dim(data, "geo")
    jan2020 = {
        ctry: round(float(series.get("2020-01")), 1)
        for ctry, series in by_country.items()
        if series.get("2020-01") is not None
    }
    result = {
        "source": "Eurostat sts_inpr_m (I21, SCA), 2020-01",
        "jan_2020_i21_by_country": jan2020,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    logger.info("Jan 2020 baseline saved: %s", jan2020)
    return out
