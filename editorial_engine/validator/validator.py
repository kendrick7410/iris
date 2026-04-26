"""Validator entry point.

Composes the deterministic factual + editorial checks, plus the optional
LLM pattern judge. Caller side controls whether the LLM is invoked
(`use_llm=False` for tests, True for the pipeline run).

  flags = compute_flags(section_text, fiche, section_type, ...)
  flags = compute_flags_inter(sections, fiches)        # cross-section pass
"""
from __future__ import annotations

from pathlib import Path

from .flag import Flag
from .factual_checks import (
    check_direction_mismatch,
    check_implausible_magnitude,
    check_inter_section_inconsistency,
    check_numerical_inconsistency,
    check_temporal_inconsistency,
)
from .editorial_checks import (
    check_banned_connectors,
    check_emotional_tone,
    check_missing_international_context,
    check_missing_long_term_perspective,
    check_non_cefic_jargon,
    check_patterns_via_llm,
)


def compute_flags(
    section_text: str,
    fiche: dict,
    section_type: str,
    edition_month: str | None = None,
    *,
    use_llm: bool = False,
    llm_log_path: Path | None = None,
) -> list[Flag]:
    """Run every per-section check and return a flat flag list.
    LLM pattern judge runs only when `use_llm=True` and an API key is set."""
    flags: list[Flag] = []
    # Niveau 1 — factual
    flags += check_numerical_inconsistency(section_text, fiche, section_type)
    flags += check_direction_mismatch(section_text, section_type)
    flags += check_implausible_magnitude(section_text, section_type)
    if edition_month:
        flags += check_temporal_inconsistency(section_text, section_type, edition_month)
    # Niveau 2 — editorial (deterministic)
    flags += check_banned_connectors(section_text, section_type)
    flags += check_non_cefic_jargon(section_text, section_type)
    flags += check_missing_long_term_perspective(section_text, section_type, edition_month)
    flags += check_missing_international_context(section_text, section_type)
    flags += check_emotional_tone(section_text, section_type)
    # Niveau 2 — editorial (LLM-judged pattern check, optional)
    if use_llm:
        flags += check_patterns_via_llm(section_text, section_type, log_path=llm_log_path)
    return flags


def compute_flags_inter(
    sections: dict[str, str],
    fiches: dict[str, dict],
) -> list[Flag]:
    """Cross-section consistency. Run once per edition after every section
    has been drafted."""
    return check_inter_section_inconsistency(sections, fiches)
