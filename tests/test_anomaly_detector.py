"""Unit + integration tests for analysis.anomaly_detector.

Covers each detector (D1–D5) in isolation, aggregation logic, and an
integration test on the real 2026-02 trade_exports fiche — the case that
motivated the module.
"""

import json
from pathlib import Path

from analysis.anomaly_detector import (
    AnomalyReport,
    detect_base_effects,
    _detect_comext_ipi_divergence,
    _detect_value_volume_divergence,
    _detect_abnormal_prior_year_base,
    _detect_partner_concentration,
    _detect_n_minus_2_modest,
    _aggregate_severity,
    _shift_period,
)


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------

def _trade_fiche_2026_02() -> dict:
    """Mimic the 2026-02 trade_exports fiche — headline numbers only."""
    return {
        "section_type": "trade_exports",
        "period": {"month": "2026-02", "window_months": 2},
        "data": {
            "current": {"value_eur_bn": 18.18, "volume_kt": 5633.7, "period": "2026-02"},
            "previous_year": {
                "value_eur_bn": 31.64, "volume_kt": 6959.2, "period": "2025-02",
                "delta_pct_value": -42.5, "delta_pct_volume": -19.0,
            },
            "ytd": {
                "current_value_eur_bn": 34.48,
                "previous_year_value_eur_bn": 59.53,
                "delta_pct_value": -42.1,
                "delta_pct_volume": -17.4,
                "window_months": 2,
            },
            "by_partner": [
                {"partner": "US", "label": "United States",
                 "value_eur_bn": 3.56, "previous_year_value_eur_bn": 12.95, "yoy_pct": -72.5},
                {"partner": "GB", "label": "United Kingdom",
                 "value_eur_bn": 2.13, "previous_year_value_eur_bn": 2.03, "yoy_pct": 4.9},
                {"partner": "CN", "label": "China",
                 "value_eur_bn": 1.40, "previous_year_value_eur_bn": 1.51, "yoy_pct": -7.3},
                {"partner": "TR", "label": "Türkiye",
                 "value_eur_bn": 1.01, "previous_year_value_eur_bn": 1.19, "yoy_pct": -14.4},
                {"partner": "CH", "label": "Switzerland",
                 "value_eur_bn": 0.97, "previous_year_value_eur_bn": 3.99, "yoy_pct": -75.6},
            ],
        },
    }


def _historical_series_2026_02() -> dict:
    """Real monthly EU27 exports €bn from the parquet (2024-01 .. 2026-02)."""
    eu27 = {
        "2024-01": 20.54, "2024-02": 20.22, "2024-03": 22.47, "2024-04": 20.69,
        "2024-05": 21.68, "2024-06": 21.81, "2024-07": 22.51, "2024-08": 20.86,
        "2024-09": 22.23, "2024-10": 23.56, "2024-11": 22.81, "2024-12": 20.45,
        "2025-01": 27.88, "2025-02": 31.64, "2025-03": 41.18, "2025-04": 22.84,
        "2025-05": 24.76, "2025-06": 19.92, "2025-07": 20.50, "2025-08": 16.60,
        "2025-09": 29.25, "2025-10": 18.33, "2025-11": 18.22, "2025-12": 17.79,
        "2026-01": 16.30, "2026-02": 18.18,
    }
    return {"eu27_total": eu27}


def _related_indicators_2026_02() -> dict:
    """Matching IPI and PPI YoY from the other 2026-02 fiches."""
    return {"output_ipi_yoy_pct": -3.9, "prices_ppi_yoy_pct": -2.8}


# ----------------------------------------------------------------------------
# Individual detectors
# ----------------------------------------------------------------------------

def test_d1_comext_ipi_divergence_triggers():
    data = _trade_fiche_2026_02()["data"]
    result = _detect_comext_ipi_divergence(data, _related_indicators_2026_02())
    assert result is not None, "D1 should fire: -42.1% trade vs -3.9% IPI"
    assert result["trade_yoy_pct"] == -42.1
    assert result["ipi_yoy_pct"] == -3.9
    assert result["ratio"] == 10.8  # 42.1 / 3.9


def test_d1_no_fire_when_ipi_also_shocks():
    """If IPI also down sharply, it's a real shock, not a base effect."""
    data = _trade_fiche_2026_02()["data"]
    result = _detect_comext_ipi_divergence(data, {"output_ipi_yoy_pct": -15.0})
    assert result is None


def test_d1_no_fire_when_trade_moderate():
    data = _trade_fiche_2026_02()["data"]
    data["ytd"]["delta_pct_value"] = -5.0
    result = _detect_comext_ipi_divergence(data, _related_indicators_2026_02())
    assert result is None


def test_d2_value_volume_divergence_triggers():
    data = _trade_fiche_2026_02()["data"]
    result = _detect_value_volume_divergence(data)
    assert result is not None
    assert result["value_pct"] == -42.1
    assert result["volume_pct"] == -17.4
    assert result["ratio"] == 2.42  # 42.1 / 17.4
    assert result["window"] == "ytd"


def test_d2_no_fire_when_aligned():
    data = {
        "ytd": {"delta_pct_value": -10.0, "delta_pct_volume": -8.0},
    }
    result = _detect_value_volume_divergence(data)
    assert result is None


def test_d3_abnormal_prior_year_base_triggers():
    data = _trade_fiche_2026_02()["data"]
    hist = _historical_series_2026_02()
    result = _detect_abnormal_prior_year_base(data, hist)
    # Feb 2025 = 31.64. Prior 12m (Feb 2024 .. Jan 2025) mean ≈ 22.1, std ≈ 2.
    # Z-score should be well above 2.
    assert result is not None
    assert result["base_period"] == "2025-02"
    assert result["base_value"] == 31.64
    assert result["z_score"] > 2.0
    assert result["direction"] == "above"


def test_d3_no_fire_on_stable_series():
    data = {"previous_year": {"period": "2025-02", "value_eur_bn": 22.0}}
    stable = {f"2024-{m:02d}": 22.0 + 0.1 * m for m in range(1, 13)}
    stable["2025-01"] = 22.0
    result = _detect_abnormal_prior_year_base(data, {"eu27_total": stable})
    # 22.0 is within 2σ of a tight series → no flag
    assert result is None


def test_d4_partner_concentration_triggers():
    data = _trade_fiche_2026_02()["data"]
    result = _detect_partner_concentration(data)
    # US delta = 3.56 - 12.95 = -9.39
    # CH delta = 0.97 - 3.99 = -3.02
    # TR delta = 1.01 - 1.19 = -0.18
    # CN delta = 1.40 - 1.51 = -0.11
    # GB delta = 2.13 - 2.03 = +0.10
    # Total |Δ| = 9.39 + 3.02 + 0.18 + 0.11 + 0.10 = 12.80
    # Top-2 (US+CH) = 12.41 → 97.0%
    assert result is not None
    assert result["top_2_share_of_abs_variation_pct"] > 90
    assert result["top_2_partners"][0]["partner"] == "US"
    assert result["top_2_partners"][1]["partner"] == "CH"


def test_d4_no_fire_when_spread():
    data = {"by_partner": [
        {"partner": "A", "value_eur_bn": 10, "previous_year_value_eur_bn": 5},
        {"partner": "B", "value_eur_bn": 10, "previous_year_value_eur_bn": 5},
        {"partner": "C", "value_eur_bn": 10, "previous_year_value_eur_bn": 5},
        {"partner": "D", "value_eur_bn": 10, "previous_year_value_eur_bn": 5},
    ]}
    result = _detect_partner_concentration(data)
    # All equal contributions → top-2 = 50%, below 75% threshold
    assert result is None


def test_d5_n_minus_2_modest_triggers():
    data = _trade_fiche_2026_02()["data"]
    hist = _historical_series_2026_02()
    # Feb 2026 single-month: 18.18
    # Feb 2025 (N-1) = 31.64, Feb 2024 (N-2) = 20.22
    # Δ vs N-1 = -13.46 → -42.5%
    # Δ vs N-2 =  -2.04 → -10.1%
    # ratio = 2.04/13.46 = 0.15 < 0.5 → fire
    result = _detect_n_minus_2_modest(data, hist)
    assert result is not None
    assert result["n2_period"] == "2024-02"
    assert abs(result["delta_vs_n2_pct"] - (-10.1)) < 0.5
    assert result["ratio_n2_over_n1"] < 0.5


def test_d5_no_fire_when_consistent():
    data = {
        "current": {"value_eur_bn": 10.0},
        "previous_year": {"period": "2025-02", "value_eur_bn": 15.0},
    }
    # N-2 = 20 → Δ vs N-1 = -5, Δ vs N-2 = -10. ratio = 10/5 = 2 > 0.5 → no fire
    hist = {"eu27_total": {"2024-02": 20.0, "2025-02": 15.0}}
    result = _detect_n_minus_2_modest(data, hist)
    assert result is None


# ----------------------------------------------------------------------------
# Aggregation + period shift
# ----------------------------------------------------------------------------

def test_severity_rules():
    assert _aggregate_severity([]) == "none"
    assert _aggregate_severity(["x"]) == "watch"
    assert _aggregate_severity(["x", "y"]) == "warn"
    assert _aggregate_severity(["x", "y", "z"]) == "critical"
    # D1 + D3 combo → critical even at 2 flags
    assert _aggregate_severity(
        ["comext_ipi_divergence", "abnormal_prior_year_base"]
    ) == "critical"


def test_shift_period():
    assert _shift_period("2026-02", years=-1) == "2025-02"
    assert _shift_period("2026-02", years=-2) == "2024-02"
    assert _shift_period("2026-02", months=-1) == "2026-01"
    assert _shift_period("2026-01", months=-1) == "2025-12"


# ----------------------------------------------------------------------------
# Integration — the 2026-02 scenario end-to-end
# ----------------------------------------------------------------------------

def test_integration_2026_02_is_critical():
    """The real 2026-02 fiche must raise D1+D2+D3+D4+D5 with severity=critical."""
    fiche = _trade_fiche_2026_02()
    hist = _historical_series_2026_02()
    related = _related_indicators_2026_02()

    report = detect_base_effects(fiche, hist, related)

    assert isinstance(report, AnomalyReport)
    assert "comext_ipi_divergence" in report.flags
    assert "value_volume_divergence" in report.flags
    assert "abnormal_prior_year_base" in report.flags
    assert "partner_concentration" in report.flags
    assert "n_minus_2_modest" in report.flags
    assert report.severity == "critical"
    assert report.suggested_caveat is not None
    assert len(report.suggested_caveat) > 100
    assert report.recommended_baseline is not None


def test_no_flags_produces_clean_report():
    fiche = {
        "section_type": "trade_exports",
        "data": {
            "current": {"value_eur_bn": 20.0, "period": "2026-02"},
            "previous_year": {"period": "2025-02", "value_eur_bn": 20.5,
                               "delta_pct_value": -2.4, "delta_pct_volume": -1.8},
            "ytd": {"delta_pct_value": -2.0, "delta_pct_volume": -1.5},
            "by_partner": [
                {"partner": "A", "value_eur_bn": 5, "previous_year_value_eur_bn": 5.1},
                {"partner": "B", "value_eur_bn": 5, "previous_year_value_eur_bn": 5.1},
                {"partner": "C", "value_eur_bn": 5, "previous_year_value_eur_bn": 5.1},
                {"partner": "D", "value_eur_bn": 5, "previous_year_value_eur_bn": 5.1},
            ],
        },
    }
    stable = {f"2024-{m:02d}": 20.0 + 0.05 * m for m in range(1, 13)}
    stable.update({f"2025-{m:02d}": 20.0 + 0.05 * m for m in range(1, 13)})
    hist = {"eu27_total": stable}
    related = {"output_ipi_yoy_pct": -2.0}

    report = detect_base_effects(fiche, hist, related)
    assert report.flags == []
    assert report.severity == "none"
    assert report.suggested_caveat is None


if __name__ == "__main__":
    import sys
    import traceback
    fns = [g for n, g in list(globals().items()) if n.startswith("test_") and callable(g)]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
