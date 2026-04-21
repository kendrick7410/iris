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

from analysis.anomaly_detector import detect_base_effects

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

    # Trade fiches (from Comext)
    trade_file = cache_dir / "trade.json"
    trade_marker = cache_dir / "trade_unavailable.json"
    if trade_file.exists():
        for section_type in ("trade_exports", "trade_imports"):
            fiche = _build_trade_fiche(trade_file, section_type)
            if fiche is None:
                continue
            out = processed_dir / f"{section_type}.json"
            out.write_text(json.dumps(fiche, indent=2), encoding="utf-8")
            logger.info(f"Fiche {section_type} saved to {out}")
            produced.append(out)
    elif trade_marker.exists():
        reason = json.loads(trade_marker.read_text(encoding="utf-8")).get("reason", "unknown")
        logger.info(f"Trade data unavailable — trade sections skipped ({reason})")

    # Enrich fiches with anomaly reports (base-effect guard)
    enrich_with_anomalies(produced, cache_dir)

    return produced


def enrich_with_anomalies(fiche_paths: list, cache_dir: Path) -> None:
    """Attach an `anomaly_report` block to each fiche.

    The detector is pure; this wrapper assembles inputs per fiche:
      - historical_series from cache/trade.json monthly_history (trade sections)
        or from cache/{production,prices}.json (STS sections)
      - related_indicators from sibling fiches (IPI YoY for trade, etc.)

    Writes the enriched fiche back in place. No-op on fiches where no flags fire.
    """
    # Load trade cache once (used for trade fiches' historical series)
    trade_file = cache_dir / "trade.json"
    trade_history = {}
    if trade_file.exists():
        raw = json.loads(trade_file.read_text(encoding="utf-8"))
        trade_history = raw.get("monthly_history", {})

    # Index fiches by section type for cross-references
    fiches_by_type = {}
    for fp in fiche_paths:
        try:
            f = json.loads(fp.read_text(encoding="utf-8"))
            fiches_by_type[f["section_type"]] = (fp, f)
        except Exception as e:
            logger.warning(f"Failed to load fiche {fp}: {e}")

    related = _collect_related_indicators(fiches_by_type)

    for section_type, (fp, fiche) in fiches_by_type.items():
        hist = _historical_series_for(section_type, trade_history, fiches_by_type, cache_dir)
        report = detect_base_effects(fiche, hist, related)
        if report.flags:
            fiche["anomaly_report"] = report.to_dict()
            fp.write_text(json.dumps(fiche, indent=2), encoding="utf-8")
            logger.info(
                f"Anomaly report for {section_type}: severity={report.severity}, "
                f"flags={report.flags}"
            )


def _collect_related_indicators(fiches_by_type: dict) -> dict:
    """Gather cross-section YoY figures used by detectors (D1)."""
    related = {}
    out = fiches_by_type.get("output")
    if out:
        py = (out[1].get("data") or {}).get("previous_year") or {}
        if py.get("delta_pct") is not None:
            related["output_ipi_yoy_pct"] = py["delta_pct"]
    pri = fiches_by_type.get("prices")
    if pri:
        py = (pri[1].get("data") or {}).get("previous_year") or {}
        if py.get("delta_pct") is not None:
            related["prices_ppi_yoy_pct"] = py["delta_pct"]
    return related


def _historical_series_for(section_type: str, trade_history: dict,
                            fiches_by_type: dict, cache_dir: Path) -> dict:
    """Return a {'eu27_total': {'YYYY-MM': value, ...}} structure per section."""
    if section_type == "trade_exports":
        return {
            "eu27_total": (trade_history.get("exports") or {}).get("eu27_total", {}),
            "by_partner": (trade_history.get("exports") or {}).get("by_partner", {}),
        }
    if section_type == "trade_imports":
        return {
            "eu27_total": (trade_history.get("imports") or {}).get("eu27_total", {}),
            "by_partner": (trade_history.get("imports") or {}).get("by_partner", {}),
        }
    # STS sections: pull the EU27 monthly series from the cache JSON
    cache_map = {"output": "production.json", "prices": "prices.json", "sales": "turnover.json"}
    cache_name = cache_map.get(section_type)
    if not cache_name:
        return {}
    cache_file = cache_dir / cache_name
    if not cache_file.exists():
        return {}
    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    return {"eu27_total": raw.get("eu27") or {}}


def build_macro_brief_fiche(fiches_dir: Path, cache_dir: Path) -> Path:
    """Assemble the macro_brief fiche from existing fiches + trade.json.

    Reads output / prices / trade_exports / trade_imports fiches and picks 3 or 4
    KPIs: output YoY, trade balance YoY, producer prices YoY, capacity
    utilisation YoY (if available). Computes headline flags for Pareto
    concentration and volume/value divergence.

    Returns Path to macro_brief.json (in fiches_dir).
    """
    kpis = []
    headline = {}

    # KPI 1 — Output YoY (from output fiche)
    out_path = fiches_dir / "output.json"
    if out_path.exists():
        out = json.loads(out_path.read_text(encoding="utf-8"))
        cur = out["data"]["current"]
        pr = out["data"].get("previous_year") or {}
        delta = pr.get("delta_pct")
        if delta is not None:
            kpis.append({
                "key": "output_yoy",
                "label": "Chemical output",
                "primary_value": cur.get("value"),
                "primary_unit": cur.get("unit", "index 2021=100"),
                "delta_value": delta,
                "delta_unit": "% YoY",
                "direction": _direction(delta),
                "source_fiche": "output",
            })

    # KPI 2 — Trade balance YoY (exports - imports, from trade fiches)
    exp_path = fiches_dir / "trade_exports.json"
    imp_path = fiches_dir / "trade_imports.json"
    if exp_path.exists() and imp_path.exists():
        exp = json.loads(exp_path.read_text(encoding="utf-8"))
        imp = json.loads(imp_path.read_text(encoding="utf-8"))
        exp_cur = exp["data"]["current"].get("value_eur_bn") or 0
        imp_cur = imp["data"]["current"].get("value_eur_bn") or 0
        exp_prev = exp["data"]["previous_year"].get("value_eur_bn") or 0
        imp_prev = imp["data"]["previous_year"].get("value_eur_bn") or 0
        balance_cur = round(exp_cur - imp_cur, 2)
        balance_prev = round(exp_prev - imp_prev, 2)
        balance_delta = round(balance_cur - balance_prev, 2)
        kpis.append({
            "key": "trade_balance_yoy",
            "label": "Trade balance",
            "primary_value": balance_cur,
            "primary_unit": "€ bn",
            "delta_value": balance_delta,
            "delta_unit": "€ bn YoY",
            "direction": _direction(balance_delta),
            "source_fiche": "trade_exports|trade_imports",
        })

    # KPI 3 — Producer prices YoY (from prices fiche)
    pri_path = fiches_dir / "prices.json"
    if pri_path.exists():
        pri = json.loads(pri_path.read_text(encoding="utf-8"))
        cur = pri["data"]["current"]
        pr = pri["data"].get("previous_year") or {}
        delta = pr.get("delta_pct")
        if delta is not None:
            kpis.append({
                "key": "prices_yoy",
                "label": "Producer prices",
                "primary_value": cur.get("value"),
                "primary_unit": cur.get("unit", "index 2021=100"),
                "delta_value": delta,
                "delta_unit": "% YoY",
                "direction": _direction(delta),
                "source_fiche": "prices",
            })

    # KPI 4 — Capacity utilisation YoY (optional, from capacity fiche if present)
    cap_path = fiches_dir / "capacity.json"
    if cap_path.exists():
        cap = json.loads(cap_path.read_text(encoding="utf-8"))
        cur = cap.get("data", {}).get("current") or {}
        pr = cap.get("data", {}).get("previous_year") or {}
        delta = pr.get("delta_pp") if pr.get("delta_pp") is not None else pr.get("delta_pct")
        if delta is not None:
            kpis.append({
                "key": "capacity_yoy",
                "label": "Capacity utilisation",
                "primary_value": cur.get("value"),
                "primary_unit": cur.get("unit", "%"),
                "delta_value": delta,
                "delta_unit": "pp YoY",
                "direction": _direction(delta),
                "source_fiche": "capacity",
            })

    # Headline data — Pareto concentration (from exports fiche)
    if exp_path.exists():
        exp = json.loads(exp_path.read_text(encoding="utf-8"))
        partners = exp["data"].get("by_partner") or []
        if partners:
            top5_share = round(sum((p.get("share_pct") or 0) for p in partners[:5]), 1)
            if top5_share >= 50:
                top5_labels = [p.get("label", p.get("partner", "")) for p in partners[:5]]
                headline["concentration_pareto"] = {
                    "top_n": 5,
                    "share_pct": top5_share,
                    "entities": top5_labels,
                    "scope": f"top-5 export partners cover {top5_share}% of value",
                }

    # Headline data — volume/value divergence (from exports fiche YoY)
    if exp_path.exists():
        exp = json.loads(exp_path.read_text(encoding="utf-8"))
        pr = exp["data"].get("previous_year") or {}
        dv = pr.get("delta_pct_value")
        dvol = pr.get("delta_pct_volume")
        if dv is not None and dvol is not None and abs(dv - dvol) >= 3:
            headline["volume_value_divergence"] = {
                "volume_pct": dvol,
                "value_pct": dv,
                "gap_pp": round(dv - dvol, 1),
                "scope": "exports, year-on-year",
            }

    # Period — pick from any available fiche
    period = None
    for p in (out_path, pri_path, exp_path, imp_path):
        if p.exists():
            period = json.loads(p.read_text(encoding="utf-8"))["period"]
            break

    fiche = {
        "section_type": "macro_brief",
        "period": period or {"month": "unknown"},
        "kpis": kpis,
        "headline_data": headline,
        "source": "Cefic analysis based on Eurostat data and Comext (" +
                  str(date.today().year) + ")",
    }

    out = fiches_dir / "macro_brief.json"
    out.write_text(json.dumps(fiche, indent=2), encoding="utf-8")
    logger.info(f"Macro brief fiche saved to {out} ({len(kpis)} KPIs, "
                f"{len(headline)} headline flags)")
    return out


def _direction(delta):
    if delta is None:
        return "flat"
    if delta > 0.1:
        return "up"
    if delta < -0.1:
        return "down"
    return "flat"


def _build_trade_fiche(trade_file: Path, section_type: str) -> dict:
    """Convert cache/trade.json (raw aggregates) into a section fiche (schema §10)."""
    raw = json.loads(trade_file.read_text(encoding="utf-8"))
    flow_key = "exports" if section_type == "trade_exports" else "imports"
    flow = raw.get("flows", {}).get(flow_key)
    if not flow or not flow.get("current"):
        return None

    month = raw["month"]
    year, month_num = month.split("-")
    month_num = int(month_num)
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    window = (f"{month_names[0]}-{month_names[month_num - 1]} {year}"
              if month_num > 1 else f"{month_names[0]} {year}")
    window_ordinal = _ordinal(month_num) if month_num > 1 else None

    direction = "exports" if section_type == "trade_exports" else "imports"
    # Waterfall chart is emitted only if at least one key partner has a drill_down.
    # Stacked-bars NACE chart is deferred — requires by_year_by_nace aggregation
    # in trade.json, planned for a follow-up commit.
    has_drill = any(p.get("drill_down") for p in flow.get("by_partner", []))
    chart_ids = [f"trade_{direction}_waterfall_cn8"] if has_drill else []

    return {
        "section_type": section_type,
        "period": {
            "month": month,
            "publication_date": date.today().isoformat(),
            "window": window,
            "window_months": month_num,
            "window_ordinal": window_ordinal,
        },
        "data": {
            "current": {
                **flow["current"],
                "unit_value": "€ bn",
                "unit_volume": "kt",
                "scope": raw.get("scope", "Extra-EU27 trade"),
            },
            "previous_year": flow["previous_year"],
            "ytd": flow["ytd"],
            "five_year_window": flow.get("five_year_window"),
            "by_partner": flow["by_partner"],
            "by_chapter": flow["by_chapter"],
            "key_partners": raw.get("key_partners", []),
            "source": f"Cefic analysis based on Comext data (Eurostat, {date.today().year})",
        },
        "charts": chart_ids,
        "editorial_context": {
            "latest_structural_break": "March 2022",
            "notable_events": ["US tariff measures since March 2025"],
            "scope_note": raw.get("scope", ""),
            "narrative_hints": {
                "apply_volume_value_duality": True,
                "apply_pareto_if_concentrated": True,
                "apply_drilldown_for_key_partners": has_drill,
            },
        },
    }
