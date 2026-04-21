"""
Anomaly detector for Iris fiches — guards against base-effect misreads.

Contract:
  - detect_base_effects(current_fiche, historical_series, related_indicators) → AnomalyReport
  - Pure: no I/O, no globals. Caller assembles inputs and persists outputs.
  - Detects 5 families of data anomalies that make headline figures misleading:
      D1 — Comext/IPI divergence (trade shock without production shock)
      D2 — Volume/value divergence (price/mix effect dominates)
      D3 — Abnormal prior-year base (Z-score on 12m pre-base window)
      D4 — Partner concentration (1-2 partners drive the variation)
      D5 — N-2 sanity check (modest vs N-2 but large vs N-1)

Triggered flags inflate `severity`: 1 flag = "watch", 2 = "warn",
≥3 or the (D1+D3) combo = "critical".

The detector emits a `suggested_caveat` draft — the LLM rewrites it in Cefic
voice per system.md §5.9.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any

# Thresholds — tuneable; keep in one place for calibration
TRADE_YOY_SHOCK_PCT = 30.0          # D1: |trade YoY| above this is a "shock"
IPI_NORMAL_PCT = 10.0               # D1: |IPI YoY| below this means no real shock
VALUE_VOLUME_RATIO = 2.0            # D2: |Δvalue| > VVR × |Δvolume|
Z_SCORE_THRESHOLD = 2.0             # D3: base > mean + 2σ of prior 12m
PARTNER_CONCENTRATION_PCT = 75.0    # D4: top-2 partners explain >X% of |Δ|
N2_MODEST_RATIO = 0.5               # D5: |Δ vs N-2| < 0.5 × |Δ vs N-1|
N2_MIN_N1_MOVE_PCT = 10.0           # D5: only fire if |Δ vs N-1| is itself ≥ this
HISTORY_WINDOW_MONTHS = 12          # Rolling window for Z-score denominator


@dataclass
class AnomalyReport:
    """Structured output of anomaly detection for one fiche."""
    flags: list[str] = field(default_factory=list)
    severity: str = "none"  # "none" | "watch" | "warn" | "critical"
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_caveat: str | None = None
    recommended_baseline: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------

def detect_base_effects(
    current_fiche: dict,
    historical_series: dict | None = None,
    related_indicators: dict | None = None,
) -> AnomalyReport:
    """Run all applicable detectors on a fiche and return an AnomalyReport.

    Arguments:
      current_fiche: the fiche JSON (with `section_type`, `data.*`).
      historical_series: optional monthly history per entity, shape:
          {"eu27_total": {"YYYY-MM": float, ...},
           "by_partner": {"US": {"YYYY-MM": float, ...}, ...}}
          The unit should be homogeneous (value in €bn for trade).
      related_indicators: cross-section YoY figures used by D1:
          {"output_ipi_yoy_pct": -3.9, "prices_ppi_yoy_pct": -2.8, ...}

    Returns an AnomalyReport. If no flags are raised, severity is "none"
    and the suggested_caveat is None.
    """
    historical_series = historical_series or {}
    related_indicators = related_indicators or {}

    section = current_fiche.get("section_type", "")
    data = current_fiche.get("data") or {}

    flags: list[str] = []
    evidence: dict[str, Any] = {}

    # Each detector is gated on section_type and input availability.
    if section in ("trade_exports", "trade_imports"):
        _d1 = _detect_comext_ipi_divergence(data, related_indicators)
        if _d1:
            flags.append("comext_ipi_divergence")
            evidence["comext_ipi_divergence"] = _d1

        _d2 = _detect_value_volume_divergence(data)
        if _d2:
            flags.append("value_volume_divergence")
            evidence["value_volume_divergence"] = _d2

        _d4 = _detect_partner_concentration(data)
        if _d4:
            flags.append("partner_concentration")
            evidence["partner_concentration"] = _d4

    # D3 and D5 need historical series — applicable to any section that
    # provides one. Most relevant for trade today.
    _d3 = _detect_abnormal_prior_year_base(data, historical_series)
    if _d3:
        flags.append("abnormal_prior_year_base")
        evidence["abnormal_prior_year_base"] = _d3

    _d5 = _detect_n_minus_2_modest(data, historical_series)
    if _d5:
        flags.append("n_minus_2_modest")
        evidence["n_minus_2_modest"] = _d5

    severity = _aggregate_severity(flags)
    caveat = _build_suggested_caveat(section, flags, evidence) if severity != "none" else None
    baseline = _recommend_baseline(flags, evidence) if severity != "none" else None

    return AnomalyReport(
        flags=flags,
        severity=severity,
        evidence=evidence,
        suggested_caveat=caveat,
        recommended_baseline=baseline,
    )


# ----------------------------------------------------------------------------
# Detectors
# ----------------------------------------------------------------------------

def _detect_comext_ipi_divergence(data: dict, related: dict) -> dict | None:
    """D1 — trade YoY is dramatic but production IPI YoY is tame."""
    trade_yoy = _trade_yoy_headline(data)
    ipi_yoy = related.get("output_ipi_yoy_pct")
    if trade_yoy is None or ipi_yoy is None:
        return None
    if abs(trade_yoy) < TRADE_YOY_SHOCK_PCT or abs(ipi_yoy) >= IPI_NORMAL_PCT:
        return None
    ratio = abs(trade_yoy) / abs(ipi_yoy) if ipi_yoy else None
    return {
        "trade_yoy_pct": round(trade_yoy, 1),
        "ipi_yoy_pct": round(ipi_yoy, 1),
        "ratio": round(ratio, 1) if ratio else None,
        "threshold_trade_pct": TRADE_YOY_SHOCK_PCT,
        "threshold_ipi_pct": IPI_NORMAL_PCT,
        "interpretation": (
            "Trade shock magnitudes of this order normally co-move with "
            "production or price shocks. The absence of such co-movement "
            "suggests a base effect or a one-off composition change rather "
            "than a real underlying rupture."
        ),
    }


def _detect_value_volume_divergence(data: dict) -> dict | None:
    """D2 — value YoY is much larger than volume YoY (price/mix effect)."""
    # Prefer YTD (matches the headline figure), fallback to single-month.
    ytd = (data.get("ytd") or {})
    dv = ytd.get("delta_pct_value")
    dvol = ytd.get("delta_pct_volume")
    window = "ytd"
    if dv is None or dvol is None:
        py = (data.get("previous_year") or {})
        dv = py.get("delta_pct_value")
        dvol = py.get("delta_pct_volume")
        window = "single_month"
    if dv is None or dvol is None:
        return None
    if abs(dvol) == 0:
        return None
    if abs(dv) < VALUE_VOLUME_RATIO * abs(dvol):
        return None
    return {
        "value_pct": round(dv, 1),
        "volume_pct": round(dvol, 1),
        "ratio": round(abs(dv) / abs(dvol), 2),
        "window": window,
        "threshold_ratio": VALUE_VOLUME_RATIO,
        "interpretation": (
            "Value decline exceeds volume decline by more than the "
            f"{VALUE_VOLUME_RATIO}× threshold, indicating a unit-value / "
            "product-mix shift rather than a uniform demand contraction."
        ),
    }


def _detect_abnormal_prior_year_base(data: dict, history: dict) -> dict | None:
    """D3 — base (previous_year) value is > 2σ above its 12m pre-base mean."""
    py = data.get("previous_year") or {}
    base_period = py.get("period")
    base_value = _prior_year_value(py)
    if base_period is None or base_value is None:
        return None

    series = (history.get("eu27_total") or {})
    if not series:
        return None

    prior = _prior_window(series, base_period, HISTORY_WINDOW_MONTHS)
    if len(prior) < 6:  # need enough history to compute a meaningful σ
        return None

    mean = sum(prior) / len(prior)
    var = sum((x - mean) ** 2 for x in prior) / len(prior)
    std = math.sqrt(var) if var > 0 else 0.0
    if std == 0:
        return None
    z = (base_value - mean) / std
    if abs(z) < Z_SCORE_THRESHOLD:
        return None

    # Likely driver: surface editorial_context notable_events when present
    driver = None
    events = ((data.get("source") and []) or [])
    # Grab from fiche.editorial_context when the caller routed it
    # (we do not read top-level editorial_context here; callers may inject it)
    return {
        "base_period": base_period,
        "base_value": round(base_value, 2),
        "prior_window_months": len(prior),
        "prior_window_mean": round(mean, 2),
        "prior_window_std": round(std, 2),
        "z_score": round(z, 2),
        "direction": "above" if z > 0 else "below",
        "likely_driver": driver,
        "interpretation": (
            f"The comparison base ({base_period}) is {abs(z):.1f} standard "
            f"deviations {'above' if z > 0 else 'below'} the mean of the "
            f"preceding {len(prior)} months. Any YoY change against this "
            "base will mechanically exaggerate the apparent movement."
        ),
    }


def _detect_partner_concentration(data: dict) -> dict | None:
    """D4 — top 2 partners explain >75% of the absolute variation."""
    partners = data.get("by_partner") or []
    if not partners:
        return None

    abs_deltas: list[tuple[str, float, float, float]] = []
    for p in partners:
        cur = p.get("value_eur_bn")
        prev = p.get("previous_year_value_eur_bn")
        if cur is None or prev is None:
            continue
        delta = cur - prev
        abs_deltas.append((p.get("partner") or p.get("label") or "?",
                           p.get("label") or p.get("partner") or "?",
                           delta, abs(delta)))
    if not abs_deltas:
        return None

    abs_deltas.sort(key=lambda x: x[3], reverse=True)
    total_abs = sum(x[3] for x in abs_deltas)
    if total_abs == 0:
        return None

    top2 = abs_deltas[:2]
    top2_abs = sum(x[3] for x in top2)
    share = top2_abs / total_abs * 100
    if share < PARTNER_CONCENTRATION_PCT:
        return None

    return {
        "top_2_partners": [
            {"partner": code, "label": label,
             "delta_eur_bn": round(delta, 2),
             "abs_contribution_pct": round(abs_v / total_abs * 100, 1)}
            for code, label, delta, abs_v in top2
        ],
        "top_2_share_of_abs_variation_pct": round(share, 1),
        "threshold_pct": PARTNER_CONCENTRATION_PCT,
        "total_abs_variation_eur_bn": round(total_abs, 2),
        "interpretation": (
            f"{share:.1f}% of the absolute variation is explained by 2 partners. "
            "A movement this concentrated is not a structural trend — it is an "
            "idiosyncratic shift in a small number of bilateral flows."
        ),
    }


def _detect_n_minus_2_modest(data: dict, history: dict) -> dict | None:
    """D5 — compare current vs N-2: if much smaller than current vs N-1, flag."""
    cur = _current_value(data)
    py = data.get("previous_year") or {}
    base_period = py.get("period")
    prev = _prior_year_value(py)
    if cur is None or prev is None or base_period is None:
        return None

    series = history.get("eu27_total") or {}
    if not series:
        return None

    n2_period = _shift_period(base_period, years=-1)
    n2_value = series.get(n2_period)
    if n2_value is None:
        return None

    delta_n1 = cur - prev
    delta_n2 = cur - n2_value
    if delta_n1 == 0:
        return None
    # Only fire when the N-1 move itself is editorially material — avoids
    # flagging noise on near-stable series.
    if abs(delta_n1 / prev * 100) < N2_MIN_N1_MOVE_PCT:
        return None
    ratio = abs(delta_n2) / abs(delta_n1)
    if ratio >= N2_MODEST_RATIO:
        return None

    return {
        "n2_period": n2_period,
        "n2_value": round(n2_value, 2),
        "n1_period": base_period,
        "n1_value": round(prev, 2),
        "current_value": round(cur, 2),
        "delta_vs_n1": round(delta_n1, 2),
        "delta_vs_n2": round(delta_n2, 2),
        "delta_vs_n1_pct": _safe_pct(delta_n1, prev),
        "delta_vs_n2_pct": _safe_pct(delta_n2, n2_value),
        "ratio_n2_over_n1": round(ratio, 2),
        "threshold_ratio": N2_MODEST_RATIO,
        "interpretation": (
            f"Against an N-2 base ({n2_period}, {n2_value:.2f}) the movement "
            f"is {_safe_pct(delta_n2, n2_value):.1f}% — much smaller than the "
            f"{_safe_pct(delta_n1, prev):.1f}% change vs N-1. The N-1 comparison "
            "is distorted by an anomalous base."
        ),
    }


# ----------------------------------------------------------------------------
# Aggregation + caveat synthesis
# ----------------------------------------------------------------------------

def _aggregate_severity(flags: list[str]) -> str:
    """Map the set of flags to a severity level.

    Rules:
      - 0 flags  → "none"
      - 1 flag   → "watch"
      - 2 flags  → "warn"
      - ≥3 flags → "critical"
      - (D1 + D3) together → "critical" (strong converging evidence)
    """
    if not flags:
        return "none"
    if {"comext_ipi_divergence", "abnormal_prior_year_base"}.issubset(flags):
        return "critical"
    n = len(flags)
    if n == 1:
        return "watch"
    if n == 2:
        return "warn"
    return "critical"


def _build_suggested_caveat(section: str, flags: list[str], evidence: dict) -> str:
    """Synthesise a one-paragraph caveat draft. The LLM rewrites in Cefic voice."""
    parts: list[str] = []

    if "abnormal_prior_year_base" in flags:
        ev = evidence["abnormal_prior_year_base"]
        parts.append(
            f"The comparison base ({ev['base_period']}) is {abs(ev['z_score']):.1f} "
            f"standard deviations {ev['direction']} the mean of the prior "
            f"{ev['prior_window_months']} months "
            f"({ev['base_value']:.2f} vs rolling mean {ev['prior_window_mean']:.2f}), "
            "so the year-on-year movement mechanically overstates the underlying trend."
        )

    if "comext_ipi_divergence" in flags:
        ev = evidence["comext_ipi_divergence"]
        parts.append(
            f"Production indicators (IPI {ev['ipi_yoy_pct']:+.1f}% YoY) show no "
            f"corresponding shock to the {ev['trade_yoy_pct']:+.1f}% trade value "
            "change, a divergence consistent with a composition or base effect."
        )

    if "value_volume_divergence" in flags:
        ev = evidence["value_volume_divergence"]
        parts.append(
            f"Value fell by {abs(ev['value_pct']):.1f}% while volume moved "
            f"{ev['volume_pct']:+.1f}%, indicating a unit-value or mix shift."
        )

    if "partner_concentration" in flags:
        ev = evidence["partner_concentration"]
        top = ", ".join(p["label"] for p in ev["top_2_partners"])
        parts.append(
            f"{ev['top_2_share_of_abs_variation_pct']:.1f}% of the absolute "
            f"variation is attributable to 2 partners ({top})."
        )

    if "n_minus_2_modest" in flags:
        ev = evidence["n_minus_2_modest"]
        parts.append(
            f"Against the N-2 base ({ev['n2_period']}) the change is "
            f"{ev['delta_vs_n2_pct']:+.1f}%, versus {ev['delta_vs_n1_pct']:+.1f}% "
            "vs N-1 — a more representative read of the underlying trend."
        )

    return " ".join(parts) if parts else ""


def _recommend_baseline(flags: list[str], evidence: dict) -> str | None:
    """If N-2 comparison is available, name it as a cleaner baseline."""
    if "n_minus_2_modest" in flags:
        ev = evidence["n_minus_2_modest"]
        return f"Compare to {ev['n2_period']} (N-2) rather than {ev['n1_period']} (N-1)."
    if "abnormal_prior_year_base" in flags:
        return "Use a pre-anomaly baseline (e.g. 2014–2019 average or N-2) for interpretation."
    return None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _trade_yoy_headline(data: dict) -> float | None:
    """Pick the YoY percentage most representative of the headline.

    For multi-month editions, YTD value is the headline. Otherwise single month.
    """
    ytd = data.get("ytd") or {}
    if ytd.get("delta_pct_value") is not None:
        return ytd["delta_pct_value"]
    py = data.get("previous_year") or {}
    return py.get("delta_pct_value")


def _current_value(data: dict) -> float | None:
    """Return the headline current value (trade: value_eur_bn; STS: value)."""
    cur = data.get("current") or {}
    if "value_eur_bn" in cur:
        return cur["value_eur_bn"]
    return cur.get("value")


def _prior_year_value(py: dict) -> float | None:
    if "value_eur_bn" in py:
        return py["value_eur_bn"]
    return py.get("value")


def _prior_window(series: dict, end_period: str, months: int) -> list[float]:
    """Return the N monthly values strictly BEFORE end_period (chronological order)."""
    periods = sorted(series.keys())
    if end_period not in periods:
        cutoff = [p for p in periods if p < end_period]
    else:
        idx = periods.index(end_period)
        cutoff = periods[:idx]
    window = cutoff[-months:] if len(cutoff) >= months else cutoff
    return [series[p] for p in window if series.get(p) is not None]


def _shift_period(period: str, years: int = 0, months: int = 0) -> str:
    y, m = period.split("-")
    y, m = int(y), int(m)
    total = y * 12 + (m - 1) + years * 12 + months
    ny, nm = divmod(total, 12)
    return f"{ny:04d}-{nm+1:02d}"


def _safe_pct(num: float, denom: float) -> float:
    if denom == 0 or denom is None:
        return 0.0
    return round(num / denom * 100, 1)
