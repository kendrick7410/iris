"""
Scatter 1 — "Who holds up, who struggles" (CU × Trade balance, by country).

X-axis: average capacity utilisation over the latest fully-elapsed quarter (%)
Y-axis: contribution to the extra-EU27 chemical trade balance over the
        SAME 3 months as the X-axis quarter (€ bn)
Points: 7 top chemical producers (DE, FR, IT, NL, ES, BE, PL)
References: mean historical CU = 81.3% (vertical), y = 0 (horizontal)

Both axes share the same period — the BCS quarter and the trade-balance
window are pinned to the same 3 months. The compute step verifies the
alignment and raises if the cached files were produced for different
windows; rerun the fetchers with matching parameters in that case.

IMPORTANT caveat on the X-axis data: Eurostat's BCS indicator
`BS-ICU-PC` (ei_bsin_q_r2) publishes capacity utilisation at the
manufacturing-industry level, NOT NACE C20 specifically. We use it as
a country-level proxy; chemical industry CU is not available per
country in the Eurostat dissemination API. Each point's annotations
flag this (`cu_proxy = 'manufacturing'`).

Data sources:
  - data/cache/{month}/bcs.json
      {"latest_quarter": "2025-Q4",
       "quarter_months": ["2025-10", "2025-11", "2025-12"],
       "cu_by_country": {"DE": 74.0, ...}}
  - data/cache/{month}/country_trade_balance.json
      {"window_months": ["2025-10", "2025-11", "2025-12"],
       "balance_eur_bn_by_country": {"DE": 2.34, ...}}

Signal strength: std-dev of trade balance across countries, normalised
by a cap of 3 €bn. Above 3€bn of dispersion (one country strongly
surplus while another is deficit) there is clearly a story.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from analysis.scatters.base import (
    ScatterData,
    ScatterPoint,
    COUNTRY_NAMES,
    TOP7_COUNTRIES,
    normalise_stdev,
)

logger = logging.getLogger("iris.scatters.cu_trade")


HISTORICAL_CU_MEAN = 81.3  # long-run EU27 manufacturing CU, per BCS


def _quarter_months(quarter: str) -> list[str]:
    """'2025-Q4' → ['2025-10', '2025-11', '2025-12']."""
    y, q = quarter.split("-Q")
    end = int(q) * 3
    return [f"{y}-{end - 2:02d}", f"{y}-{end - 1:02d}", f"{y}-{end:02d}"]


def compute(month: str, config: dict) -> ScatterData:
    cache_dir = Path(config["cache_dir"])

    bcs_path = cache_dir / "bcs.json"
    balance_path = cache_dir / "country_trade_balance.json"
    for p in (bcs_path, balance_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {p}; run the corresponding fetcher first "
                "(data.fetchers.eurostat.fetch_bcs_cu, "
                "data.fetchers.comext.fetch_country_trade_balance)."
            )

    bcs = json.loads(bcs_path.read_text())
    balance = json.loads(balance_path.read_text())

    quarter = bcs.get("latest_quarter")
    if not quarter:
        raise RuntimeError("bcs.json is missing 'latest_quarter'.")
    expected_months = bcs.get("quarter_months") or _quarter_months(quarter)
    actual_months = balance.get("window_months", [])
    if list(actual_months) != list(expected_months):
        raise RuntimeError(
            f"Period mismatch in cu_trade: BCS quarter {quarter} covers "
            f"{expected_months} but country_trade_balance.json covers "
            f"{actual_months}. Re-run "
            f"`data.fetchers.comext.fetch_country_trade_balance(month, cache_dir, "
            f"window_end_month='{expected_months[-1]}')` to align the two axes."
        )

    cu_by_ctry = bcs["cu_by_country"]
    bal_by_ctry = balance["balance_eur_bn_by_country"]

    points: list[ScatterPoint] = []
    y_values: list[float] = []
    for ctry in TOP7_COUNTRIES:
        cu = cu_by_ctry.get(ctry)
        bal = bal_by_ctry.get(ctry)
        if cu is None or bal is None:
            logger.warning("cu_trade: skipping %s (cu=%s bal=%s)", ctry, cu, bal)
            continue
        y_values.append(float(bal))
        points.append(
            ScatterPoint(
                label=ctry,
                x=round(float(cu), 1),
                y=round(float(bal), 2),
                annotations={
                    "country_name": COUNTRY_NAMES.get(ctry, ctry),
                    "period": quarter,
                    "period_months": expected_months,
                    "cu_proxy": "manufacturing",
                    "cu_note": (
                        "Eurostat BCS does not publish country-level CU for NACE C20 "
                        "specifically; manufacturing total is used as a proxy."
                    ),
                    "balance_eur_bn": round(float(bal), 2),
                },
            )
        )

    # Cap of 3 €bn: when trade balances spread by more than 3 €bn across
    # countries, the scatter already tells a strong who-wins / who-loses story.
    sig = normalise_stdev(y_values, cap=3.0) if y_values else 0.0
    if y_values:
        mean = sum(y_values) / len(y_values)
        stdev = (sum((v - mean) ** 2 for v in y_values) / len(y_values)) ** 0.5
        sig_expl = (
            f"Std-dev of country trade balances: {stdev:.2f} €bn "
            f"(capped at 3 €bn). Higher dispersion = clearer winners/losers."
        )
    else:
        sig_expl = "No usable data points."

    year = int(month.split("-")[0])

    return ScatterData(
        scatter_id="cu_trade",
        title="Who holds up, who struggles: capacity utilisation vs trade balance",
        x_axis_label=f"Manufacturing capacity utilisation, {quarter} (%)",
        y_axis_label=f"Extra-EU27 chemical trade balance, {quarter} (€bn)",
        points=points,
        reference_lines={"x_ref": HISTORICAL_CU_MEAN, "y_ref": 0.0},
        signal_strength=sig,
        signal_explanation=sig_expl,
        metadata={
            "source": "Eurostat BCS ei_bsin_q_r2 (BS-ICU-PC, SA) + Comext extra-EU27",
            "cu_proxy": "manufacturing total (C) as NACE C20 not available per country",
            "edition_month": month,
            "year": year,
            "period": quarter,
            "period_months": expected_months,
            "historical_cu_mean": HISTORICAL_CU_MEAN,
        },
    )
