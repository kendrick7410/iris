"""Phase 1 tests — factual checks (5 checks, each: positive + negative + edge).
Run with `python -m pytest editorial_engine/validator/tests -v`.
"""
from editorial_engine.validator.factual_checks import (
    check_direction_mismatch,
    check_implausible_magnitude,
    check_inter_section_inconsistency,
    check_numerical_inconsistency,
    check_temporal_inconsistency,
)
from editorial_engine.validator.validator import compute_flags, compute_flags_inter
from editorial_engine.validator.flag import ValidationReport, Flag


# ──────────────────────────────────────────────────────────────────────
# 1.1 numerical_inconsistency
# ──────────────────────────────────────────────────────────────────────


def test_num_match_within_tolerance():
    text = "EU27 chemical exports fell by 42.1% in value."
    fiche = {"yoy_pct": -42.0}  # within 0.5 pp tolerance of 42.1
    assert check_numerical_inconsistency(text, fiche, "trade_exports") == []


def test_num_drift_beyond_tolerance():
    text = "EU27 chemical exports fell by 42.1% in value."
    fiche = {"yoy_pct": -38.0}  # 4 pp off
    flags = check_numerical_inconsistency(text, fiche, "trade_exports")
    assert len(flags) == 1
    assert flags[0].flag_id == "numerical_inconsistency"
    assert flags[0].severity == "critical"


def test_num_eur_bn_match():
    text = "Exports amounted to €34.5 bn in the first two months of 2026."
    fiche = {"total_value_eur_bn": 34.51}  # within 0.05
    assert check_numerical_inconsistency(text, fiche, "trade_exports") == []


def test_num_eur_bn_drift():
    text = "Exports amounted to €34.5 bn."
    fiche = {"total_value_eur_bn": 34.71}  # 0.21 off
    flags = check_numerical_inconsistency(text, fiche, "trade_exports")
    assert len(flags) == 1
    assert "€34.50 bn" in flags[0].message


def test_num_negative_signed_pct():
    text = "Imports declined by -2.8% year-on-year."
    fiche = {"yoy_pct": -2.8}
    assert check_numerical_inconsistency(text, fiche, "trade_imports") == []


def test_num_walks_nested_fiche():
    text = "The largest current flow remains polypeptide hormones (€0.9 bn)."
    fiche = {
        "partner_drilldown": {
            "CN": {"top_movers_up": [{"label": "polypeptide", "delta_eur_bn": 0.92}]},
        },
    }
    assert check_numerical_inconsistency(text, fiche, "trade_imports") == []


# ──────────────────────────────────────────────────────────────────────
# 1.2 inter_section_inconsistency
# ──────────────────────────────────────────────────────────────────────


def test_inter_section_match():
    sections = {
        "overview": "EU27 chemical exports amounted to €34.5 bn.",
        "trade_exports": "EU27 chemical exports amounted to €34.5 bn in the period.",
    }
    assert check_inter_section_inconsistency(sections, {}) == []


def test_inter_section_disagree_eur_bn():
    sections = {
        "overview": "EU27 chemical exports amounted to €34.5 bn.",
        "trade_exports": "EU27 chemical exports amounted to €36.2 bn.",
    }
    flags = check_inter_section_inconsistency(sections, {})
    assert any(f.flag_id == "inter_section_inconsistency" for f in flags)


def test_inter_section_within_rounding_pct():
    sections = {
        "overview": "EU27 chemical production fell 3.9% YoY.",
        "macro_brief": "EU27 chemical production fell 4.0% YoY.",
    }
    # 0.1pp delta < 0.5pp tolerance
    flags = check_inter_section_inconsistency(sections, {})
    assert flags == []


# ──────────────────────────────────────────────────────────────────────
# 1.3 direction_mismatch
# ──────────────────────────────────────────────────────────────────────


def test_direction_match_positive():
    text = "Imports rose by 4.7% to €3.7 bn."
    assert check_direction_mismatch(text, "trade_imports") == []


def test_direction_match_negative():
    text = "Exports fell by 42.1% in the period."
    assert check_direction_mismatch(text, "trade_exports") == []


def test_direction_mismatch_positive_verb_negative_value():
    text = "Imports rose by -4.7% in the period."
    flags = check_direction_mismatch(text, "trade_imports")
    assert any(f.flag_id == "direction_mismatch" for f in flags)


def test_direction_mismatch_stable_with_large_value():
    # Construct one that actually parses through the verb-by-N% pattern.
    text = "Producer prices held by 8% over the year."
    flags = check_direction_mismatch(text, "macro_brief")
    assert any(f.flag_id == "direction_mismatch" for f in flags)


def test_direction_neutral_below_stable_threshold():
    text = "Producer prices held at 0.4% above the prior reading."
    assert check_direction_mismatch(text, "macro_brief") == []


# ──────────────────────────────────────────────────────────────────────
# 1.4 implausible_magnitude
# ──────────────────────────────────────────────────────────────────────


def test_magnitude_normal_value_quiet():
    text = "Production fell 3.9% YoY."
    assert check_implausible_magnitude(text, "macro_brief") == []


def test_magnitude_pct_above_threshold_macro():
    text = "Production rose 145% YoY in February."
    flags = check_implausible_magnitude(text, "macro_brief")
    assert any(f.flag_id == "implausible_magnitude" for f in flags)


def test_magnitude_pct_high_but_under_trade_threshold():
    text = "Polypeptide hormones added 438% of the net variation."
    # Trade threshold is 500%, 438 should not fire
    flags = check_implausible_magnitude(text, "trade_imports")
    assert flags == []


def test_magnitude_eur_bn_above_threshold():
    text = "Exports added €312 bn in the month, exceptional."
    flags = check_implausible_magnitude(text, "trade_exports")
    assert any(f.flag_id == "implausible_magnitude" for f in flags)


# ──────────────────────────────────────────────────────────────────────
# 1.5 temporal_inconsistency
# ──────────────────────────────────────────────────────────────────────


def test_temporal_match():
    text = "In February 2026, EU27 chemical production fell 3.9%."
    assert check_temporal_inconsistency(text, "macro_brief", "2026-02") == []


def test_temporal_yoy_baseline_fine():
    text = "Against the February 2024 base, exports are down by approximately 10%."
    # 2024 is older than YoY but allowed (2014-2019 baseline class), shouldn't flag
    # This rule fires only on first-N-months patterns
    assert check_temporal_inconsistency(text, "trade_exports", "2026-02") == []


def test_temporal_future_month_flagged():
    text = "Exports are projected to recover in June 2026."
    flags = check_temporal_inconsistency(text, "trade_exports", "2026-02")
    assert any(f.flag_id == "temporal_inconsistency" for f in flags)


def test_temporal_first_two_months_correct_year():
    text = "Exports amounted to €34.5 bn in the first two months of 2026."
    assert check_temporal_inconsistency(text, "trade_exports", "2026-02") == []


def test_temporal_first_two_months_wrong_year():
    text = "Exports rose in the first two months of 2024 against the prior year."
    flags = check_temporal_inconsistency(text, "trade_exports", "2026-02")
    assert any(f.flag_id == "temporal_inconsistency" for f in flags)


# ──────────────────────────────────────────────────────────────────────
# Validator entry point + ValidationReport
# ──────────────────────────────────────────────────────────────────────


def test_compute_flags_aggregates():
    text = (
        "Exports rose by -42.1% in the first two months of 2026, "  # direction mismatch
        "amounting to €34.5 bn."
    )
    fiche = {"yoy_pct": -42.1, "total_value_eur_bn": 34.5}
    flags = compute_flags(text, fiche, "trade_exports", edition_month="2026-02")
    # Direction mismatch must trigger; numerical should be quiet (matches)
    assert any(f.flag_id == "direction_mismatch" for f in flags)
    assert not any(f.flag_id == "numerical_inconsistency" for f in flags)


def test_validation_report_summary():
    report = ValidationReport(
        edition_month="2026-02",
        validated_at="2026-04-23T14:32:00Z",
        sections_validated=["macro_brief", "trade_exports"],
        flags=[
            Flag(flag_id="direction_mismatch", severity="critical",
                 section="trade_exports", message="x"),
            Flag(flag_id="numerical_inconsistency", severity="critical",
                 section="macro_brief", message="x"),
            Flag(flag_id="banned_connector", severity="warning",
                 section="macro_brief", message="x"),
        ],
    )
    s = report.summary()
    assert s["critical_count"] == 2
    assert s["warning_count"] == 1
    assert s["info_count"] == 0
    assert s["sections_validated"] == 2


def test_compute_flags_inter_no_overlap_silent():
    sections = {
        "overview": "Production fell 3.9% YoY.",
        "trade_exports": "Exports rose 5%.",  # no shared anchor with overview
    }
    flags = compute_flags_inter(sections, {})
    assert flags == []
