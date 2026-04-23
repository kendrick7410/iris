"""Eurostat STS release watcher for Iris.

Polls the three STS datasets (production, prices, turnover) via the
Eurostat dissemination API and triggers `pipelines/monthly_run.py` only
when the production reference month has advanced past the last
processed month.

    python scripts/release_watcher.py          # poll + trigger if new
    python scripts/release_watcher.py --dry-run # poll and report, do not trigger
    python scripts/release_watcher.py --force-month 2026-03  # override

State is persisted to `data/cache/_watcher_state.json`:
  {
    "last_processed_month": "2026-02",
    "last_check_utc": "2026-04-23T05:00:00+00:00",
    "last_seen": {
      "production": "2026-02",
      "prices":     "2026-02",
      "turnover":   "2026-01"
    }
  }
"""
import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE   = PROJECT_ROOT / "data" / "cache" / "_watcher_state.json"
BASE_URL     = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Same config as data/fetchers/eurostat.py DATASET_CONFIGS
DATASETS = {
    "production": ("sts_inpr_m",  "I21", "SCA"),
    "prices":     ("sts_inppd_m", "I21", "NSA"),
    "turnover":   ("sts_intv_m",  "I21", "SCA"),
}

logger = logging.getLogger("iris.release_watcher")


def fetch_latest_period(dataset: str, unit: str, s_adj: str,
                        retries: int = 3) -> str | None:
    """Return the latest YYYY-MM available for (dataset, unit, s_adj).

    Uses EU27 + C20 as the minimal query; the response carries every
    published reference month in `dimension.time.category.index`.
    """
    url = f"{BASE_URL}/{dataset}?geo=EU27_2020&nace_r2=C20&unit={unit}&s_adj={s_adj}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read())
            idx = data.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
            periods = sorted(idx.keys())
            if not periods:
                return None
            # Only count periods that actually have a value (Eurostat can
            # list the header without a published figure)
            values = data.get("value", {})
            index_to_period = {v: k for k, v in idx.items()}
            published = [index_to_period[i] for i in sorted(int(k) for k in values.keys())]
            return max(published) if published else max(periods)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            wait = 2 ** (attempt + 1)
            logger.warning(f"{dataset}: attempt {attempt+1}/{retries} failed: {e}. Retry in {wait}s.")
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                logger.error(f"{dataset}: giving up after {retries} attempts.")
                return None


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def trigger_pipeline(month: str, dry_run: bool = False) -> int:
    """Run `pipelines/monthly_run.py --month M --force` and return exit code."""
    cmd = [sys.executable, "pipelines/monthly_run.py", "--month", month, "--force"]
    logger.info(f"{'(dry-run) ' if dry_run else ''}Would run: {' '.join(cmd)}")
    if dry_run:
        return 0
    logger.info(f"Triggering pipeline for {month}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    logger.info(f"Pipeline exit code: {result.returncode}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Poll and report, do not trigger the pipeline")
    parser.add_argument("--force-month", default=None,
                        help="Skip polling and force-trigger the pipeline for this month")
    parser.add_argument("--quiet", action="store_true",
                        help="Only log warnings and errors")
    args = parser.parse_args()

    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stderr,
    )

    if args.force_month:
        logger.info(f"--force-month {args.force_month}: bypassing poll.")
        rc = trigger_pipeline(args.force_month, dry_run=args.dry_run)
        if rc == 0 and not args.dry_run:
            state = load_state()
            state["last_processed_month"] = args.force_month
            state["last_check_utc"] = datetime.now(timezone.utc).isoformat()
            save_state(state)
        return rc

    state = load_state()
    last_processed = state.get("last_processed_month")
    logger.info(f"Last processed month: {last_processed or '(none)'}")

    latest_by_key: dict[str, str | None] = {}
    for key, (ds, unit, sadj) in DATASETS.items():
        p = fetch_latest_period(ds, unit, sadj)
        latest_by_key[key] = p
        logger.info(f"{key:11} ({ds:12}): latest published = {p or 'N/A'}")

    production_latest = latest_by_key.get("production")

    state["last_check_utc"] = datetime.now(timezone.utc).isoformat()
    state["last_seen"] = latest_by_key

    if not production_latest:
        logger.warning("Could not determine the production latest period. Skipping trigger.")
        save_state(state)
        return 2

    if production_latest == last_processed:
        logger.info(f"No new production release (still at {production_latest}). Nothing to do.")
        save_state(state)
        return 0

    if last_processed and production_latest < last_processed:
        logger.warning(
            f"production latest ({production_latest}) is OLDER than last processed "
            f"({last_processed}). Possible revision? Skipping trigger."
        )
        save_state(state)
        return 0

    logger.info(
        f"Release detected: production advanced to {production_latest} "
        f"(was {last_processed or 'unset'}). Triggering pipeline."
    )
    rc = trigger_pipeline(production_latest, dry_run=args.dry_run)
    if rc == 0 and not args.dry_run:
        state["last_processed_month"] = production_latest
        save_state(state)
        logger.info(f"State updated: last_processed_month = {production_latest}")
    elif rc != 0:
        logger.error(f"Pipeline failed with exit code {rc}. State not advanced.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
