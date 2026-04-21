"""
Comext Parquet reader for Iris — STUB until Yaghi access.

Contract:
  - read_parquet(month, cache_dir) → Path to trade.json in cache
  - Reads 3 Parquet files from $COMEXT_DATA_PATH (fact + partner_dim + product_dim)
  - If COMEXT_DATA_PATH not set or files missing: writes trade_unavailable.json
  - Iris NEVER queries PostgreSQL or runs the Comext ETL pipeline

This module is a documented stub. When Yaghi is available, implement the
actual Parquet reading with pyarrow/pandas, filtering flow=1 (imports)
and flow=2 (exports), aggregating by period/partner/chapter_cn.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("iris.fetchers.comext")


def read_parquet(month: str, cache_dir: Path) -> Path:
    """Read Comext Parquet files for the given month.

    Returns path to the cached trade.json, or trade_unavailable.json
    if the data source is not accessible.
    """
    comext_path = os.environ.get("COMEXT_DATA_PATH")

    if not comext_path:
        logger.warning("COMEXT_DATA_PATH not set. Trade sections will be skipped.")
        return _write_unavailable(cache_dir, "COMEXT_DATA_PATH environment variable not set")

    parquet_dir = Path(comext_path)
    fact_file = parquet_dir / "comext_export.parquet"

    if not fact_file.exists():
        logger.warning(f"Comext fact file not found at {fact_file}. Trade sections will be skipped.")
        return _write_unavailable(cache_dir, f"comext_export.parquet not found at {parquet_dir}")

    # TODO: Implement actual Parquet reading when Yaghi is available
    # Steps:
    #   1. Read comext_export.parquet with pyarrow
    #   2. Filter: declarant='EU', period matches month
    #   3. Split: flow=2 (exports), flow=1 (imports)
    #   4. Aggregate by partner, by chapter_cn
    #   5. Join partner_dim.parquet for labels
    #   6. Produce trade_exports and trade_imports structures
    #   7. Save to cache_dir/trade.json

    logger.error("Comext Parquet reading not yet implemented. Returning unavailable.")
    return _write_unavailable(cache_dir, "Parquet reading not yet implemented (stub)")


def _write_unavailable(cache_dir: Path, reason: str) -> Path:
    """Write a trade_unavailable.json marker file."""
    out = cache_dir / "trade_unavailable.json"
    out.write_text(json.dumps({
        "status": "unavailable",
        "reason": reason,
        "sections_affected": ["trade_exports", "trade_imports"],
    }, indent=2), encoding="utf-8")
    return out
