"""Build the peers_series fiche from the raw cached Eurostat production /
prices / turnover data.

The fiche is what the Astro "Chemicals versus peers" page consumes at
build time. Cache lives in `data/cache/{id}/` (gitignored, dev-only)
while fiches under `data/processed/{id}/fiches/` are versioned, so this
script bridges the two: it reads the cache once per edition and writes
a stable, committable fiche.

Usage:
    python scripts/build_peers_fiche.py --month 2026-02
    python scripts/build_peers_fiche.py --all   # every edition with cache
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Reuse the Eurostat fetcher's API call helper for the YoY extension.
sys.path.insert(0, str(PROJECT_ROOT))
from data.fetchers.eurostat import _api_call, _parse_single_dim  # noqa: E402

EXTENDED_HISTORY_MONTHS = 30  # gives us 18 YoY points after subtracting 12

logger = logging.getLogger("iris.build_peers_fiche")

NACE_LABELS = {
    "C":   {"key": "manufacturing",    "label": "Manufacturing total"},
    "C20": {"key": "chemicals",        "label": "Chemicals (C20)"},
    "C21": {"key": "pharmaceuticals",  "label": "Pharmaceuticals (C21)"},
    "C24": {"key": "basic_metals",     "label": "Basic metals (C24)"},
    "C29": {"key": "motor_vehicles",   "label": "Motor vehicles (C29)"},
}


def _series_for(by_sector: dict, code: str, months: list[str]) -> list[float | None]:
    """Return the value for each month in `months`, or None if missing."""
    series = by_sector.get(code, {}) or {}
    return [series.get(m) for m in months]


def _load(path: Path) -> dict | None:
    if not path.exists():
        logger.warning("Missing cache file: %s", path)
        return None
    return json.loads(path.read_text())


def _shift_month(month: str, delta: int) -> str:
    """'2026-02' shifted by delta months."""
    y, m = (int(x) for x in month.split("-"))
    total = y * 12 + (m - 1) + delta
    ny, nm = divmod(total, 12)
    return f"{ny:04d}-{nm + 1:02d}"


def _fetch_extended_series(dataset: str, unit: str, s_adj: str,
                           geo: str, nace: str, since_month: str) -> dict[str, float]:
    """One-shot Eurostat call with a single geo / single nace, returning
    `{period: value}` for every published month from `since_month`."""
    data = _api_call(dataset, {
        "geo": geo, "nace_r2": nace,
        "unit": unit, "s_adj": s_adj,
        "sinceTimePeriod": since_month,
    })
    return _parse_single_dim(data)


def _yoy_series(series: dict[str, float], months: list[str]) -> list[float | None]:
    """Compute YoY % per month: 100 * (M / M-12 - 1). None when either side
    is missing or zero."""
    out: list[float | None] = []
    for m in months:
        anchor = _shift_month(m, -12)
        cur = series.get(m)
        prev = series.get(anchor)
        if cur is None or prev is None or prev == 0:
            out.append(None)
        else:
            out.append(round(100.0 * (cur - prev) / prev, 1))
    return out


def _common_months(*sources: dict | None) -> list[str]:
    """Return the union of months that appear in every present source."""
    sets = []
    for s in sources:
        if s is None:
            continue
        # production / prices / turnover all use eu27 as the canonical series
        eu27 = s.get("eu27", {}) or {}
        sets.append(set(eu27.keys()))
    if not sets:
        return []
    return sorted(set.union(*sets))


def build(month: str, extended_history: bool = True) -> Path:
    cache = CACHE_DIR / month
    prod = _load(cache / "production.json")
    prices = _load(cache / "prices.json")
    turn = _load(cache / "turnover.json")

    if not (prod and prices and turn):
        raise FileNotFoundError(
            f"Need production.json + prices.json + turnover.json under {cache}; "
            "run the eurostat fetchers first."
        )

    months = _common_months(prod, prices, turn)
    if not months:
        raise RuntimeError(f"No overlapping months across the three datasets for {month}.")

    prod_by_sector = prod.get("by_sector", {}) or {}
    prices_by_sector = prices.get("by_sector", {}) or {}
    turn_by_sector = turn.get("by_sector", {}) or {}

    production = {
        NACE_LABELS[c]["key"]: _series_for(prod_by_sector, c, months)
        for c in ("C", "C20", "C21", "C24", "C29")
    }
    prices_block = {
        "chemicals":     _series_for(prices_by_sector, "C20", months),
        "manufacturing": _series_for(prices_by_sector, "C",   months),
    }
    sales_block = {
        "chemicals":     _series_for(turn_by_sector, "C20", months),
    }

    # YoY blocks need 12 months of history before the first plotted month.
    # The main Eurostat fetcher only keeps ~14 months in cache; if we want
    # YoY across the full window, refetch directly with a longer
    # `sinceTimePeriod`. Cached on disk by `since_month` so re-runs are
    # cheap.
    production_yoy: dict | None = None
    prices_yoy: dict | None = None
    sales_yoy: dict | None = None
    if extended_history:
        since_month = _shift_month(month, -(EXTENDED_HISTORY_MONTHS - 1))
        logger.info("Fetching extended 30m history since %s for YoY series…", since_month)

        ext_prod: dict[str, dict[str, float]] = {}
        for code in ("C", "C20", "C21", "C24", "C29"):
            ext_prod[code] = _fetch_extended_series(
                "sts_inpr_m", "I21", "SCA", "EU27_2020", code, since_month,
            )
        ext_prices_c20 = _fetch_extended_series(
            "sts_inppd_m", "I21", "NSA", "EU27_2020", "C20", since_month,
        )
        ext_prices_c = _fetch_extended_series(
            "sts_inppd_m", "I21", "NSA", "EU27_2020", "C", since_month,
        )
        ext_turn_c20 = _fetch_extended_series(
            "sts_intv_m", "I21", "SCA", "EU27_2020", "C20", since_month,
        )

        production_yoy = {
            NACE_LABELS[c]["key"]: _yoy_series(ext_prod[c], months)
            for c in ("C", "C20", "C21", "C24", "C29")
        }
        prices_yoy = {
            "chemicals":     _yoy_series(ext_prices_c20, months),
            "manufacturing": _yoy_series(ext_prices_c,   months),
        }
        sales_yoy = {
            "chemicals":     _yoy_series(ext_turn_c20, months),
        }

    # Cap at 24 trailing months when the dataset has more (parity with the
    # design canvas page; today the Eurostat fetcher writes 14 months but
    # the schema is forward-compatible).
    if len(months) > 24:
        months = months[-24:]
        production = {k: v[-24:] for k, v in production.items()}
        prices_block = {k: v[-24:] for k, v in prices_block.items()}
        sales_block  = {k: v[-24:] for k, v in sales_block.items()}
        if production_yoy: production_yoy = {k: v[-24:] for k, v in production_yoy.items()}
        if prices_yoy:     prices_yoy     = {k: v[-24:] for k, v in prices_yoy.items()}
        if sales_yoy:      sales_yoy      = {k: v[-24:] for k, v in sales_yoy.items()}

    current = months[-1] if months else None
    fiche = {
        "section_type": "peers_series",
        "period": month,
        "data": {
            "months": months,
            "labels": {
                "manufacturing":   NACE_LABELS["C"]["label"],
                "chemicals":       NACE_LABELS["C20"]["label"],
                "pharmaceuticals": NACE_LABELS["C21"]["label"],
                "basic_metals":    NACE_LABELS["C24"]["label"],
                "motor_vehicles":  NACE_LABELS["C29"]["label"],
            },
            "production": production,
            "prices": prices_block,
            "sales":  sales_block,
            "production_yoy": production_yoy,
            "prices_yoy": prices_yoy,
            "sales_yoy": sales_yoy,
            "current": {
                "month": current,
                "chemicals_production": production["chemicals"][-1] if current else None,
                "chemicals_prices":     prices_block["chemicals"][-1] if current else None,
                "chemicals_sales":      sales_block["chemicals"][-1]  if current else None,
                "chemicals_yoy_production":   (production_yoy["chemicals"][-1] if production_yoy and current else None),
                "manufacturing_yoy_production": (production_yoy["manufacturing"][-1] if production_yoy and current else None),
                "pharmaceuticals_yoy_production": (production_yoy["pharmaceuticals"][-1] if production_yoy and current else None),
                "basic_metals_yoy_production": (production_yoy["basic_metals"][-1] if production_yoy and current else None),
                "motor_vehicles_yoy_production": (production_yoy["motor_vehicles"][-1] if production_yoy and current else None),
            },
            "source": (
                "Eurostat sts_inpr_m + sts_inppd_m + sts_intv_m, NACE C / C20 / C21 / "
                "C24 / C29, EU27, I21, SCA where available."
            ),
        },
    }

    out_dir = PROCESSED_DIR / month / "fiches"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "peers_series.json"
    out_path.write_text(json.dumps(fiche, indent=2, ensure_ascii=False))
    logger.info("Wrote %s (%d months)", out_path, len(months))
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--month", help="Edition (YYYY-MM)")
    g.add_argument("--all", action="store_true", help="Every edition with cache")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.all:
        ids = sorted([d.name for d in CACHE_DIR.iterdir()
                      if d.is_dir() and d.name[:4].isdigit()])
        if not ids:
            print("No edition cache directories found.", file=sys.stderr)
            return 2
    else:
        ids = [args.month]

    failures = []
    for m in ids:
        try:
            print(build(m))
        except Exception as exc:
            print(f"✗ {m}: {exc}", file=sys.stderr)
            failures.append(m)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
