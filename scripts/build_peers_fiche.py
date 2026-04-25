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


def build(month: str) -> Path:
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

    # Cap at 24 trailing months when the dataset has more (parity with the
    # design canvas page; today the Eurostat fetcher writes 14 months but
    # the schema is forward-compatible).
    if len(months) > 24:
        months = months[-24:]
        production = {k: v[-24:] for k, v in production.items()}
        prices_block = {k: v[-24:] for k, v in prices_block.items()}
        sales_block  = {k: v[-24:] for k, v in sales_block.items()}

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
            "current": {
                "month": current,
                "chemicals_production": production["chemicals"][-1] if current else None,
                "chemicals_prices":     prices_block["chemicals"][-1] if current else None,
                "chemicals_sales":      sales_block["chemicals"][-1]  if current else None,
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
