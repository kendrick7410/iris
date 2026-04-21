"""
Editorial section drafter for Iris.

Contract:
  - draft_section(fiche_path, system_prompt_path, output_dir, log_path) → Path to section .md
  - Calls Anthropic API (Sonnet, temp=0.3) with system.md as system, fiche JSON as user
  - Logs full prompt+response to llm_log.jsonl
  - Returns markdown with YAML frontmatter (section_type, order, charts, period, model)
  - Requires httpx.Client(verify=False) on Cefic network (SSL proxy)

Retry: 3 attempts, exponential backoff (2s, 8s, 32s). Retry on timeout/429/5xx.
No retry on 400/401/403.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import anthropic

logger = logging.getLogger("iris.editorial.draft")

MODEL = "claude-sonnet-4-20250514"
TEMPERATURE = 0.3
MAX_TOKENS = 2000
MAX_RETRIES = 3
BACKOFF_BASE = 2  # 2s, 8s, 32s

SECTION_ORDER = {
    "output": 1, "prices": 2, "sales": 3,
    "trade_exports": 4, "trade_imports": 5,
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _log_call(log_path: Path, entry: dict):
    """Append one JSON line to the LLM log."""
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def draft_section(
    fiche_path: Path,
    system_prompt_path: Path,
    output_dir: Path,
    log_path: Path,
) -> Path:
    """Generate one editorial section from a fiche via the Anthropic API.

    Returns path to the generated section .md file, or None if all retries fail.
    """
    fiche_text = fiche_path.read_text(encoding="utf-8")
    fiche_data = json.loads(fiche_text)
    system_prompt = system_prompt_path.read_text(encoding="utf-8")

    section_type = fiche_data["section_type"]
    period = fiche_data["period"]["month"]
    charts = fiche_data.get("charts", [])

    logger.info(f"Drafting section '{section_type}' for {period}...")

    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(http_client=http_client)

    response_text = None
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": fiche_text}],
            )
            response_text = resp.content[0].text

            # Log successful call
            _log_call(log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "section_type": section_type,
                "period": period,
                "model": MODEL,
                "temperature": TEMPERATURE,
                "system_hash": _sha256(system_prompt),
                "user_msg_hash": _sha256(fiche_text),
                "user_msg_length": len(fiche_text),
                "response_length": len(response_text),
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "attempt": attempt + 1,
                "status": "success",
            })
            break

        except (anthropic.RateLimitError, anthropic.InternalServerError,
                anthropic.APITimeoutError, httpx.ConnectError) as e:
            last_error = str(e)
            wait = BACKOFF_BASE ** (attempt + 1)
            logger.warning(
                f"API attempt {attempt+1}/{MAX_RETRIES} failed for {section_type}: {e}. "
                f"Retry in {wait}s."
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

        except (anthropic.BadRequestError, anthropic.AuthenticationError,
                anthropic.PermissionDeniedError) as e:
            # Non-retryable errors
            last_error = str(e)
            logger.error(f"Non-retryable API error for {section_type}: {e}")
            _log_call(log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "section_type": section_type,
                "period": period,
                "model": MODEL,
                "status": "failed_no_retry",
                "error": last_error,
            })
            break

    http_client.close()

    if response_text is None:
        logger.error(f"All retries exhausted for {section_type}. Last error: {last_error}")
        _log_call(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "section_type": section_type,
            "period": period,
            "model": MODEL,
            "status": "failed_all_retries",
            "error": last_error,
        })
        return None

    # Build section file with YAML frontmatter
    frontmatter = (
        f"---\n"
        f"section_type: {section_type}\n"
        f"order: {SECTION_ORDER.get(section_type, 99)}\n"
        f"charts:\n"
    )
    for c in charts:
        frontmatter += f"  - {c}\n"
    frontmatter += (
        f"period: {period}\n"
        f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"model: {MODEL}\n"
        f"---\n\n"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{section_type}.md"
    out_path.write_text(frontmatter + response_text, encoding="utf-8")

    logger.info(f"Section '{section_type}' saved to {out_path} ({len(response_text)} chars)")
    return out_path
