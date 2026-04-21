"""
Summary generator for Iris.

Contract:
  - draft_summary(section_paths, summary_prompt_path, output_dir, log_path) → Path
  - Concatenates drafted sections, sends to LLM with summary_prompt.md
  - Validates output against 4 quality criteria (word count, bullet count, banned words, number count)
  - Falls back to Opus if Sonnet fails quality checks
  - Returns path to summary.md

Quality criteria (from ARCHITECTURE.md Patch 2):
  - 80-250 words
  - Exactly 4 bullets
  - No banned connectors from system.md §4
  - At least 3 distinct numbers
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import anthropic

logger = logging.getLogger("iris.editorial.summary")

SONNET = "claude-sonnet-4-20250514"
OPUS = "claude-opus-4-20250514"
TEMPERATURE = 0.3
MAX_TOKENS = 1000

BANNED_CONNECTORS = [
    "furthermore", "moreover", "additionally", "notably",
    "consequently", "thus", "hence", "indeed",
    "in conclusion", "in summary", "to summarize",
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _log_call(log_path: Path, entry: dict):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _count_bullets(text: str) -> int:
    return len(re.findall(r"^- ", text, re.MULTILINE))


def _count_words(text: str) -> int:
    return len(text.split())


def _count_numbers(text: str) -> int:
    return len(set(re.findall(r"\d+\.?\d*%?", text)))


def _has_banned_connectors(text: str) -> list:
    text_lower = text.lower()
    return [c for c in BANNED_CONNECTORS if c in text_lower]


def _quality_check(text: str) -> dict:
    """Check summary against quality criteria. Returns dict with pass/fail."""
    words = _count_words(text)
    bullets = _count_bullets(text)
    numbers = _count_numbers(text)
    banned = _has_banned_connectors(text)

    return {
        "words": words,
        "words_ok": 80 <= words <= 250,
        "bullets": bullets,
        "bullets_ok": bullets == 4,
        "numbers": numbers,
        "numbers_ok": numbers >= 3,
        "banned_found": banned,
        "banned_ok": len(banned) == 0,
        "pass": (80 <= words <= 250) and bullets == 4 and numbers >= 3 and len(banned) == 0,
    }


def _generate_summary(sections_text: str, summary_prompt: str, model: str,
                       log_path: Path) -> tuple:
    """Call API and return (text, quality_check)."""
    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(http_client=http_client)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=summary_prompt,
            messages=[{"role": "user", "content": sections_text}],
        )
        text = resp.content[0].text
        qc = _quality_check(text)

        _log_call(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "section_type": "summary",
            "model": model,
            "system_hash": _sha256(summary_prompt),
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "quality_check": qc,
            "status": "success",
        })

        return text, qc

    except Exception as e:
        logger.error(f"Summary generation failed with {model}: {e}")
        _log_call(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "section_type": "summary",
            "model": model,
            "status": "failed",
            "error": str(e),
        })
        return None, None

    finally:
        http_client.close()


def draft_summary(
    section_paths: list,
    summary_prompt_path: Path,
    output_dir: Path,
    log_path: Path,
    month: str,
) -> tuple:
    """Generate executive summary from drafted sections.

    Returns (path_to_summary, quality_status) where quality_status is "ok" or "degraded".
    Returns (None, "failed") if generation fails entirely.
    """
    if len(section_paths) < 2:
        logger.error(f"Need ≥2 sections for summary, got {len(section_paths)}")
        return None, "failed"

    summary_prompt = summary_prompt_path.read_text(encoding="utf-8")

    # Concatenate sections (strip frontmatter)
    sections_text = ""
    for sp in sorted(section_paths, key=lambda p: p.stem):
        content = sp.read_text(encoding="utf-8")
        # Remove YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        sections_text += f"\n\n{content}"

    # Try Sonnet first
    logger.info("Generating summary with Sonnet...")
    sonnet_text, sonnet_qc = _generate_summary(sections_text, summary_prompt, SONNET, log_path)

    if sonnet_text and sonnet_qc and sonnet_qc["pass"]:
        logger.info(f"Summary quality OK: {sonnet_qc['words']} words, {sonnet_qc['bullets']} bullets")
        return _save_summary(sonnet_text, output_dir, month, SONNET, "ok"), "ok"

    # Fallback to Opus
    if sonnet_text and sonnet_qc:
        logger.warning(f"Sonnet summary failed quality: {sonnet_qc}")

    logger.info("Falling back to Opus for summary...")
    opus_text, opus_qc = _generate_summary(sections_text, summary_prompt, OPUS, log_path)

    if opus_text and opus_qc and opus_qc["pass"]:
        logger.info(f"Opus summary quality OK: {opus_qc['words']} words")
        return _save_summary(opus_text, output_dir, month, OPUS, "ok"), "ok"

    # Both failed quality — pick best
    if opus_text and sonnet_text:
        opus_violations = sum(1 for k in ["words_ok", "bullets_ok", "numbers_ok", "banned_ok"]
                             if not opus_qc[k])
        sonnet_violations = sum(1 for k in ["words_ok", "bullets_ok", "numbers_ok", "banned_ok"]
                               if not sonnet_qc[k])
        best_text = opus_text if opus_violations <= sonnet_violations else sonnet_text
        best_model = OPUS if opus_violations <= sonnet_violations else SONNET
        logger.warning(f"Both models failed quality. Using {best_model} (fewer violations).")
        return _save_summary(best_text, output_dir, month, best_model, "degraded"), "degraded"

    if sonnet_text:
        return _save_summary(sonnet_text, output_dir, month, SONNET, "degraded"), "degraded"

    return None, "failed"


def _save_summary(text: str, output_dir: Path, month: str, model: str, quality: str) -> Path:
    frontmatter = (
        f"---\n"
        f"type: summary\n"
        f"period: {month}\n"
        f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"model: {model}\n"
        f"quality: {quality}\n"
        f"---\n\n"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "summary.md"
    out.write_text(frontmatter + text, encoding="utf-8")
    logger.info(f"Summary saved to {out}")
    return out
