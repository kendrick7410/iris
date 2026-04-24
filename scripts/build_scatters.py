"""
Phase A orchestrator for Iris analytical scatters.

Builds the 4 scatters defined in analysis/scatters/, saves their JSON
payloads under data/processed/{month}/scatters/, renders their SVG under
site/public/charts/{month}/, and prints a recap table with each
scatter's signal_strength so the editor can eyeball the ranking.

Run:
  .venv/bin/python -m scripts.build_scatters --month 2026-02

Not wired into pipelines/monthly_run.py. Phase C will decide whether to
integrate after visual review.

Assumes these cached files already exist under data/cache/{month}/
(run the fetchers first if missing):
  - production.json             (existing)
  - bcs.json                    (eurostat.fetch_bcs_cu)
  - subsectors.json             (eurostat.fetch_subsectors)
  - country_trade_balance.json  (comext.fetch_country_trade_balance)

And these global baselines under data/baselines/:
  - precrisis_by_country.json   (eurostat.fetch_precrisis_by_country)
  - jan2020_by_country.json     (eurostat.fetch_jan2020_by_country)

If any is missing, the corresponding scatter raises FileNotFoundError
with a pointer to the right fetcher call.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from analysis.scatters import SCATTERS
from charts.templates.scatter import render


LOG = logging.getLogger("iris.scatters.build")

DEFAULT_CACHE_DIR = Path("data/cache")
DEFAULT_BASELINES_DIR = Path("data/baselines")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_CHARTS_DIR = Path("site/public/charts")


def build_all(month: str, *,
              cache_dir: Path = DEFAULT_CACHE_DIR,
              baselines_dir: Path = DEFAULT_BASELINES_DIR,
              processed_dir: Path = DEFAULT_PROCESSED_DIR,
              charts_dir: Path = DEFAULT_CHARTS_DIR,
              parquet_path: str | None = None,
              fail_fast: bool = False) -> list[dict]:
    """Build all 4 scatters and return a summary list.

    Each entry is a dict with keys:
      scatter_id, title, signal_strength, signal_explanation,
      n_points, svg_path, json_path, status, error (optional)
    """
    month_cache = cache_dir / month
    month_processed = processed_dir / month / "scatters"
    month_charts = charts_dir / month
    month_processed.mkdir(parents=True, exist_ok=True)
    month_charts.mkdir(parents=True, exist_ok=True)

    year = int(month.split("-")[0])

    config_by_scatter = {
        "cu_trade":      {"cache_dir": month_cache},
        "price_volume":  {"cache_dir": month_cache},
        "trajectory":    {"cache_dir": month_cache, "baselines_dir": baselines_dir},
        "concentration": {"cache_dir": month_cache,
                          "parquet_path": parquet_path
                              or "/home/jme/comext-etl/comext_export.parquet"},
    }

    results: list[dict] = []
    for sid, module in SCATTERS.items():
        json_path = month_processed / f"scatter_{sid}.json"
        svg_path = month_charts / f"scatter_{sid}.svg"
        LOG.info("Building scatter %s …", sid)
        try:
            sd = module.compute(month, config_by_scatter[sid])
            sd.to_json_file(json_path)
            render(sd, svg_path, source_year=year)
            results.append({
                "scatter_id": sid,
                "title": sd.title,
                "signal_strength": sd.signal_strength,
                "signal_explanation": sd.signal_explanation,
                "n_points": len(sd.points),
                "json_path": str(json_path),
                "svg_path": str(svg_path),
                "status": "ok",
            })
            LOG.info(
                "  ✓ %s | signal=%.3f | n_points=%d | svg=%s",
                sid, sd.signal_strength, len(sd.points), svg_path,
            )
        except Exception as exc:
            LOG.exception("  ✗ %s failed: %s", sid, exc)
            results.append({
                "scatter_id": sid,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            if fail_fast:
                raise

    return results


def print_summary(results: list[dict]) -> None:
    """Print a compact recap table ranked by signal_strength."""
    print()
    print("=" * 90)
    print(f"{'scatter':<16} {'signal':>8} {'n_pts':>6} {'status':>8}  title")
    print("-" * 90)
    ok = sorted(
        (r for r in results if r["status"] == "ok"),
        key=lambda r: -r["signal_strength"],
    )
    for r in ok:
        print(f"{r['scatter_id']:<16} {r['signal_strength']:>8.3f} "
              f"{r['n_points']:>6d} {'ok':>8}  {r['title'][:60]}")
    for r in results:
        if r["status"] == "error":
            print(f"{r['scatter_id']:<16} {'-':>8} {'-':>6} {'ERROR':>8}  "
                  f"{r.get('error', '')[:60]}")
    print("=" * 90)
    print("Signal explanations:")
    for r in results:
        if r["status"] == "ok":
            print(f"  [{r['scatter_id']}] {r['signal_explanation']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="Edition month, e.g. 2026-02")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--baselines-dir", type=Path, default=DEFAULT_BASELINES_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--charts-dir", type=Path, default=DEFAULT_CHARTS_DIR)
    parser.add_argument("--parquet-path", default=None,
                        help="Override path to comext_export.parquet for Scatter 4")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Abort on first error instead of building the rest")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    results = build_all(
        args.month,
        cache_dir=args.cache_dir,
        baselines_dir=args.baselines_dir,
        processed_dir=args.processed_dir,
        charts_dir=args.charts_dir,
        parquet_path=args.parquet_path,
        fail_fast=args.fail_fast,
    )

    print_summary(results)

    n_errors = sum(1 for r in results if r["status"] == "error")
    return 0 if n_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
