"""Long-arc line charts for Iris, 60-month window.

Two renderers (Pattern 24, long-arc context):
  - render_trade_balance_monthly(series, ...)
  - render_exports_by_partner(series_by_partner, ...)

Both use charts.style.CEFIC_COLORS for palette, DEFAULT_DIMS for dimensions,
and format_source_line for the verbatim Cefic caption.
"""

from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyArrowPatch

from charts.style import CEFIC_COLORS, DEFAULT_DIMS, FONT_STACK, apply_style, format_source_line


def _parse_period(p: str) -> datetime:
    """Parse YYYY-MM into a datetime anchored to the 1st of the month."""
    y, m = p.split("-")
    return datetime(int(y), int(m), 1)


def render_trade_balance_monthly(
    series: list,
    output_path: Path,
    annotations: list = None,
    source_year: int = None,
) -> Path:
    """Render EU27 chemical trade balance over N months (default 60).

    series       : list of {"period": "YYYY-MM", "value_eur_bn": float}, chronological
    annotations  : optional list of {"period": "YYYY-MM", "label": "..."},
                   max 2 honoured (more would clutter)
    """
    dates  = [_parse_period(s["period"]) for s in series]
    values = [s["value_eur_bn"] for s in series]

    w_px, h_px, dpi = DEFAULT_DIMS["width_px"], DEFAULT_DIMS["height_px"], DEFAULT_DIMS["dpi"]
    fig, ax = plt.subplots(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)

    ax.fill_between(dates, values, 0, where=[v >= 0 for v in values],
                    color=CEFIC_COLORS["positive"], alpha=0.25, interpolate=True,
                    label="Surplus")
    ax.fill_between(dates, values, 0, where=[v < 0 for v in values],
                    color=CEFIC_COLORS["negative"], alpha=0.30, interpolate=True,
                    label="Deficit")

    ax.plot(dates, values, color="#1a1a1a", linewidth=1.5)
    ax.axhline(0, color="#1a1a1a", linewidth=1.2, zorder=3)

    # X-axis: year ticks (every 12 months), format "MMM YYYY" on Jan
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    for lbl in ax.get_xticklabels():
        lbl.set_fontsize(9)

    ax.set_ylabel("€ bn", fontsize=9)

    # Annotations (max 2)
    if annotations:
        for ann in annotations[:2]:
            d = _parse_period(ann["period"])
            # Find value at or nearest to this date
            v = next((v for dt, v in zip(dates, values) if dt == d), None)
            if v is None:
                continue
            offset_y = 2.0 if v < 5 else -2.0  # push away from the line
            ax.annotate(
                ann["label"],
                xy=(d, v),
                xytext=(d, v + offset_y),
                fontsize=8,
                color="#333333",
                fontfamily=FONT_STACK[0],
                ha="center",
                arrowprops=dict(arrowstyle="->", color="#666666", lw=0.8,
                                connectionstyle="arc3,rad=0"),
            )

    ax.legend(loc="upper left", fontsize=8, frameon=False)
    apply_style(ax, title="EU27 chemical trade balance, monthly",
                source_year=source_year or datetime.now().year)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


def render_exports_by_partner(
    series_by_partner: dict,
    output_path: Path,
    current_month: str = None,
    source_year: int = None,
) -> Path:
    """Render EU27 chemical exports by top 4 partners + Other.

    series_by_partner : {"US": [{"period": ..., "value_eur_bn": ...}, ...],
                         "GB": [...], "CN": [...], "CH": [...],
                         "OTHER": [...]}
                        Each list is chronological; all lists share the same periods.
    current_month     : "YYYY-MM"; adds a marker dot on that point per partner.
    """
    # Fixed partner order + colours; US is the pivot, thicker line
    partner_spec = [
        ("US",    CEFIC_COLORS["primary"],   2.0, "United States"),
        ("GB",    CEFIC_COLORS["blue_2"],    1.3, "United Kingdom"),
        ("CN",    CEFIC_COLORS["blue_1"],    1.3, "China"),
        ("CH",    CEFIC_COLORS["positive"],  1.3, "Switzerland"),
        ("OTHER", "#aaaaaa",                 1.1, "Other partners"),
    ]

    w_px, h_px, dpi = DEFAULT_DIMS["width_px"], DEFAULT_DIMS["height_px"], DEFAULT_DIMS["dpi"]
    fig, ax = plt.subplots(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)

    label_positions = []
    for key, colour, lw, label in partner_spec:
        pts = series_by_partner.get(key)
        if not pts:
            continue
        dates  = [_parse_period(p["period"])        for p in pts]
        values = [p["value_eur_bn"]                 for p in pts]
        ax.plot(dates, values, color=colour, linewidth=lw, label=label)
        label_positions.append((dates[-1], values[-1], colour, label))

        if current_month:
            cd = _parse_period(current_month)
            cv = next((v for dt, v in zip(dates, values) if dt == cd), None)
            if cv is not None:
                ax.plot([cd], [cv], "o", color=colour, markersize=5, zorder=5,
                        markeredgecolor="white", markeredgewidth=1.2)

    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    for lbl in ax.get_xticklabels():
        lbl.set_fontsize(9)

    ax.set_ylabel("€ bn", fontsize=9)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=5)

    apply_style(ax, title="EU27 chemical exports by partner, monthly",
                source_year=source_year or datetime.now().year)

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), format="svg", bbox_inches="tight")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
def _build_series_from_parquet(parquet_path: str, months: int = 60):
    """Return (balance_series, exports_by_partner) from the Comext parquet.

    balance_series       : list of {"period": "YYYY-MM", "value_eur_bn": ...}
    exports_by_partner   : {"US": [...], "GB": [...], "CN": [...], "CH": [...], "OTHER": [...]}
    """
    import pandas as pd
    import pyarrow.parquet as pq

    t = pq.read_table(parquet_path,
        columns=["period", "declarant", "partner", "flow", "value_in_euros"])
    df = t.to_pandas()
    df = df[(df.declarant == "EU") & (df.partner != "EU27")]
    df["period_ym"] = df["period"].dt.strftime("%Y-%m")

    all_periods = sorted(df.period_ym.unique())
    window = all_periods[-months:]
    df = df[df.period_ym.isin(window)]

    # Balance = exports (flow=2) - imports (flow=1)
    agg = df.groupby(["period_ym", "flow"])["value_in_euros"].sum().unstack(fill_value=0)
    agg = agg.rename(columns={1: "imports", 2: "exports"})
    agg["balance"] = agg["exports"] - agg["imports"]
    balance_series = [
        {"period": p, "value_eur_bn": round(v / 1e9, 3)}
        for p, v in agg["balance"].items()
    ]

    # Exports by partner (flow=2)
    xdf = df[df.flow == 2]
    by_partner = xdf.groupby(["period_ym", "partner"])["value_in_euros"].sum().unstack(fill_value=0)
    by_partner_bn = by_partner / 1e9

    keys = ["US", "GB", "CN", "CH"]
    out = {}
    for k in keys:
        if k not in by_partner_bn.columns:
            out[k] = []
            continue
        out[k] = [{"period": p, "value_eur_bn": round(v, 3)}
                  for p, v in by_partner_bn[k].items()]

    # OTHER = all partners except the 4 above
    other_cols = [c for c in by_partner_bn.columns if c not in keys]
    other_series = by_partner_bn[other_cols].sum(axis=1)
    out["OTHER"] = [{"period": p, "value_eur_bn": round(v, 3)}
                    for p, v in other_series.items()]

    return balance_series, out


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        PARQUET = "/home/jme/comext-etl/comext_export.parquet"
        balance, by_partner = _build_series_from_parquet(PARQUET, months=60)
        print(f"balance series: {len(balance)} months, {balance[0]['period']} to {balance[-1]['period']}")
        print(f"partners: {list(by_partner.keys())}, each with {len(by_partner['US'])} points")

        out1 = Path("/tmp/test_trade_balance_monthly_60m.svg")
        out2 = Path("/tmp/test_exports_by_partner_60m.svg")

        render_trade_balance_monthly(
            balance, out1,
            annotations=[
                {"period": "2025-02", "label": "Pre-tariff front-loading"},
                {"period": "2026-02", "label": "Latest read"},
            ],
            source_year=2026,
        )
        render_exports_by_partner(
            by_partner, out2,
            current_month="2026-02",
            source_year=2026,
        )
        print(f"Generated: {out1}")
        print(f"Generated: {out2}")
