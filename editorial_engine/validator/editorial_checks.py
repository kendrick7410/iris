"""Editorial (Niveau 2) validator checks — Cefic-style judgement.

Two layers:

  1. **Deterministic checks** (regex / word lists, fast, free, no API).
     Banned connectors, non-Cefic jargon, missing long-term anchor,
     missing international context, emotional tone.
  2. **LLM judge** (`check_patterns_via_llm`) for the more nuanced
     pattern-missing check (2.1), invoked once per section. Gated by an
     `ANTHROPIC_API_KEY` so tests can run unit-only without network.

Every check returns `list[Flag]`. The validator entry point composes them.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from .flag import Flag

logger = logging.getLogger("iris.editorial.validator")

# ──────────────────────────────────────────────────────────────────────
# 2.2 banned_connector  — system.md §4.3
# ──────────────────────────────────────────────────────────────────────

BANNED_CONNECTORS = {
    "furthermore", "moreover", "additionally", "in conclusion",
    "notably", "consequently", "thus", "hence", "indeed",
}


def check_banned_connectors(text: str, section: str) -> list[Flag]:
    """Hit on any whole-word occurrence of a banned connector. Severity
    'warning' — these slip past LLMs but are easy to fix manually."""
    flags: list[Flag] = []
    for term in BANNED_CONNECTORS:
        # Word-boundary match, case-insensitive
        for m in re.finditer(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE):
            flags.append(Flag(
                flag_id="banned_connector",
                severity="warning",
                section=section,
                message=f"'{term}' is on the Cefic banned-connectors list (system.md §4.3).",
                citation=_excerpt(text, m),
                pattern_ref="system.md §4.3",
                suggested_resolution=f"Remove '{term}' or rewrite the sentence without a connector.",
            ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 2.3 non_cefic_jargon  — patch §2.3
# ──────────────────────────────────────────────────────────────────────

# Buckets carry distinct messages so the suggestion stays useful.
_JARGON = {
    "business": [
        "synergistic", "leverage as a verb", "going forward",
        "low-hanging fruit", "deep-dive", "circle back", "best-in-class",
    ],
    "mainstream_economist": [
        "uncertainty", "headwinds", "challenging environment", "soft demand",
    ],
    "vague_intensifier": [
        "significant", "substantial", "considerable",
    ],
}
# Flatten to a single regex per bucket. The vague-intensifier bucket also
# matches the -ly adverb form ("significantly", "substantially").
def _bucket_pattern(terms: list[str], adverb_form: bool = False) -> re.Pattern:
    suffix = r"(?:ly)?" if adverb_form else ""
    safe = [re.escape(t) for t in terms if t != "leverage as a verb"]
    return re.compile(
        r"\b(?:" + "|".join(safe) + r")" + suffix + r"\b",
        flags=re.IGNORECASE,
    )

_JARGON_RX = {
    "business":              _bucket_pattern(_JARGON["business"]),
    "mainstream_economist":  _bucket_pattern(_JARGON["mainstream_economist"]),
    "vague_intensifier":     _bucket_pattern(_JARGON["vague_intensifier"], adverb_form=True),
}
# 'leverage' is flagged in any verb form, plus bare 'leverage'/'leverages'
# (noun usage is rare in Cefic prose; over-flagging is acceptable here).
_LEVERAGE_RX = re.compile(
    r"\b(to\s+leverage|leverages?|leveraging|leveraged)\b", flags=re.IGNORECASE,
)


def check_non_cefic_jargon(text: str, section: str) -> list[Flag]:
    flags: list[Flag] = []
    for bucket, rx in _JARGON_RX.items():
        for m in rx.finditer(text):
            flags.append(Flag(
                flag_id="non_cefic_jargon",
                severity="warning",
                section=section,
                message=f"'{m.group(0)}' reads as {bucket.replace('_', ' ')} jargon, foreign to the Cefic register.",
                citation=_excerpt(text, m),
                suggested_resolution=(
                    "Replace with a figure-anchored statement"
                    if bucket == "vague_intensifier"
                    else "Rewrite in plain analytical prose."
                ),
            ))
    for m in _LEVERAGE_RX.finditer(text):
        flags.append(Flag(
            flag_id="non_cefic_jargon",
            severity="warning",
            section=section,
            message="'leverage' as a verb is on the Cefic banned-business-jargon list.",
            citation=_excerpt(text, m),
            suggested_resolution="Use 'use', 'draw on', or rewrite without the metaphor.",
        ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 2.4 missing_long_term_perspective
# ──────────────────────────────────────────────────────────────────────

_LONG_TERM_TOKENS = re.compile(
    r"\b(?:"
    r"2014\D{0,3}201[5-9]|2014[-–]?2019|"     # 2014-2019 baseline
    r"pre[- ]?crisis|"                         # pre-crisis
    r"12[- ]?month\s+rolling|rolling\s+(?:12|twelve)|"   # 12-month rolling
    r"(?:five|5)[- ]?year\s+(?:window|baseline|average)|"
    r"baseline"                                # any baseline mention
    r")\b",
    flags=re.IGNORECASE,
)


def check_missing_long_term_perspective(
    text: str, section: str, edition_month: str | None = None,
) -> list[Flag]:
    """Cefic anchors monthly readings in multi-year context. If no
    long-term marker is present and the section is non-trivial, flag."""
    if len(text.split()) < 60:
        return []  # too short to expect an anchor
    if _LONG_TERM_TOKENS.search(text):
        return []
    # Allow an explicit older year (more than ref_year - 2) as an anchor too
    if edition_month:
        try:
            ref_y = int(edition_month.split("-")[0])
            for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", text):
                if int(m.group(1)) <= ref_y - 2:
                    return []
        except ValueError:
            pass
    return [Flag(
        flag_id="missing_long_term_perspective",
        severity="warning",
        section=section,
        message=(
            "Section discusses recent variation only; no anchor to pre-crisis "
            "(2014-2019), 12-month rolling, or a multi-year baseline."
        ),
        pattern_ref="SYNTHESIS.md pattern 6",
        suggested_resolution="Add a comparison to the historical baseline or rolling average.",
    )]


# ──────────────────────────────────────────────────────────────────────
# 2.5 missing_international_context
# ──────────────────────────────────────────────────────────────────────

_INTL_TOKENS = re.compile(
    r"\b(?:"
    r"US|U\.S\.|United\s+States|American|"
    r"China|Chinese|"
    r"UK|United\s+Kingdom|British|"
    r"global|worldwide|international|extra[- ]?EU"
    r")\b",
)
# Sections where international framing is expected (per patch §2.5)
_INTL_REQUIRED_SECTIONS = {
    "macro_brief", "trade_exports", "trade_imports", "overview",
}


def check_missing_international_context(text: str, section: str) -> list[Flag]:
    if section not in _INTL_REQUIRED_SECTIONS:
        return []
    if _INTL_TOKENS.search(text):
        return []
    return [Flag(
        flag_id="missing_international_context",
        severity="warning",
        section=section,
        message=(
            "Macro/trade section without mention of US, China, UK, or global "
            "context. Cefic systematically reads EU27 against the rest of the world."
        ),
        pattern_ref="SYNTHESIS.md pattern 23",
        suggested_resolution="Add at least one comparator or partner reference.",
    )]


# ──────────────────────────────────────────────────────────────────────
# 2.6 emotional_tone
# ──────────────────────────────────────────────────────────────────────

_EMOTIONAL = re.compile(
    r"\b(?:"
    r"good\s+news|promising|encouraging|"            # cheerleading
    r"disaster|disastrous|catastroph(?:e|ic)|"       # catastrophism
    r"collapse|collapsing|crisis|crises|"
    r"alarming|worrying|troubling|"
    r"booming|surging\s+ahead|skyrocket(?:ed|ing)?"
    r")\b",
    flags=re.IGNORECASE,
)
# 'crisis' inside 'pre-crisis [year]' is a Cefic reference baseline, not
# catastrophism. Same for 'post-crisis'.
_CRISIS_NEUTRAL_CONTEXT = re.compile(
    r"\b(?:pre|post)[- ]crisis\b", flags=re.IGNORECASE,
)


def check_emotional_tone(text: str, section: str) -> list[Flag]:
    flags: list[Flag] = []
    # Carve out the neutral 'pre-crisis' / 'post-crisis' spans so 'crisis'
    # inside them doesn't fire.
    neutral_spans = [m.span() for m in _CRISIS_NEUTRAL_CONTEXT.finditer(text)]

    def _inside_neutral(start: int, end: int) -> bool:
        return any(s <= start and end <= e for s, e in neutral_spans)

    for m in _EMOTIONAL.finditer(text):
        if _inside_neutral(m.start(), m.end()):
            continue
        flags.append(Flag(
            flag_id="emotional_tone",
            severity="warning",
            section=section,
            message=(
                f"'{m.group(0)}' carries emotional charge; Cefic prose is neutral "
                "and figure-anchored."
            ),
            citation=_excerpt(text, m),
            suggested_resolution="Replace with a neutral, data-anchored phrasing.",
        ))
    return flags


# ──────────────────────────────────────────────────────────────────────
# 2.1 pattern_missing  — LLM judge
# ──────────────────────────────────────────────────────────────────────

# Required SYNTHESIS.md patterns per section type (patch §2.1)
REQUIRED_PATTERNS_BY_SECTION = {
    "macro_brief":   [1, 2, 4, 10],
    "output":        [1, 2, 4, 10],   # macro brief sub-section
    "prices":        [1, 2, 4, 10],
    "sales":         [1, 2, 4, 10],
    "trade_exports": [14, 17, 22, 23],
    "trade_imports": [14, 17, 22, 23],
    "drilldown":     [5, 19, 23],
    "drill_down":    [5, 19, 23],
}
# Patterns required across every section
PATTERNS_ALL = [7, 13]

# Compact descriptions sent to the LLM so it doesn't need the full SYNTHESIS.
PATTERN_LIBRARY = {
    1:  "the figure first, interpretation after — every analytical claim anchored to a sourced number",
    2:  "dual-period comparison is systematic — every figure carries at least one benchmark (YoY, vs pre-crisis, vs peer)",
    4:  "heading-as-finding, not heading-as-topic — the title states the conclusion with figures",
    5:  "CN 8-digit truncation — codes are written in full but with a short label",
    7:  "no banned connectors (furthermore, moreover, additionally, in conclusion, notably, consequently, thus, hence, indeed)",
    10: "third person institutional voice (the sector / the EU27 chemical industry); no 'we' / 'our'",
    13: "no concluding paragraph; section ends on the last data point",
    14: "trade-formula opening: 'From [window], [indicator] [verb] by [%]... amounting to €X bn, [direction] by €Y bn compared to [year]'",
    17: "ranking sentence with 'With €X bn, [entity] is the primary/largest...'",
    19: "Pareto-style concentration diagnosis: 'X partners account for Y% of the variation'",
    22: "base-effect mise en garde — when magnitudes are unusual, the section qualifies the interpretation but keeps the headline",
    23: "key-partner symmetry — US, CN, GB treated together when relevant",
}


def _load_validator_system_prompt() -> str:
    p = Path(__file__).parent / "prompts" / "validator_system.md"
    return p.read_text(encoding="utf-8")


def check_patterns_via_llm(
    text: str,
    section: str,
    *,
    api_key: str | None = None,
    log_path: Path | None = None,
    timeout: float = 30.0,
) -> list[Flag]:
    """Ask Sonnet to evaluate which of the section's required Cefic patterns
    are missing or weak. Returns a list of `pattern_missing_<id>` flags.

    Skips silently (returns []) when no API key is available, so the rest
    of the pipeline keeps running offline / in CI without secrets.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.info("ANTHROPIC_API_KEY missing — skipping LLM pattern check for %s", section)
        return []

    required = REQUIRED_PATTERNS_BY_SECTION.get(section, []) + PATTERNS_ALL
    if not required:
        return []

    pattern_lines = "\n".join(
        f"  - Pattern {n}: {PATTERN_LIBRARY.get(n, 'see SYNTHESIS.md')}"
        for n in required
    )
    user_msg = (
        f"Section type: {section}\n"
        f"Required Cefic patterns for this section type:\n{pattern_lines}\n\n"
        "Read the section below and judge which required patterns are MISSING "
        "or only WEAKLY applied. For each missing pattern, output one flag "
        "object with: pattern_id (int), severity ('warning' or 'info'), message "
        "(one sentence, why missing), citation (short excerpt or empty if global).\n\n"
        "Return JSON only, in this exact shape:\n"
        '{"flags": [{"pattern_id": int, "severity": "warning"|"info", '
        '"message": str, "citation": str}, ...]}\n\n'
        f"=== SECTION TEXT ===\n{text}\n=== END ===\n"
    )

    # Lazy-import anthropic so unit tests don't pull it in.
    try:
        import anthropic  # noqa: WPS433 (intentional lazy import)
        import httpx
    except ImportError as exc:
        logger.warning("anthropic SDK not available — skipping LLM pattern check: %s", exc)
        return []

    client = anthropic.Anthropic(
        api_key=key,
        http_client=httpx.Client(verify=False, timeout=timeout),
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            temperature=0.0,
            system=_load_validator_system_prompt(),
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as exc:  # network / auth / quota — fail soft
        logger.warning("Validator LLM call failed for %s: %s", section, exc)
        return []

    # Optional log line, mirrors draft.py convention
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "kind": "validator.pattern_check",
                "section": section,
                "model": resp.model,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }) + "\n")

    raw = resp.content[0].text if resp.content else ""
    return _parse_llm_flags(raw, section)


def _parse_llm_flags(raw: str, section: str) -> list[Flag]:
    """Tolerant JSON extraction — model sometimes wraps in code fences."""
    body = raw.strip()
    if body.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body, flags=re.MULTILINE)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        # Last-ditch: find the first {...} blob
        m = re.search(r"\{.*\}", body, re.DOTALL)
        if not m:
            return []
        try:
            payload = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []

    out: list[Flag] = []
    for entry in payload.get("flags", []):
        pid = entry.get("pattern_id")
        if pid is None:
            continue
        out.append(Flag(
            flag_id=f"pattern_missing_{pid}",
            severity=entry.get("severity", "warning"),
            section=section,
            message=entry.get("message", "Pattern missing or weak."),
            citation=entry.get("citation", "") or "",
            pattern_ref=f"SYNTHESIS.md pattern {pid}",
            suggested_resolution=PATTERN_LIBRARY.get(pid, "Apply the Cefic pattern; see SYNTHESIS.md"),
        ))
    return out


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _excerpt(text: str, m: re.Match, window: int = 80) -> str:
    start = max(0, m.start() - window // 2)
    end = min(len(text), m.end() + window // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
