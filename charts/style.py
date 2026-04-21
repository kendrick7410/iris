"""
Cefic chart style constants and helpers for Iris.

Contract: single source of truth for palette, fonts, dimensions, source line formatting.
"""

CEFIC_COLORS = {
    "primary": "#d36b1d",
    "primary_dark": "#9f5216",
    "primary_light": "#e07e2a",
    "positive": "#80b664",
    "negative": "#b85f1a",
    "benchmark": "#888888",
    "grid": "#E0E0E0",
    "highlight": "#049cd2",
    "blue_1": "#049cd2",
    "blue_2": "#0574b8",
    "blue_3": "#4398a5",
    "sectors": ["#d36b1d", "#0574b8", "#80b664", "#4398a5", "#9f5216"],
}

FONT_STACK = ["Inter", "Arial", "Helvetica", "sans-serif"]
DEFAULT_DIMS = {"width_px": 800, "height_px": 450, "dpi": 96}


def format_source_line(year: int, note: str = "") -> str:
    """Returns the verbatim Cefic source line per system.md Template 5.4."""
    if note:
        return f"Source: Cefic analysis based on Eurostat data ({year}, {note})"
    return f"Source: Cefic analysis based on Eurostat data ({year})"


def apply_style(ax, title: str = "", source_year: int = None, source_note: str = ""):
    """Apply Cefic styling to a matplotlib axes."""
    import matplotlib.pyplot as plt

    ax.set_title(title, fontsize=12, fontfamily=FONT_STACK[0], fontweight="bold",
                 loc="left", pad=12)
    ax.grid(axis="y", color=CEFIC_COLORS["grid"], linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(CEFIC_COLORS["grid"])
    ax.spines["bottom"].set_color(CEFIC_COLORS["grid"])
    ax.tick_params(colors="#333333", labelsize=9)

    if source_year:
        source_text = format_source_line(source_year, source_note)
        ax.figure.text(0.1, 0.02, source_text, fontsize=7, color="#666666",
                       fontfamily=FONT_STACK[0])
