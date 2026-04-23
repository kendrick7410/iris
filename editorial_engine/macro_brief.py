"""
Macro brief generator for Iris (Livrable 5).

Contract:
  - draft_macro_brief(fiche_path, system_prompt_path, macro_prompt_path,
                      sections_paths, output_dir, log_path) → (Path, quality)
  - Concatenates fiche JSON + drafted sections, sends to LLM with system.md
    as base and macro_brief.md as overlay
  - Validates output against 5 quality criteria:
      1. Heading present (## line)
      2. 80-120 words in the paragraph body
      3. 0 bullets (macro brief is a paragraph, not bulleted)
      4. ≥ 3 distinct numbers in the paragraph
      5. No banned connectors
  - Falls back to Opus if Sonnet fails quality checks
  - Returns (path_to_macro_md, quality) where quality is "ok" or "degraded"

This module mirrors summary.py but targets the macro brief format
(heading + paragraph, no bullets).
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
import anthropic

logger = logging.getLogger("iris.editorial.macro_brief")

SONNET = "claude-sonnet-4-20250514"
OPUS = "claude-opus-4-20250514"
TEMPERATURE = 0.3
MAX_TOKENS = 1000

BANNED_CONNECTORS = [
    "furthermore", "moreover", "additionally", "notably",
    "consequently", "thus", "hence", "indeed",
    "in conclusion", "in summary", "to summarize", "overall,",
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _log_call(log_path: Path, entry: dict):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _any_anomaly_in_fiches(fiches_dir: Path) -> bool:
    """True if any fiche in the directory carries severity ≥ warn."""
    for fp in fiches_dir.glob("*.json"):
        try:
            f = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        ar = f.get("anomaly_report") or {}
        if ar.get("severity") in ("warn", "critical"):
            return True
    return False


def _strip_heading(text: str) -> tuple:
    """Return (heading_line, body_text). Heading is the first '## ...' line."""
    lines = text.strip().split("\n")
    heading = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("## "):
            heading = line.strip()
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return heading, body


_MONTH_TOKEN = (
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)"
)


def _heading_scope_ok(heading: str) -> bool:
    # Enforces system.md §1.21: a heading with a % delta must be self-explicit
    # on period. Specifically, any "in <Month>" citation must be followed by a
    # 4-digit year OR by a compound window like "Jan-Feb 2026". A bare
    # "in February" next to a % is the forbidden pattern (reader cannot tell
    # single-month vs YTD).
    if not heading:
        return False
    if not re.search(r"\d+(?:\.\d+)?\s*%", heading):
        return True
    bare_month = re.compile(
        rf"\bin\s+{_MONTH_TOKEN}\b"
        rf"(?!\s+\d{{4}})"
        rf"(?!\s*[-–]\s*{_MONTH_TOKEN}\s+\d{{4}})",
        re.IGNORECASE,
    )
    return not bool(bare_month.search(heading))


def _quality_check(text: str, anomaly_active: bool = False) -> dict:
    """Gate the macro brief against Cefic register rules.

    `anomaly_active=True` relaxes the upper word bound to 150 so the mandatory
    base-effect caveat (§1.13 of system.md) fits within budget.
    """
    heading, body = _strip_heading(text)
    words = len(body.split())
    bullets = len(re.findall(r"^[-*] ", body, re.MULTILINE))
    numbers = len(set(re.findall(r"\d+\.?\d*%?", body)))
    banned = [c for c in BANNED_CONNECTORS if c in body.lower()]
    has_heading = bool(heading)
    em_dashes = text.count("—")  # §1.18 absolute ban
    heading_scope_ok = _heading_scope_ok(heading)  # §1.21

    word_floor = 80
    word_ceiling = 150 if anomaly_active else 120

    return {
        "heading": heading,
        "has_heading": has_heading,
        "words": words,
        "words_ok": word_floor <= words <= word_ceiling,
        "bullets": bullets,
        "bullets_ok": bullets == 0,
        "numbers": numbers,
        "numbers_ok": numbers >= 3,
        "banned_found": banned,
        "banned_ok": len(banned) == 0,
        "em_dashes": em_dashes,
        "em_dashes_ok": em_dashes == 0,
        "heading_scope_ok": heading_scope_ok,
        "anomaly_active": anomaly_active,
        "word_ceiling": word_ceiling,
        "pass": (has_heading and word_floor <= words <= word_ceiling
                 and bullets == 0 and numbers >= 3
                 and len(banned) == 0 and em_dashes == 0
                 and heading_scope_ok),
    }


def _build_user_message(fiche_path: Path, section_paths: list) -> str:
    """Concatenate fiche JSON + drafted sections into one user message."""
    fiche_text = fiche_path.read_text(encoding="utf-8")
    parts = ["MACRO BRIEF FICHE (JSON):", fiche_text, ""]
    parts.append("DRAFTED SECTIONS (context, do not re-edit):")
    for sp in sorted(section_paths, key=lambda p: p.stem):
        content = sp.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        parts.append(f"\n--- {sp.stem} ---\n{content}")
    return "\n".join(parts)


def _generate(user_msg: str, system_prompt: str, macro_prompt: str,
              model: str, log_path: Path, anomaly_active: bool = False) -> tuple:
    """Call API and return (text, quality_check)."""
    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(http_client=http_client)
    combined_system = system_prompt + "\n\n---\n\n" + macro_prompt

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=combined_system,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text
        qc = _quality_check(text, anomaly_active=anomaly_active)
        _log_call(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "section_type": "macro_brief",
            "model": model,
            "system_hash": _sha256(combined_system),
            "user_msg_hash": _sha256(user_msg),
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "quality_check": qc,
            "status": "success",
        })
        return text, qc
    except Exception as e:
        logger.error(f"Macro brief generation failed with {model}: {e}")
        _log_call(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "section_type": "macro_brief",
            "model": model,
            "status": "failed",
            "error": str(e),
        })
        return None, None
    finally:
        http_client.close()


def draft_macro_brief(
    fiche_path: Path,
    system_prompt_path: Path,
    macro_prompt_path: Path,
    section_paths: list,
    output_dir: Path,
    log_path: Path,
    month: str,
) -> tuple:
    """Generate the macro brief (heading + 80-120 word paragraph).

    Returns (path_to_macro_md, quality). Quality is "ok", "degraded", or "failed".
    """
    if not fiche_path.exists():
        logger.error(f"Macro brief fiche not found: {fiche_path}")
        return None, "failed"

    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    macro_prompt = macro_prompt_path.read_text(encoding="utf-8")
    user_msg = _build_user_message(fiche_path, section_paths)
    anomaly_active = _any_anomaly_in_fiches(fiche_path.parent)

    logger.info(f"Generating macro brief with Sonnet (anomaly_active={anomaly_active})...")
    sonnet_text, sonnet_qc = _generate(user_msg, system_prompt, macro_prompt, SONNET,
                                        log_path, anomaly_active=anomaly_active)

    if sonnet_text and sonnet_qc and sonnet_qc["pass"]:
        logger.info(f"Macro brief quality OK: {sonnet_qc['words']} words")
        return _save(sonnet_text, output_dir, month, SONNET, "ok"), "ok"

    if sonnet_text and sonnet_qc:
        logger.warning(f"Sonnet macro brief failed quality: {sonnet_qc}")

    logger.info("Falling back to Opus for macro brief...")
    opus_text, opus_qc = _generate(user_msg, system_prompt, macro_prompt, OPUS,
                                    log_path, anomaly_active=anomaly_active)

    if opus_text and opus_qc and opus_qc["pass"]:
        logger.info(f"Opus macro brief quality OK: {opus_qc['words']} words")
        return _save(opus_text, output_dir, month, OPUS, "ok"), "ok"

    if opus_text and sonnet_text:
        opus_viol = sum(1 for k in ["has_heading", "words_ok", "bullets_ok",
                                     "numbers_ok", "banned_ok", "em_dashes_ok",
                                     "heading_scope_ok"] if not opus_qc[k])
        sonnet_viol = sum(1 for k in ["has_heading", "words_ok", "bullets_ok",
                                       "numbers_ok", "banned_ok", "em_dashes_ok"] if not sonnet_qc[k])
        best_text = opus_text if opus_viol <= sonnet_viol else sonnet_text
        best_model = OPUS if opus_viol <= sonnet_viol else SONNET
        logger.warning(f"Both models failed quality. Using {best_model} ({min(opus_viol, sonnet_viol)} violations).")
        return _save(best_text, output_dir, month, best_model, "degraded"), "degraded"

    if sonnet_text:
        return _save(sonnet_text, output_dir, month, SONNET, "degraded"), "degraded"

    return None, "failed"


def _save(text: str, output_dir: Path, month: str, model: str, quality: str) -> Path:
    frontmatter = (
        f"---\n"
        f"type: macro_brief\n"
        f"period: {month}\n"
        f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"model: {model}\n"
        f"quality: {quality}\n"
        f"---\n\n"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "macro.md"
    out.write_text(frontmatter + text, encoding="utf-8")
    logger.info(f"Macro brief saved to {out}")
    return out
