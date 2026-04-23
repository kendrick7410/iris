"""One-shot: regenerate only the macro brief for a given month.

Re-runs step_macro_brief → _consolidate → step_build, leaving the 5 section
drafts untouched. Used to apply prompt/system.md changes without touching
validated section content.

    python scripts/regen_macro_brief.py 2026-02
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from pipelines.monthly_run import (
    step_macro_brief,
    _consolidate,
    step_build,
    _drafts_dir,
)


def main(month: str) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )
    log = logging.getLogger("iris.regen_macro_brief")

    drafts_dir = _drafts_dir(month, None)
    sections_dir = drafts_dir / "sections"
    fiches_dir = PROJECT_ROOT / "data" / "processed" / month / "fiches"
    charts_dir = PROJECT_ROOT / "site" / "public" / "charts" / month

    fiches = sorted(fiches_dir.glob("*.json"))
    section_paths = sorted(sections_dir.glob("*.md"))
    charts = sorted(charts_dir.glob("*.svg")) if charts_dir.exists() else []

    if not section_paths:
        log.error(f"No sections found at {sections_dir} — cannot regenerate macro brief.")
        return 2

    log.info(f"Regenerating macro brief for {month}")
    log.info(f"  sections:  {len(section_paths)} ({', '.join(p.stem for p in section_paths)})")
    log.info(f"  fiches:    {len(fiches)}")
    log.info(f"  charts:    {len(charts)}")

    macro_path, quality = step_macro_brief(month, fiches, section_paths, variant=None)
    if not macro_path:
        log.error(f"Macro brief generation failed (quality={quality}).")
        return 1
    log.info(f"Macro brief saved (quality={quality}): {macro_path}")

    edition_path = _consolidate(macro_path, section_paths, drafts_dir, month)
    log.info(f"Edition consolidated: {edition_path}")

    step_build(month, edition_path, charts)
    log.info("Site MDX rebuilt.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/regen_macro_brief.py YYYY-MM", file=sys.stderr)
        sys.exit(64)
    sys.exit(main(sys.argv[1]))
