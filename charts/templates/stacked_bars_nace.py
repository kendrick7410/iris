"""
Stacked or clustered bars by NACE 4-digit category over multiple years — L5.

Reproduces slides 11/16/21/26 (stacked) and 12/17/22/27 (clustered with
YoY annotations on last year) of the Cefic Trade Brief 2026-04 deck.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from charts.style import CEFIC_COLORS, DEFAULT_DIMS, apply_style

SECTOR_PALETTE = CEFIC_COLORS["sectors"] + [
    CEFIC_COLORS["primary_dark"], CEFIC_COLORS["blue_2"],
    CEFIC_COLORS["positive"], CEFIC_COLORS["benchmark"],
    CEFIC_COLORS["primary_light"], CEFIC_COLORS["blue_3"],
]


def render(
    by_year_by_nace: dict,
    nace_labels: dict,
    dimension: str,
    title: str,
    output_path: Path,
    source_year: int,
    mode: str = "stacked",
    annotate_yoy_last: bool = False,
    year_range: tuple = None,
    unit: str = None,
):
    """Render stacked or clustered bars by NACE 4-digit over years.

    by_year_by_nace : {"2021": {"20.14": 12.3, "20.15": 4.5, ...}, "2022": {...}, ...}
    nace_labels     : {"20.14": "Other organic basic chemicals", ...}
    dimension       : "volume" or "value" — only used for axis label fallback
    mode            : "stacked" (sum per year) or "clustered" (grouped side by side)
    annotate_yoy_last : if True, annotate each NACE bar of the last year with YoY %
    year_range      : (2021, 2025) — optional filter; defaults to all years in data
    unit            : y-axis unit label; defaults to "mln tonnes" (volume) or "€ bn" (value)
    """
    if not by_year_by_nace:
        return None

    if year_range:
        years = [str(y) for y in range(year_range[0], year_range[1] + 1)
                 if str(y) in by_year_by_nace]
    else:
        years = sorted(by_year_by_nace.keys())
    if len(years) < 2:
        return None

    nace_codes = sorted({code for y in years for code in by_year_by_nace[y]})
    color_map = {code: SECTOR_PALETTE[i % len(SECTOR_PALETTE)] for i, code in enumerate(nace_codes)}

    if unit is None:
        unit = "mln tonnes" if dimension == "volume" else "€ bn"

    fig, ax = plt.subplots(
        figsize=(DEFAULT_DIMS["width_px"] / DEFAULT_DIMS["dpi"],
                 DEFAULT_DIMS["height_px"] / DEFAULT_DIMS["dpi"]),
        dpi=DEFAULT_DIMS["dpi"],
    )

    if mode == "stacked":
        bottoms = [0.0] * len(years)
        for code in nace_codes:
            values = [by_year_by_nace[y].get(code, 0) for y in years]
            ax.bar(years, values, bottom=bottoms, color=color_map[code],
                   label=f"{code} {_short(nace_labels.get(code, code))}",
                   edgecolor="white", linewidth=0.5)
            bottoms = [b + v for b, v in zip(bottoms, values)]

        if annotate_yoy_last and len(years) >= 2:
            prev_y, last_y = years[-2], years[-1]
            prev_total = sum(by_year_by_nace[prev_y].values())
            last_total = sum(by_year_by_nace[last_y].values())
            if prev_total != 0:
                yoy = (last_total - prev_total) / prev_total * 100
                ax.annotate(f"{yoy:+.1f}%",
                            xy=(len(years) - 1, last_total),
                            xytext=(0, 6), textcoords="offset points",
                            ha="center", fontsize=9,
                            color=CEFIC_COLORS["primary_dark"], fontweight="bold")

    else:  # clustered
        import numpy as np
        n_naces = len(nace_codes)
        x = np.arange(len(years))
        width = 0.8 / max(n_naces, 1)
        for i, code in enumerate(nace_codes):
            values = [by_year_by_nace[y].get(code, 0) for y in years]
            offset = (i - (n_naces - 1) / 2) * width
            bars = ax.bar(x + offset, values, width, color=color_map[code],
                          label=f"{code} {_short(nace_labels.get(code, code))}",
                          edgecolor="white", linewidth=0.3)
            if annotate_yoy_last and len(years) >= 2:
                prev_val = by_year_by_nace[years[-2]].get(code, 0)
                last_val = by_year_by_nace[years[-1]].get(code, 0)
                if prev_val:
                    yoy = (last_val - prev_val) / prev_val * 100
                    ax.annotate(f"{yoy:+.0f}%",
                                xy=(x[-1] + offset, last_val),
                                xytext=(0, 3), textcoords="offset points",
                                ha="center", fontsize=7,
                                color=CEFIC_COLORS["primary_dark"])
        ax.set_xticks(x)
        ax.set_xticklabels(years)

    ax.set_ylabel(f"{dimension.capitalize()} ({unit})", fontsize=9)
    ax.axhline(y=0, color="#333333", linewidth=0.5)
    apply_style(ax, title=title, source_year=source_year)

    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=7,
              frameon=False, borderaxespad=0)

    fig.tight_layout(rect=[0, 0.06, 0.82, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


def _short(label: str, max_len: int = 35) -> str:
    if not label:
        return ""
    if len(label) <= max_len:
        return label
    cut = label[:max_len].rsplit(" ", 1)[0]
    return cut + "…"
