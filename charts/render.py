"""
Chart renderer orchestrator for Iris.

Contract:
  - render_charts(fiches_dir, output_dir) → list of SVG paths
  - Reads fiche JSONs, dispatches to appropriate chart template
  - Produces SVGs in site/public/charts/YYYY-MM/
"""

import json
import logging
from pathlib import Path

from charts.templates import index_timeseries, yoy_bars, sector_comparison

logger = logging.getLogger("iris.charts")

CHART_DISPATCHERS = {
    "output_index": ("index_timeseries", "EU27 chemical output (index 2021=100)"),
    "output_yoy_country": ("yoy_bars", "EU27 chemical production by country (YoY %)"),
    "prices_index": ("index_timeseries", "EU27 chemical producer prices (index 2021=100)"),
    "prices_yoy_country": ("yoy_bars", "EU27 chemical producer prices by country (YoY %)"),
    "turnover_index": ("index_timeseries", "EU27 chemical turnover (index 2021=100)"),
    "turnover_yoy_country": ("yoy_bars", "EU27 chemical turnover by country (YoY %)"),
}


def render_charts(fiches_dir: Path, output_dir: Path) -> list:
    """Render all charts for all fiches in the directory.

    Returns list of paths to generated SVG files.
    """
    produced = []

    for fiche_path in sorted(fiches_dir.glob("*.json")):
        fiche = json.loads(fiche_path.read_text(encoding="utf-8"))
        chart_ids = fiche.get("charts", [])
        year = int(fiche["period"]["month"].split("-")[0])
        data = fiche.get("data", {})

        for chart_id in chart_ids:
            if chart_id not in CHART_DISPATCHERS:
                logger.warning(f"Unknown chart_id '{chart_id}', skipping")
                continue

            template_name, title = CHART_DISPATCHERS[chart_id]
            svg_path = output_dir / f"{chart_id}.svg"

            try:
                if template_name == "index_timeseries":
                    # Use EU27 timeseries from the cache data
                    ts_data = data.get("current", {})
                    # Build a mini timeseries from current + previous_year
                    ts = {}
                    if data.get("previous_year", {}).get("period") and data["previous_year"].get("value"):
                        ts[data["previous_year"]["period"]] = data["previous_year"]["value"]
                    if data["current"].get("period") and data["current"].get("value"):
                        ts[data["current"]["period"]] = data["current"]["value"]
                    # Add YTD points if available
                    if data.get("ytd"):
                        pass  # YTD is an average, not a point — skip for timeseries

                    if len(ts) >= 2:
                        index_timeseries.render(ts, title, svg_path, year)
                        produced.append(svg_path)
                        logger.info(f"Chart {chart_id} → {svg_path}")
                    else:
                        logger.warning(f"Not enough timeseries points for {chart_id}")

                elif template_name == "yoy_bars":
                    country_data = data.get("by_country")
                    if country_data:
                        yoy_bars.render(country_data, title, svg_path, year)
                        produced.append(svg_path)
                        logger.info(f"Chart {chart_id} → {svg_path}")

                elif template_name == "sector_comparison":
                    sector_data = data.get("by_sector")
                    if sector_data:
                        sector_comparison.render(sector_data, title, svg_path, year)
                        produced.append(svg_path)
                        logger.info(f"Chart {chart_id} → {svg_path}")

            except Exception as e:
                logger.error(f"Chart {chart_id} failed: {e}")

    return produced
