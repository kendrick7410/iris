"""Horizontal bar chart for YoY country rankings."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from charts.style import CEFIC_COLORS, DEFAULT_DIMS, apply_style

COUNTRY_NAMES = {
    "DE": "Germany", "FR": "France", "IT": "Italy",
    "NL": "Netherlands", "ES": "Spain", "BE": "Belgium", "PL": "Poland",
}


def render(data: dict, title: str, output_path: Path, source_year: int):
    """Render a horizontal bar chart of YoY changes by country.

    data: dict of {"DE": {"yoy_pct": -3.5}, "FR": {"yoy_pct": 1.1}, ...}
    """
    items = sorted(data.items(), key=lambda x: x[1].get("yoy_pct") or 0)
    countries = [COUNTRY_NAMES.get(k, k) for k, _ in items]
    values = [v.get("yoy_pct", 0) for _, v in items]
    colors = [CEFIC_COLORS["negative"] if v < 0 else CEFIC_COLORS["positive"] for v in values]

    fig, ax = plt.subplots(figsize=(
        DEFAULT_DIMS["width_px"] / DEFAULT_DIMS["dpi"],
        DEFAULT_DIMS["height_px"] / DEFAULT_DIMS["dpi"],
    ), dpi=DEFAULT_DIMS["dpi"])

    bars = ax.barh(countries, values, color=colors, height=0.6)
    ax.axvline(x=0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Year-on-year change (%)", fontsize=9)

    for bar, val in zip(bars, values):
        x_pos = bar.get_width() + (0.3 if val >= 0 else -0.3)
        ha = "left" if val >= 0 else "right"
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2,
                f"{val:+.1f}%", va="center", ha=ha, fontsize=8, color="#333333")

    apply_style(ax, title=title, source_year=source_year)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)
