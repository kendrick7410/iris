"""Regenerate 2026-02 v3 edition (macro brief + trade_exports + trade_imports).

Keeps output, prices, sales sections from the canonical v2 drafts; re-drafts
only the three trade-related modules under variant=v3.

    python scripts/regen_v3.py 2026-02

After running, review editorial/drafts/2026-02-v3/edition.md, then (manually)
copy over site/src/content/editions/2026-02.mdx to preview on the site.
"""
import logging
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from editorial_engine.draft import draft_section
from pipelines.monthly_run import (
    step_macro_brief,
    _consolidate,
    step_build,
    _drafts_dir,
)


STABLE_SECTIONS = ["output", "prices", "sales"]
REDRAFT_SECTIONS = ["trade_exports", "trade_imports"]


def main(month: str) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )
    log = logging.getLogger("iris.regen_v3")

    canonical_dir = _drafts_dir(month, None)
    v3_dir = _drafts_dir(month, "v3")
    v3_sections = v3_dir / "sections"
    v3_sections.mkdir(parents=True, exist_ok=True)
    log_path = v3_dir / "llm_log.jsonl"

    # Copy stable sections from v2 to v3
    for name in STABLE_SECTIONS:
        src = canonical_dir / "sections" / f"{name}.md"
        dst = v3_sections / f"{name}.md"
        if src.exists():
            shutil.copy(src, dst)
            log.info(f"copied stable: {src} -> {dst}")
        else:
            log.warning(f"stable section missing in canonical: {src}")

    # Re-draft trade sections against the new system.md
    system_prompt_path = PROJECT_ROOT / "context-prep" / "editorial" / "system.md"
    fiches_dir = PROJECT_ROOT / "data" / "processed" / month / "fiches"
    section_paths = []
    for name in REDRAFT_SECTIONS:
        fp = fiches_dir / f"{name}.json"
        if not fp.exists():
            log.error(f"fiche missing: {fp}")
            continue
        log.info(f"re-drafting {name}")
        out = draft_section(fp, system_prompt_path, v3_sections, log_path)
        if out:
            section_paths.append(out)
            log.info(f"  wrote {out}")

    # Compose full section list (stable + redrafted)
    all_sections = sorted(v3_sections.glob("*.md"))
    log.info(f"sections available for macro brief: {[p.stem for p in all_sections]}")

    # Regenerate macro brief
    all_fiches = sorted(fiches_dir.glob("*.json"))
    macro_path, quality = step_macro_brief(month, all_fiches, all_sections, variant="v3")
    if not macro_path:
        log.error(f"macro brief failed: quality={quality}")
        return 1
    log.info(f"macro brief saved (quality={quality}): {macro_path}")

    # Consolidate edition.md
    edition_path = _consolidate(macro_path, all_sections, v3_dir, month)
    log.info(f"edition consolidated: {edition_path}")

    # Do NOT run step_build for the variant (would overwrite the canonical MDX).
    # The site preview MDX is updated manually after review.
    log.info("Variant=v3 regen complete. Review %s and promote when ready.", edition_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/regen_v3.py YYYY-MM", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1]))
