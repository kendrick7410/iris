"""
Waterfall chart for CN 8-digit drill-down contributions, L5.

Replaces the pie charts of slides 13/18/23/28 with a bridge chart that
shows each CN8 code's contribution to the total change, followed by
an "Other products" bar and a total-change bar (Pattern 21 visual).

Pie is rejected per Phase 1 decision (out of Cefic in-depth corpus).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from charts.style import CEFIC_COLORS, DEFAULT_DIMS, apply_style


def render(
    contributions: list,
    other_value: float,
    total_label: str,
    dimension: str,
    title: str,
    output_path: Path,
    source_year: int,
    unit: str = None,
    show_cumulative: bool = True,
):
    """Render a waterfall showing CN8 contributions + 'other' + total.

    contributions  : list of {"label": "29091990 (...)", "value": 0.5}
                     Already truncated (system.md §5.8 truncation rule).
    other_value    : aggregate contribution of the rest of the products
    total_label    : e.g. "Total change 2020-2025"
    dimension      : "volume" or "value"
    unit           : "mln tonnes" (volume) or "€ bn" (value), auto if None
    show_cumulative: draws faint connectors between bars
    """
    if not contributions and not other_value:
        return None

    if unit is None:
        unit = "mln tonnes" if dimension == "volume" else "€ bn"

    items = list(contributions) + [{"label": "Other products", "value": float(other_value)}]
    total_value = sum(item["value"] for item in items)
    items.append({"label": total_label, "value": total_value, "is_total": True})

    labels = [it["label"] for it in items]
    values = [it["value"] for it in items]

    cumulative = 0.0
    bottoms = []
    bar_values = []
    colors = []
    for it in items:
        if it.get("is_total"):
            bottoms.append(0.0)
            bar_values.append(it["value"])
            colors.append(CEFIC_COLORS["primary_dark"])
        else:
            v = it["value"]
            if v >= 0:
                bottoms.append(cumulative)
                bar_values.append(v)
                colors.append(CEFIC_COLORS["positive"] if v >= 0 else CEFIC_COLORS["negative"])
            else:
                bottoms.append(cumulative + v)
                bar_values.append(-v)
                colors.append(CEFIC_COLORS["negative"])
            cumulative += v

    fig, ax = plt.subplots(
        figsize=(DEFAULT_DIMS["width_px"] / DEFAULT_DIMS["dpi"],
                 (DEFAULT_DIMS["height_px"] + 60) / DEFAULT_DIMS["dpi"]),
        dpi=DEFAULT_DIMS["dpi"],
    )

    x_positions = list(range(len(items)))
    bars = ax.bar(x_positions, bar_values, bottom=bottoms,
                  color=colors, edgecolor="white", linewidth=0.6, width=0.7)

    if show_cumulative:
        cum = 0.0
        for i, it in enumerate(items[:-1]):
            cum += it["value"]
            ax.plot([i + 0.35, i + 1 - 0.35], [cum, cum],
                    color="#999999", linewidth=0.5, linestyle="--")

    for i, it in enumerate(items):
        top = bottoms[i] + bar_values[i]
        raw = it["value"]
        sign = "+" if raw > 0 and not it.get("is_total") else ""
        ax.text(i, top + abs(total_value) * 0.02,
                f"{sign}{raw:.2f}",
                ha="center", va="bottom", fontsize=8,
                color="#333333", fontweight="bold" if it.get("is_total") else "normal")

    ax.set_xticks(x_positions)
    ax.set_xticklabels([_wrap(lbl) for lbl in labels], fontsize=7, rotation=30, ha="right")
    ax.set_ylabel(f"{dimension.capitalize()} contribution ({unit})", fontsize=9)
    ax.axhline(y=0, color="#333333", linewidth=0.5)
    apply_style(ax, title=title, source_year=source_year)

    fig.tight_layout(rect=[0, 0.10, 1, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


def _wrap(label: str, width: int = 22) -> str:
    if len(label) <= width:
        return label
    parts, cur = [], ""
    for word in label.split():
        if len(cur) + len(word) + 1 > width and cur:
            parts.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        parts.append(cur)
    return "\n".join(parts[:3])
