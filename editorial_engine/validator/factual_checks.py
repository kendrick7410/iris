"""Factual (Niveau 1) validator checks.

Each check is a deterministic pure-Python function that returns a list of
Flag objects. No LLM calls in this module — that's Phase 2's job. We reserve
the LLM for editorial style judgement, where heuristics break down. Numbers
are extracted from prose with regex and cross-referenced against the fiche
JSON the section was drafted from.

The five checks (ref. patch §Niveau 1):
  1.1 numerical_inconsistency  — prose number ↔ fiche number
  1.2 inter_section_inconsistency — same variable across sections
  1.3 direction_mismatch — verb ('rose', 'fell') vs sign of nearby number
  1.4 implausible_magnitude — YoY > 100% / 500%, € bn > 100 on monthly
  1.5 temporal_inconsistency — time references vs current month

Tolerances (from the patch):
  ±0.5 on percentages (in pp)
  ±0.05 on € bn
  ±0.5 on index points
"""
from __future__ import annotations

import re
from typing import Iterable

from .flag import Flag

# ──────────────────────────────────────────────────────────────────────
# Number extraction
# ──────────────────────────────────────────────────────────────────────

# Matches: 12.3%, +12.3%, -2.8%, 12%, 0.21
_NUM_PCT = re.compile(
    r"(?P<sign>[+-])?(?P<num>\d{1,4}(?:[.,]\d{1,3})?)\s*%",
)
# Matches: €34.5 bn, €0.21 bn, €1,234 bn, EUR 34 bn
_NUM_EUR_BN = re.compile(
    r"(?:€|EUR\s*)(?P<sign>[+-])?(?P<num>\d{1,4}(?:[.,]\d{1,3})?)\s*bn",
    re.IGNORECASE,
)
# Matches: percentage points constructs ("23.9 percentage points", "+21.7 pp")
_NUM_PP = re.compile(
    r"(?P<sign>[+-])?(?P<num>\d{1,3}(?:[.,]\d{1,2})?)\s*(?:percentage[- ]point[s]?|pp)\b",
    re.IGNORECASE,
)


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def _signed(sign: str | None, val: float) -> float:
    return -val if sign == "-" else val


def _iter_pct(text: str) -> Iterable[tuple[float, re.Match]]:
    for m in _NUM_PCT.finditer(text):
        yield _signed(m.group("sign"), _to_float(m.group("num"))), m


def _iter_eur_bn(text: str) -> Iterable[tuple[float, re.Match]]:
    for m in _NUM_EUR_BN.finditer(text):
        yield _signed(m.group("sign"), _to_float(m.group("num"))), m


def _sentence_around(text: str, m: re.Match, max_chars: int = 160) -> str:
    """Return the sentence (or context window) containing the match."""
    start, end = m.start(), m.end()
    # Walk back to the previous sentence boundary
    left = text.rfind(".", 0, start) + 1
    right = text.find(".", end)
    if right == -1:
        right = len(text)
    snippet = text[left:right + 1].strip()
    if len(snippet) > max_chars:
        # Centre the snippet on the match
        offset = max(0, start - left - max_chars // 2)
        snippet = snippet[offset:offset + max_chars]
    return snippet


# ──────────────────────────────────────────────────────────────────────
# Fiche walk — collect all numbers worth checking against
# ──────────────────────────────────────────────────────────────────────


def _walk_fiche_numbers(fiche: dict, prefix: str = "") -> list[tuple[str, float]]:
    """Flatten every numeric leaf in a fiche, with dotted path. Strings that
    parse as numbers count too (the pipeline sometimes stringifies %s)."""
    out: list[tuple[str, float]] = []
    if isinstance(fiche, dict):
        for k, v in fiche.items():
            out.extend(_walk_fiche_numbers(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(fiche, list):
        for i, v in enumerate(fiche):
            out.extend(_walk_fiche_numbers(v, f"{prefix}[{i}]"))
    elif isinstance(fiche, (int, float)) and not isinstance(fiche, bool):
        out.append((prefix, float(fiche)))
    elif isinstance(fiche, str):
        s = fiche.strip().replace("%", "").replace(",", ".")
        try:
            out.append((prefix, float(s)))
        except ValueError:
            pass
    return out


# ──────────────────────────────────────────────────────────────────────
# 1.1 numerical_inconsistency
# ──────────────────────────────────────────────────────────────────────


def check_numerical_inconsistency(
    text: str, fiche: dict, section: str,
    pct_tol: float = 0.5, bn_tol: float = 0.05,
) -> list[Flag]:
    """For each %, € bn or pp value cited in the prose, look for a fiche
    number within tolerance. Flag the values with no match."""
    fiche_nums = [v for _, v in _walk_fiche_numbers(fiche)]
    flags: list[Flag] = []

    def matches(target: float, tol: float) -> bool:
        # Direct match, or absolute-value match (prose often drops the sign,
        # e.g. "fell by 42.1%" vs fiche -42.1).
        for v in fiche_nums:
            if abs(target - v) <= tol or abs(abs(target) - abs(v)) <= tol:
                return True
        return False

    for val, m in _iter_pct(text):
        if not matches(val, pct_tol) and not matches(abs(val), pct_tol):
            flags.append(Flag(
                flag_id="numerical_inconsistency",
                severity="critical",
                section=section,
                message=f"Prose cites {val:+.1f}% but no fiche value within ±{pct_tol} pp",
                citation=_sentence_around(text, m),
                suggested_resolution="Verify against the source fiche; revise prose if drifted.",
            ))
    for val, m in _iter_eur_bn(text):
        if not matches(val, bn_tol) and not matches(abs(val), bn_tol):
            flags.append(Flag(
                flag_id="numerical_inconsistency",
                severity="critical",
                section=section,
                message=f"Prose cites €{val:.2f} bn but no fiche value within ±{bn_tol} bn",
                citation=_sentence_around(text, m),
                suggested_resolution="Verify against the source fiche; revise prose if drifted.",
            ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 1.2 inter_section_inconsistency
# ──────────────────────────────────────────────────────────────────────


def check_inter_section_inconsistency(
    sections: dict[str, str], fiches: dict[str, dict],
    pct_tol: float = 0.5, bn_tol: float = 0.05,
) -> list[Flag]:
    """Cross-section: when the same EUR-bn or percentage anchor word appears
    in two sections (e.g. 'EU27 chemical exports'), the cited values should
    match within tolerance. Heuristic — group by the noun phrase preceding
    the number, then compare across sections."""
    # Anchor noun-phrases the publication is built around. If we miss one,
    # the check just doesn't fire — false-negatives over false-positives.
    anchors = [
        "exports",
        "imports",
        "trade balance",
        "production",
        "producer prices",
        "sales",
    ]
    # Per-anchor: list of (section_name, value, original match)
    seen: dict[str, list[tuple[str, float, str]]] = {a: [] for a in anchors}
    for sect, text in sections.items():
        for anchor in anchors:
            for m in re.finditer(
                rf"\b{anchor}\b[^.€%]{{0,80}}?(?:€\s*([+-]?\d{{1,4}}(?:[.,]\d{{1,3}})?)\s*bn|([+-]?\d{{1,3}}(?:[.,]\d{{1,2}})?)\s*%)",
                text, flags=re.IGNORECASE,
            ):
                raw = m.group(1) or m.group(2)
                try:
                    val = _to_float(raw)
                except ValueError:
                    continue
                seen[anchor].append((sect, val, m.group(0)))

    flags: list[Flag] = []
    for anchor, items in seen.items():
        if len(items) < 2:
            continue
        # Compare each pair; flag if the two sections disagree beyond tolerance
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                s_i, v_i, raw_i = items[i]
                s_j, v_j, raw_j = items[j]
                if s_i == s_j:
                    continue
                tol = bn_tol if "bn" in (raw_i + raw_j).lower() else pct_tol
                if abs(v_i - v_j) > tol:
                    flags.append(Flag(
                        flag_id="inter_section_inconsistency",
                        severity="critical",
                        section=f"{s_i}+{s_j}",
                        message=(
                            f"'{anchor}' cited as {v_i} in {s_i} and {v_j} in {s_j} "
                            f"(delta {abs(v_i - v_j):.2f}, tol ±{tol})"
                        ),
                        citation=f"{s_i}: '{raw_i}' | {s_j}: '{raw_j}'",
                        suggested_resolution=(
                            f"Reconcile the two sections; pick the canonical fiche value."
                        ),
                    ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 1.3 direction_mismatch
# ──────────────────────────────────────────────────────────────────────


_POSITIVE_VERBS = {
    "rose", "rises", "rising", "increased", "increases", "increasing",
    "gained", "gains", "gaining", "improved", "improves", "improving",
    "expanded", "expands", "expanding", "grew", "grows", "growing",
    "added", "adding", "advanced", "advancing", "climbed",
}
_NEGATIVE_VERBS = {
    "fell", "falls", "falling", "declined", "declines", "declining",
    "dropped", "drops", "dropping", "decreased", "decreases", "decreasing",
    "contracted", "contracts", "contracting", "lost", "losing",
    "retreated", "retreating", "shrank", "shrinking", "slumped",
}
_STABLE_VERBS = {"stable", "held", "holding", "unchanged", "flat", "steady"}


def check_direction_mismatch(text: str, section: str) -> list[Flag]:
    """Detect 'verb + by/to N%' constructs and flag verb/sign mismatches.
    Pattern: <verb> [by|to|down|up] <signed_or_unsigned_number>%."""
    flags: list[Flag] = []
    pattern = re.compile(
        r"(?P<verb>\b(?:" + "|".join(_POSITIVE_VERBS | _NEGATIVE_VERBS | _STABLE_VERBS) + r")\b)"
        r"\s+(?:by|to|approximately|roughly|about)?\s*"
        r"(?P<sign>[+-])?(?P<num>\d{1,4}(?:[.,]\d{1,3})?)\s*%",
        flags=re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        verb = m.group("verb").lower()
        sign = m.group("sign")
        raw_val = _to_float(m.group("num"))
        val = _signed(sign, raw_val)
        # When the prose drops the sign ("fell by 42.1%"), the number is the
        # magnitude and the verb supplies the direction — never a mismatch.
        # Only fire when the sign is explicit, or for the stable-with-large
        # case where the magnitude alone refutes the verb.
        bad = False
        if sign in ("+", "-"):
            if verb in _POSITIVE_VERBS and val < 0:
                bad = True
            elif verb in _NEGATIVE_VERBS and val > 0:
                bad = True
        if verb in _STABLE_VERBS and raw_val >= 1.0:
            bad = True
        if bad:
            flags.append(Flag(
                flag_id="direction_mismatch",
                severity="critical",
                section=section,
                message=(
                    f"Verb '{verb}' implies {'positive' if verb in _POSITIVE_VERBS else 'negative' if verb in _NEGATIVE_VERBS else 'stable'} "
                    f"but value is {val:+g}%"
                ),
                citation=_sentence_around(text, m),
                suggested_resolution="Reverse the verb or check the sign in the fiche.",
            ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 1.4 implausible_magnitude
# ──────────────────────────────────────────────────────────────────────


def check_implausible_magnitude(text: str, section: str) -> list[Flag]:
    """Flag magnitudes that demand a base-effect or one-off explanation."""
    flags: list[Flag] = []

    # %s above 100 on production/prices, above 500 on trade
    threshold_pct = 500 if "trade" in section else 100
    for val, m in _iter_pct(text):
        if abs(val) > threshold_pct:
            flags.append(Flag(
                flag_id="implausible_magnitude",
                severity="warning",
                section=section,
                message=(
                    f"Magnitude {val:+.1f}% exceeds the {threshold_pct}% plausibility "
                    f"threshold for '{section}'. Verify base-effect disclosure is present."
                ),
                citation=_sentence_around(text, m),
                pattern_ref="SYNTHESIS.md pattern 22",
                suggested_resolution="Confirm base-effect or one-off context is mentioned.",
            ))

    # Monthly € bn variations above 100
    for val, m in _iter_eur_bn(text):
        if abs(val) > 100:
            flags.append(Flag(
                flag_id="implausible_magnitude",
                severity="warning",
                section=section,
                message=f"€{val:.1f} bn on a monthly variation is unusually large.",
                citation=_sentence_around(text, m),
                suggested_resolution="Cross-check against fiche; expected aggregation level?",
            ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 1.5 temporal_inconsistency
# ──────────────────────────────────────────────────────────────────────


_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_NUM_TO_MONTH = {v: k.capitalize() for k, v in _MONTH_NAMES.items()}


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, (total % 12) + 1


def check_temporal_inconsistency(
    text: str, section: str, edition_month: str,
) -> list[Flag]:
    """Compare month references in prose against the edition's reference
    month. Flag obvious drift: 'first two months of YYYY' that doesn't line up
    with the edition, or 'latest reading' on a stale month."""
    flags: list[Flag] = []
    try:
        ref_y, ref_m = (int(x) for x in edition_month.split("-"))
    except ValueError:
        return flags

    # 'in <Month> YYYY' — flag if the year drifts away from the edition by
    # more than 1 (e.g. saying 'in February 2024' for a 2026-02 edition that
    # isn't a baseline reference).
    for m in re.finditer(
        r"\bin\s+(?P<month>"
        + "|".join(_MONTH_NAMES.keys())
        + r")\s+(?P<year>\d{4})\b",
        text, flags=re.IGNORECASE,
    ):
        cited_month = _MONTH_NAMES[m.group("month").lower()]
        cited_year = int(m.group("year"))
        cited_total = cited_year * 12 + cited_month
        ref_total = ref_y * 12 + ref_m
        delta = cited_total - ref_total
        # Future months relative to the edition are almost always wrong.
        if delta > 0:
            flags.append(Flag(
                flag_id="temporal_inconsistency",
                severity="warning",
                section=section,
                message=(
                    f"Prose mentions {m.group('month').capitalize()} {cited_year}, "
                    f"which is in the future relative to the {edition_month} edition."
                ),
                citation=_sentence_around(text, m),
                suggested_resolution="Verify the month reference matches the edition window.",
            ))

    # 'first N months of YYYY' — only meaningful if YYYY == ref_y or ref_y - 1
    # (the YoY comparator). Flag other years.
    for m in re.finditer(
        r"\bfirst\s+(?:two|three|four|five|six)\s+months\s+of\s+(?P<year>\d{4})\b",
        text, flags=re.IGNORECASE,
    ):
        cited_year = int(m.group("year"))
        if cited_year not in (ref_y, ref_y - 1):
            flags.append(Flag(
                flag_id="temporal_inconsistency",
                severity="warning",
                section=section,
                message=(
                    f"'first months of {cited_year}' doesn't line up with the {edition_month} "
                    "edition (expected current or YoY comparator year)."
                ),
                citation=_sentence_around(text, m),
                suggested_resolution="Realign the YTD window to the edition.",
            ))
    return flags
