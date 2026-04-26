"""Phase 2 tests — editorial checks.
The LLM pattern judge is mocked / no-op'd here (no API key in CI)."""
from editorial_engine.validator.editorial_checks import (
    check_banned_connectors,
    check_emotional_tone,
    check_missing_international_context,
    check_missing_long_term_perspective,
    check_non_cefic_jargon,
    check_patterns_via_llm,
    _parse_llm_flags,
)
from editorial_engine.validator.validator import compute_flags


# ──────────────────────────────────────────────────────────────────────
# 2.2 banned_connector
# ──────────────────────────────────────────────────────────────────────


def test_banned_connector_clean():
    text = "EU27 chemical exports fell 42% in February 2026."
    assert check_banned_connectors(text, "trade_exports") == []


def test_banned_connector_furthermore():
    text = "Exports fell 42%. Furthermore, prices declined 2.8%."
    flags = check_banned_connectors(text, "trade_exports")
    assert any(f.flag_id == "banned_connector" and "furthermore" in f.message.lower() for f in flags)


def test_banned_connector_multi():
    text = "Notably, exports fell. Moreover, imports rose. In conclusion, the picture is mixed."
    flags = check_banned_connectors(text, "macro_brief")
    # 3 distinct connectors
    assert len(flags) == 3


def test_banned_connector_case_insensitive():
    text = "Hence the figure should be qualified."
    flags = check_banned_connectors(text, "macro_brief")
    assert len(flags) == 1


# ──────────────────────────────────────────────────────────────────────
# 2.3 non_cefic_jargon
# ──────────────────────────────────────────────────────────────────────


def test_jargon_clean():
    text = "Producer prices declined by 2.8% in February 2026."
    assert check_non_cefic_jargon(text, "macro_brief") == []


def test_jargon_business_word():
    text = "The strategy is best-in-class for the chemical sector."
    flags = check_non_cefic_jargon(text, "macro_brief")
    assert any(f.flag_id == "non_cefic_jargon" for f in flags)


def test_jargon_vague_intensifier():
    text = "Exports declined significantly in the period."
    flags = check_non_cefic_jargon(text, "trade_exports")
    assert any("vague intensifier" in f.message for f in flags)


def test_jargon_leverage_verb():
    text = "Companies leverage scale to absorb the shock."
    flags = check_non_cefic_jargon(text, "macro_brief")
    assert any("leverage" in f.message.lower() for f in flags)


def test_jargon_economist_mainstream():
    text = "The chemical industry faces significant headwinds and a challenging environment."
    flags = check_non_cefic_jargon(text, "macro_brief")
    # "headwinds", "challenging environment", "significant" — three hits
    assert len(flags) >= 3


# ──────────────────────────────────────────────────────────────────────
# 2.4 missing_long_term_perspective
# ──────────────────────────────────────────────────────────────────────


def test_long_term_anchor_pre_crisis():
    text = (
        "Producer prices declined by 2.8% YoY in February 2026, against the "
        "2014-2019 baseline still 12% above pre-crisis levels. " * 3
    )
    assert check_missing_long_term_perspective(text, "macro_brief", "2026-02") == []


def test_long_term_anchor_rolling():
    text = (
        "Imports rose 4.7% versus the 12-month rolling average of €3.4 bn. " * 4
    )
    assert check_missing_long_term_perspective(text, "trade_imports", "2026-02") == []


def test_long_term_missing_flagged():
    text = (
        "Producer prices declined by 2.8% YoY in February 2026, with the EU27 "
        "running below the prior month. The decline reflects weak demand in core "
        "categories and lower input costs over the period. " * 3
    )
    flags = check_missing_long_term_perspective(text, "macro_brief", "2026-02")
    assert len(flags) == 1
    assert flags[0].flag_id == "missing_long_term_perspective"


def test_long_term_short_section_silent():
    text = "Sales fell 7.5%."  # too short to expect an anchor
    assert check_missing_long_term_perspective(text, "macro_brief", "2026-02") == []


def test_long_term_explicit_old_year_satisfies():
    text = (
        "Imports recovered to levels last seen in 2018, with chemicals running "
        "below the multi-year reference window. " * 4
    )
    assert check_missing_long_term_perspective(text, "trade_imports", "2026-02") == []


# ──────────────────────────────────────────────────────────────────────
# 2.5 missing_international_context
# ──────────────────────────────────────────────────────────────────────


def test_intl_context_present_us():
    text = "Exports to the United States fell 73%."
    assert check_missing_international_context(text, "trade_exports") == []


def test_intl_context_present_china():
    text = "Imports from China rose 4.8% in February."
    assert check_missing_international_context(text, "trade_imports") == []


def test_intl_context_missing_flagged():
    text = "Producer prices fell 2.8% in February 2026 across the bloc."
    flags = check_missing_international_context(text, "macro_brief")
    assert any(f.flag_id == "missing_international_context" for f in flags)


def test_intl_context_not_required_outside_macro_trade():
    # Sources / methodology section doesn't need it
    text = "The publication relies on Eurostat STS and Comext."
    assert check_missing_international_context(text, "sources") == []


# ──────────────────────────────────────────────────────────────────────
# 2.6 emotional_tone
# ──────────────────────────────────────────────────────────────────────


def test_emotional_clean():
    text = "Exports fell 42% in the first two months of 2026."
    assert check_emotional_tone(text, "trade_exports") == []


def test_emotional_cheerleading():
    text = "Promising signs in the chemical sector — production held steady."
    flags = check_emotional_tone(text, "macro_brief")
    assert any(f.flag_id == "emotional_tone" for f in flags)


def test_emotional_catastrophism():
    text = "The collapse of EU27 chemical exports is alarming."
    flags = check_emotional_tone(text, "trade_exports")
    # 'collapse' + 'alarming'
    assert len(flags) == 2


def test_emotional_pre_crisis_is_neutral():
    # 'pre-crisis levels' is a Cefic reference baseline, not catastrophism.
    text = "EU27 chemical production sits 18% below pre-crisis levels (2014-2019)."
    assert check_emotional_tone(text, "macro_brief") == []


def test_emotional_bare_crisis_still_flagged():
    text = "The crisis weighed on European chemical output."
    flags = check_emotional_tone(text, "macro_brief")
    assert any(f.flag_id == "emotional_tone" for f in flags)


# ──────────────────────────────────────────────────────────────────────
# 2.1 LLM pattern judge — only the offline path is unit-tested
# ──────────────────────────────────────────────────────────────────────


def test_llm_pattern_check_no_key_silent(monkeypatch):
    # Force key absence; the function must return [] without raising.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    flags = check_patterns_via_llm("Exports fell 42%.", "trade_exports")
    assert flags == []


def test_llm_response_parser_clean():
    raw = '{"flags": [{"pattern_id": 14, "severity": "warning", "message": "missing trade-formula opening", "citation": "Exports fell 42%"}]}'
    flags = _parse_llm_flags(raw, "trade_exports")
    assert len(flags) == 1
    assert flags[0].flag_id == "pattern_missing_14"
    assert flags[0].severity == "warning"
    assert flags[0].pattern_ref == "SYNTHESIS.md pattern 14"


def test_llm_response_parser_with_code_fence():
    raw = "```json\n{\"flags\": [{\"pattern_id\": 22, \"severity\": \"info\", \"message\": \"x\", \"citation\": \"\"}]}\n```"
    flags = _parse_llm_flags(raw, "trade_exports")
    assert len(flags) == 1
    assert flags[0].flag_id == "pattern_missing_22"


def test_llm_response_parser_garbage():
    flags = _parse_llm_flags("sorry I cannot help with this", "macro_brief")
    assert flags == []


# ──────────────────────────────────────────────────────────────────────
# Validator entry point — composition of factual + editorial
# ──────────────────────────────────────────────────────────────────────


def test_compute_flags_runs_both_layers():
    text = (
        "Exports fell 42.1% in the first two months of 2026, amounting to "
        "€34.5 bn. Furthermore, prices declined significantly in the period. "
        "The figure reflects an unusually high base in February 2025."
    )
    fiche = {"yoy_pct": -42.1, "total_value_eur_bn": 34.5}
    flags = compute_flags(text, fiche, "trade_exports", edition_month="2026-02", use_llm=False)
    flag_ids = {f.flag_id for f in flags}
    # Editorial flags fire (banned connector + jargon), factual stays quiet
    assert "banned_connector" in flag_ids
    assert "non_cefic_jargon" in flag_ids
    # missing_international_context should also fire (no US / China / UK mention)
    assert "missing_international_context" in flag_ids
