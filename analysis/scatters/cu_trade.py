"""
Scatter 1 — "Who holds up, who struggles" (CU × Trade balance, by country).

X-axis: average capacity utilisation over the latest available quarter (%)
Y-axis: contribution to the extra-EU27 chemical trade balance (€ bn, rolling 3m)
Points: 7 top chemical producers (DE, FR, IT, NL, ES, BE, PL)
References: mean historical CU = 81.3% (vertical), y = 0 (horizontal)

IMPORTANT caveat on the X-axis data: Eurostat's BCS indicator
`BS-ICU-PC` (ei_bsin_q_r2) publishes capacity utilisation at the
manufacturing-industry level, NOT NACE C20 specifically. We use it as
a country-level proxy; chemical industry CU is not available per
country in the Eurostat dissemination API. Each point's annotations
flag this (`cu_proxy = 'manufacturing'`).

Data sources:
  - data/cache/{month}/bcs.json
      {"latest_quarter": "2026-Q1", "cu_by_country": {"DE": 74.0, ...}}
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
                    "cu_latest_quarter": bcs.get("latest_quarter"),
                    "cu_proxy": "manufacturing",
                    "cu_note": (
                        "Eurostat BCS does not publish country-level CU for NACE C20 "
                        "specifically; manufacturing total is used as a proxy."
                    ),
                    "balance_window_months": balance.get("window_months", []),
                    "balance_eur_bn": round(float(bal), 2),
                },
            )
        )

    # Cap of 3 €bn: when trade balances spread by more than 3 €bn across
    # countries, the scatter already tells a strong who-wins / who-loses story.
    sig = normalise_stdev(y_values, cap=3.0) if y_values else 0.0
    sig_expl = (
        f"Std-dev of country trade balances: {(sum((v - sum(y_values)/len(y_values))**2 for v in y_values)/len(y_values))**0.5:.2f} €bn "
        f"(capped at 3 €bn). Higher dispersion = clearer winners/losers."
        if y_values else "No usable data points."
    )

    year = int(month.split("-")[0])

    return ScatterData(
        scatter_id="cu_trade",
        title="Who holds up, who struggles: capacity utilisation vs trade balance",
        x_axis_label=f"Manufacturing capacity utilisation, {bcs.get('latest_quarter', 'latest Q')} (%)",
        y_axis_label="Extra-EU27 chemical trade balance, rolling 3m (€bn)",
        points=points,
        reference_lines={"x_ref": HISTORICAL_CU_MEAN, "y_ref": 0.0},
        signal_strength=sig,
        signal_explanation=sig_expl,
        metadata={
            "source": "Eurostat BCS ei_bsin_q_r2 (BS-ICU-PC, SA) + Comext extra-EU27",
            "cu_proxy": "manufacturing total (C) as NACE C20 not available per country",
            "edition_month": month,
            "year": year,
            "historical_cu_mean": HISTORICAL_CU_MEAN,
        },
    )
