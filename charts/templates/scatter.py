"""
Generic scatter template for Iris Phase A analytical views.

Consumes an `analysis.scatters.base.ScatterData` and renders an 800×600
SVG with Cefic styling. Supports:
  - vertical / horizontal reference lines (`x_ref`, `y_ref`)
  - diagonal y = x (`diagonal: true`) with a legend annotation
  - multiple threshold lines per axis (`x_thresholds`, `y_thresholds`)
  - point labels with a light collision-avoidance heuristic

Design choices vs other Iris templates:
  - Points are kept uniform (no per-point colour encoding) so the
    reference lines carry the interpretive weight.
  - Labels are offset to the top-right of each point by default; when
    two points land within ~40px we alternate top-right / bottom-left
    to reduce overlap.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path

from charts.style import CEFIC_COLORS, FONT_STACK, format_source_line


SCATTER_DIMS = {"width_px": 800, "height_px": 600, "dpi": 96}


def render(scatter_data, output_path: Path, source_year: int):
    """Render a scatter to SVG.

    Parameters
    ----------
    scatter_data : analysis.scatters.base.ScatterData
    output_path : Path to the SVG file
    source_year : int, used in the Cefic source line footer
    """
    fig, ax = plt.subplots(
        figsize=(
            SCATTER_DIMS["width_px"] / SCATTER_DIMS["dpi"],
            SCATTER_DIMS["height_px"] / SCATTER_DIMS["dpi"],
        ),
        dpi=SCATTER_DIMS["dpi"],
    )

    xs = [p.x for p in scatter_data.points]
    ys = [p.y for p in scatter_data.points]

    ax.scatter(
        xs, ys,
        s=80,
        color=CEFIC_COLORS["primary"],
        edgecolor="#ffffff",
        linewidth=1.2,
        zorder=3,
    )

    # Reference lines
    refs = scatter_data.reference_lines or {}
    if "x_ref" in refs and refs["x_ref"] is not None:
        ax.axvline(
            x=refs["x_ref"],
            color=CEFIC_COLORS["benchmark"],
            linestyle="--",
            linewidth=0.8,
            zorder=1,
        )
        _annotate_ref(ax, x=refs["x_ref"], orientation="v", label=f"x = {refs['x_ref']:g}")
    if "y_ref" in refs and refs["y_ref"] is not None:
        ax.axhline(
            y=refs["y_ref"],
            color=CEFIC_COLORS["benchmark"],
            linestyle="--",
            linewidth=0.8,
            zorder=1,
        )
        _annotate_ref(ax, y=refs["y_ref"], orientation="h", label=f"y = {refs['y_ref']:g}")

    for th in refs.get("x_thresholds", []) or []:
        ax.axvline(
            x=th["value"],
            color=CEFIC_COLORS["benchmark"],
            linestyle=":",
            linewidth=0.7,
            zorder=1,
        )
        _annotate_ref(ax, x=th["value"], orientation="v", label=th.get("label", ""))
    for th in refs.get("y_thresholds", []) or []:
        ax.axhline(
            y=th["value"],
            color=CEFIC_COLORS["benchmark"],
            linestyle=":",
            linewidth=0.7,
            zorder=1,
        )
        _annotate_ref(ax, y=th["value"], orientation="h", label=th.get("label", ""))

    # Diagonal y = x, drawn across the plotted range.
    if refs.get("diagonal"):
        # Slightly pad so the diagonal doesn't brush the axes.
        lo = min(min(xs), min(ys))
        hi = max(max(xs), max(ys))
        pad = (hi - lo) * 0.05
        ax.plot(
            [lo - pad, hi + pad],
            [lo - pad, hi + pad],
            linestyle="--",
            color=CEFIC_COLORS["benchmark"],
            linewidth=0.8,
            zorder=1,
            label="y = x (no change)",
        )
        ax.legend(
            loc="lower right",
            frameon=False,
            fontsize=8,
            handlelength=2.0,
        )

    # Point labels with a simple alternation heuristic.
    _label_points(ax, scatter_data.points)

    # Axes
    ax.set_xlabel(scatter_data.x_axis_label, fontsize=10, fontweight="bold",
                  fontfamily=FONT_STACK[0])
    ax.set_ylabel(scatter_data.y_axis_label, fontsize=10, fontweight="bold",
                  fontfamily=FONT_STACK[0])

    # Title (avoid apply_style since scatters do not need a gridded y-axis)
    ax.set_title(
        scatter_data.title,
        fontsize=12, fontfamily=FONT_STACK[0], fontweight="bold",
        loc="left", pad=14,
    )
    ax.grid(color=CEFIC_COLORS["grid"], linewidth=0.5, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(CEFIC_COLORS["grid"])
    ax.spines["bottom"].set_color(CEFIC_COLORS["grid"])
    ax.tick_params(colors="#333333", labelsize=9)

    # Source line in footer
    source_text = format_source_line(source_year)
    fig.text(
        0.08, 0.025, source_text,
        fontsize=8, color="#666666", fontfamily=FONT_STACK[0],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)


def _annotate_ref(ax, x=None, y=None, orientation="v", label=""):
    """Place a small grey annotation next to a reference line."""
    if not label:
        return
    if orientation == "v":
        ax.annotate(
            label,
            xy=(x, ax.get_ylim()[1] if ax.get_ylim()[1] is not None else 0),
            xytext=(4, -8),
            textcoords="offset points",
            fontsize=7,
            color=CEFIC_COLORS["benchmark"],
            fontfamily=FONT_STACK[0],
            annotation_clip=True,
        )
    else:
        ax.annotate(
            label,
            xy=(ax.get_xlim()[1] if ax.get_xlim()[1] is not None else 0, y),
            xytext=(-4, 4),
            textcoords="offset points",
            fontsize=7,
            color=CEFIC_COLORS["benchmark"],
            fontfamily=FONT_STACK[0],
            ha="right",
            annotation_clip=True,
        )


def _label_points(ax, points):
    """Place labels near each point, alternating quadrant on collisions.

    Strategy:
      - sort points by x for stable placement
      - default offset: top-right (+6, +6)
      - if two consecutive points are close in (x, y), alternate with
        bottom-left (-6, -6). Good enough for 7-10 points; Phase B may
        swap in adjustText if point counts grow.
    """
    from itertools import combinations

    # Find pairs that are close in data coordinates; we'll flip one of
    # each close pair to the bottom-left offset.
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    if not xs:
        return
    span_x = max(xs) - min(xs) or 1.0
    span_y = max(ys) - min(ys) or 1.0
    close_thresh = 0.08  # fraction of the plotted range

    flip = {i: False for i in range(len(points))}
    for i, j in combinations(range(len(points)), 2):
        dx = abs(points[i].x - points[j].x) / span_x
        dy = abs(points[i].y - points[j].y) / span_y
        if dx < close_thresh and dy < close_thresh:
            # Flip whichever has the larger x; keeps the leftmost stable.
            target = j if points[i].x <= points[j].x else i
            flip[target] = True

    for i, p in enumerate(points):
        if flip[i]:
            dx, dy, ha, va = -8, -10, "right", "top"
        else:
            dx, dy, ha, va = 8, 8, "left", "bottom"
        ax.annotate(
            p.label,
            xy=(p.x, p.y),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=9,
            fontfamily=FONT_STACK[0],
            color="#333333",
            ha=ha,
            va=va,
        )
