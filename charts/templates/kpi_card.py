"""
KPI card for the macro brief, L5.

Renders a standalone SVG: label (top), big primary value, delta
coloured by direction, optional 12-month sparkline at the bottom.
The macro brief layout assembles 3 or 4 of these in a 2x2 grid
CSS-side (Astro template), not here.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from charts.style import CEFIC_COLORS, FONT_STACK

DIRECTION_COLOR = {
    "up":   CEFIC_COLORS["positive"],
    "down": CEFIC_COLORS["negative"],
    "flat": CEFIC_COLORS["benchmark"],
}


def render(
    label: str,
    primary_value,
    primary_unit: str,
    delta_value: float,
    delta_unit: str,
    direction: str,
    output_path: Path,
    sparkline_data: list = None,
    dims: tuple = (280, 160),
    dpi: int = 96,
):
    """Render a single KPI card to an SVG file.

    label          : e.g. "Chemical output"
    primary_value  : numeric or already-formatted string (e.g. 79.3 or "79.3")
    primary_unit   : e.g. "index 2021=100", "€ bn", "%"
    delta_value    : signed numeric, e.g. -3.9
    delta_unit     : e.g. "% YoY", "€ bn YoY", "pp YoY"
    direction      : "up" | "down" | "flat"
    sparkline_data : optional list of floats (any length, typically 12)
    dims           : (width_px, height_px)
    """
    width_in = dims[0] / dpi
    height_in = dims[1] / dpi

    fig = plt.figure(figsize=(width_in, height_in), dpi=dpi)
    fig.patch.set_facecolor("white")

    # Use a full-figure axes without visible elements, we paint text directly
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Card border
    from matplotlib.patches import Rectangle
    border = Rectangle((0.02, 0.02), 0.96, 0.96, fill=False,
                       edgecolor=CEFIC_COLORS["grid"], linewidth=1.2)
    ax.add_patch(border)

    # Label (top-left)
    ax.text(0.06, 0.86, label, fontsize=9, color="#555555",
            fontfamily=FONT_STACK[0], fontweight="normal", va="top")

    # Primary value, format to string
    if isinstance(primary_value, (int, float)):
        value_str = f"{primary_value:.1f}" if isinstance(primary_value, float) else str(primary_value)
    else:
        value_str = str(primary_value)

    y_value = 0.58 if sparkline_data else 0.50
    ax.text(0.06, y_value, value_str, fontsize=26, color="#222222",
            fontfamily=FONT_STACK[0], fontweight="bold", va="center")

    # Primary unit (smaller, after the value)
    ax.text(0.06, y_value - 0.22, primary_unit, fontsize=8,
            color="#666666", fontfamily=FONT_STACK[0], va="top")

    # Delta (bottom area, colored)
    delta_color = DIRECTION_COLOR.get(direction, CEFIC_COLORS["benchmark"])
    arrow = {"up": "▲", "down": "▼", "flat": "–"}.get(direction, "–")
    sign = "+" if delta_value > 0 else ""
    delta_str = f"{arrow} {sign}{delta_value:+.1f} {delta_unit}".replace("+-", "-")
    if sparkline_data:
        ax.text(0.06, 0.15, delta_str, fontsize=10, color=delta_color,
                fontfamily=FONT_STACK[0], fontweight="bold", va="center")
    else:
        ax.text(0.06, 0.18, delta_str, fontsize=11, color=delta_color,
                fontfamily=FONT_STACK[0], fontweight="bold", va="center")

    # Sparkline, thin line chart in bottom-right corner
    if sparkline_data and len(sparkline_data) >= 2:
        vals = list(sparkline_data)
        lo, hi = min(vals), max(vals)
        rng = (hi - lo) or 1
        normalised = [(v - lo) / rng for v in vals]
        n = len(normalised)

        x0, x1 = 0.45, 0.94
        y0, y1 = 0.08, 0.32
        xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
        ys = [y0 + (y1 - y0) * v for v in normalised]

        ax.plot(xs, ys, color=delta_color, linewidth=1.4)
        ax.fill_between(xs, [y0] * n, ys, color=delta_color, alpha=0.12)
        # Endpoint dot
        ax.plot(xs[-1], ys[-1], marker="o", markersize=4,
                markerfacecolor=delta_color, markeredgecolor="white", markeredgewidth=0.8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return output_path
