"""Line chart for index timeseries (output, prices, turnover)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from charts.style import CEFIC_COLORS, DEFAULT_DIMS, apply_style


def render(data: dict, title: str, output_path: Path, source_year: int):
    """Render an index timeseries line chart as SVG.

    data: dict of {"YYYY-MM": value, ...} for EU27 C20.
    """
    periods = sorted(data.keys())
    values = [data[p] for p in periods]
    labels = [p[5:] + "\n" + p[:4] if p.endswith("-01") or p == periods[0] else p[5:]
              for p in periods]

    fig, ax = plt.subplots(figsize=(
        DEFAULT_DIMS["width_px"] / DEFAULT_DIMS["dpi"],
        DEFAULT_DIMS["height_px"] / DEFAULT_DIMS["dpi"],
    ), dpi=DEFAULT_DIMS["dpi"])

    ax.plot(range(len(values)), values, color=CEFIC_COLORS["primary"],
            linewidth=2, marker="o", markersize=4)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=0, fontsize=8)
    ax.set_ylabel("Index (2021=100)", fontsize=9)

    apply_style(ax, title=title, source_year=source_year)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)
