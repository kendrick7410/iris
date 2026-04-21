"""Smoke tests for the macro brief module (L5).

Covers:
  - quality check logic (heading, word count, bullets, numbers, banned)
  - fiche assembly from mock fiches
  - KPI fallback when capacity is absent
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from editorial_engine.macro_brief import _quality_check, _strip_heading
from analysis.indicators import build_macro_brief_fiche


def _mk_output_fiche(val=79.3, yoy=-3.9):
    return {
        "section_type": "output",
        "period": {"month": "2026-02"},
        "data": {
            "current": {"value": val, "unit": "index 2021=100"},
            "previous_year": {"delta_pct": yoy},
        },
    }


def _mk_prices_fiche(val=117.2, yoy=-2.8):
    return {
        "section_type": "prices",
        "period": {"month": "2026-02"},
        "data": {
            "current": {"value": val, "unit": "index 2021=100"},
            "previous_year": {"delta_pct": yoy},
        },
    }


def _mk_trade_fiche(direction, val=17.79, yoy_val=-13.0, yoy_vol=-3.0, partners=None):
    return {
        "section_type": f"trade_{direction}",
        "period": {"month": "2026-02"},
        "data": {
            "current": {"value_eur_bn": val},
            "previous_year": {"value_eur_bn": val * 1.1,
                               "delta_pct_value": yoy_val,
                               "delta_pct_volume": yoy_vol},
            "by_partner": partners or [
                {"partner": "US", "share_pct": 14.6, "label": "United States"},
                {"partner": "GB", "share_pct": 10.0, "label": "United Kingdom"},
                {"partner": "CN", "share_pct": 8.6, "label": "China"},
                {"partner": "TR", "share_pct": 5.4, "label": "Türkiye"},
                {"partner": "KR", "share_pct": 5.1, "label": "South Korea"},
            ],
        },
    }


def test_quality_check_pass():
    text = (
        "## EU27 chemical output down 3.9% in February 2026\n\n"
        "EU27 chemical production stood at 79.3 in February 2026, down by 3.9% "
        "compared to February 2025. The sector remains 18.0% below pre-crisis "
        "levels (2014-2019 average). Poland posted the strongest growth at 3.1% "
        "while Belgium declined by 4.5%, with six of seven countries losing "
        "ground between early 2022 and the current period."
    )
    qc = _quality_check(text)
    assert qc["has_heading"], qc
    assert qc["bullets_ok"], qc
    assert qc["banned_ok"], qc
    assert qc["numbers"] >= 3, qc
    print(f"  quality_check pass: {qc['words']} words, {qc['numbers']} numbers")


def test_quality_check_catches_banned():
    text = ("## A heading with 5.0% and 3.2% figures present for realism\n\n"
            "Furthermore, 5.0% is the figure. Moreover, 3.2% is another. "
            "Consequently the indicator declined by 1.0%.")
    qc = _quality_check(text)
    assert not qc["banned_ok"]
    assert "furthermore" in qc["banned_found"]
    print(f"  banned caught: {qc['banned_found']}")


def test_quality_check_catches_bullets():
    text = "## Heading with 1.0% figure attached here\n\n- bullet one\n- bullet two"
    qc = _quality_check(text)
    assert not qc["bullets_ok"]
    print(f"  bullets caught: {qc['bullets']}")


def test_strip_heading():
    text = "## Heading line\n\nBody paragraph."
    heading, body = _strip_heading(text)
    assert heading == "## Heading line"
    assert body == "Body paragraph."
    print("  strip_heading OK")


def test_build_macro_brief_fiche_three_kpis():
    with tempfile.TemporaryDirectory() as tmp:
        fiches = Path(tmp) / "fiches"
        fiches.mkdir()
        (fiches / "output.json").write_text(json.dumps(_mk_output_fiche()))
        (fiches / "prices.json").write_text(json.dumps(_mk_prices_fiche()))
        (fiches / "trade_exports.json").write_text(json.dumps(_mk_trade_fiche("exports")))
        (fiches / "trade_imports.json").write_text(json.dumps(_mk_trade_fiche("imports", val=21.0)))

        path = build_macro_brief_fiche(fiches, Path(tmp))
        data = json.loads(path.read_text())
        assert data["section_type"] == "macro_brief"
        assert len(data["kpis"]) == 3, f"Expected 3 KPIs, got {len(data['kpis'])}"
        keys = [k["key"] for k in data["kpis"]]
        assert "output_yoy" in keys
        assert "trade_balance_yoy" in keys
        assert "prices_yoy" in keys
        assert "capacity_yoy" not in keys
        # volume/value divergence flag: yoy_val=-13 vs yoy_vol=-3 → gap 10 pp
        assert "volume_value_divergence" in data["headline_data"]
        # Pareto: top-5 share = 14.6+10+8.6+5.4+5.1 = 43.7 < 50 → flag absent
        assert "concentration_pareto" not in data["headline_data"]
        print(f"  3 KPIs assembled, duality flag present, Pareto absent (43.7%)")


def test_build_macro_brief_fiche_four_kpis_with_capacity():
    with tempfile.TemporaryDirectory() as tmp:
        fiches = Path(tmp) / "fiches"
        fiches.mkdir()
        (fiches / "output.json").write_text(json.dumps(_mk_output_fiche()))
        (fiches / "prices.json").write_text(json.dumps(_mk_prices_fiche()))
        (fiches / "trade_exports.json").write_text(json.dumps(_mk_trade_fiche("exports")))
        (fiches / "trade_imports.json").write_text(json.dumps(_mk_trade_fiche("imports", val=21.0)))
        (fiches / "capacity.json").write_text(json.dumps({
            "data": {
                "current": {"value": 74.0, "unit": "%"},
                "previous_year": {"delta_pp": -0.8},
            }
        }))

        path = build_macro_brief_fiche(fiches, Path(tmp))
        data = json.loads(path.read_text())
        assert len(data["kpis"]) == 4
        keys = [k["key"] for k in data["kpis"]]
        assert "capacity_yoy" in keys
        print("  4 KPIs assembled including capacity")


def test_build_macro_brief_fiche_pareto_triggered():
    partners = [
        {"partner": "US", "share_pct": 20.0, "label": "United States"},
        {"partner": "GB", "share_pct": 18.0, "label": "United Kingdom"},
        {"partner": "CN", "share_pct": 15.0, "label": "China"},
        {"partner": "TR", "share_pct": 10.0, "label": "Türkiye"},
        {"partner": "KR", "share_pct": 8.0, "label": "South Korea"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        fiches = Path(tmp) / "fiches"
        fiches.mkdir()
        (fiches / "output.json").write_text(json.dumps(_mk_output_fiche()))
        (fiches / "trade_exports.json").write_text(json.dumps(
            _mk_trade_fiche("exports", partners=partners)))
        (fiches / "trade_imports.json").write_text(json.dumps(_mk_trade_fiche("imports")))

        path = build_macro_brief_fiche(fiches, Path(tmp))
        data = json.loads(path.read_text())
        # Pareto: 20+18+15+10+8 = 71 ≥ 50 → triggered
        assert "concentration_pareto" in data["headline_data"]
        assert data["headline_data"]["concentration_pareto"]["share_pct"] == 71.0
        print("  Pareto triggered at 71% top-5 share")


if __name__ == "__main__":
    print("Testing macro brief...")
    test_quality_check_pass()
    test_quality_check_catches_banned()
    test_quality_check_catches_bullets()
    test_strip_heading()
    test_build_macro_brief_fiche_three_kpis()
    test_build_macro_brief_fiche_four_kpis_with_capacity()
    test_build_macro_brief_fiche_pareto_triggered()
    print("All macro brief tests passed.")
