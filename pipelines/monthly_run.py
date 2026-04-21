"""
Iris monthly pipeline — main CLI entry point.

Usage:
  python pipelines/monthly_run.py --month 2026-02
  python pipelines/monthly_run.py --month 2026-02 --dry-run
  python pipelines/monthly_run.py --month 2026-02 --only fetch
  python pipelines/monthly_run.py --month 2026-02 --force

Exit codes: 0 = success, 1 = error, 2 = data incomplete
"""

import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import click

from data.fetchers import eurostat, comext
from analysis.indicators import build_fiches
from editorial_engine.draft import draft_section
from editorial_engine.summary import draft_summary
from charts.render import render_charts

logger = logging.getLogger("iris")

STEPS = ["fetch", "process", "draft", "visualize", "build", "commit"]
SECTION_ORDER = ["output", "prices", "sales", "trade_exports", "trade_imports"]


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )


def step_fetch(month: str, force: bool) -> Path:
    """Step 1: Fetch raw data from APIs."""
    cache_dir = PROJECT_ROOT / "data" / "cache" / month
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not force and (cache_dir / "production.json").exists():
        logger.info(f"Cache exists for {month}, skipping fetch (use --force to override)")
        return cache_dir

    fetchers = [
        ("production", eurostat.fetch_production),
        ("prices", eurostat.fetch_prices),
        ("turnover", eurostat.fetch_turnover),
        ("gdp", eurostat.fetch_gdp),
    ]

    for name, func in fetchers:
        try:
            func(month, cache_dir)
        except Exception as e:
            logger.error(f"Fetch {name} failed: {e}")

    # Pre-crisis baseline (run once)
    try:
        eurostat.fetch_precrisis_baseline(cache_dir)
    except Exception as e:
        logger.warning(f"Pre-crisis baseline fetch failed: {e}")

    # Comext (stub)
    try:
        comext.read_parquet(month, cache_dir)
    except Exception as e:
        logger.warning(f"Comext read failed: {e}")

    return cache_dir


def step_process(month: str, cache_dir: Path) -> list:
    """Step 2: Build indicator fiches."""
    return build_fiches(cache_dir, month)


def step_draft(month: str, fiches: list, dry_run: bool) -> tuple:
    """Step 3: Draft editorial sections + summary."""
    system_prompt_path = PROJECT_ROOT / "context-prep" / "editorial" / "system.md"
    summary_prompt_path = PROJECT_ROOT / "editorial_engine" / "summary_prompt.md"
    drafts_dir = PROJECT_ROOT / "editorial" / "drafts" / month
    sections_dir = drafts_dir / "sections"
    log_path = drafts_dir / "llm_log.jsonl"
    sections_dir.mkdir(parents=True, exist_ok=True)

    section_paths = []
    failed_sections = []

    for fiche_path in fiches:
        fiche_data = json.loads(fiche_path.read_text(encoding="utf-8"))
        section_type = fiche_data["section_type"]

        result = draft_section(fiche_path, system_prompt_path, sections_dir, log_path)
        if result:
            section_paths.append(result)
        else:
            failed_sections.append(section_type)

    # Check if output section succeeded (required)
    output_present = any("output" in str(p) for p in section_paths)
    if not output_present:
        logger.error("Output section failed — edition cannot proceed")
        return section_paths, None, "failed"

    if len(section_paths) < 2:
        logger.error(f"Only {len(section_paths)} sections produced, need ≥2")
        return section_paths, None, "failed"

    # Generate summary
    summary_path, summary_quality = draft_summary(
        section_paths, summary_prompt_path, drafts_dir, log_path, month
    )

    # Consolidate edition
    if summary_path:
        edition_path = _consolidate(summary_path, section_paths, drafts_dir, month)
    else:
        edition_path = None

    return section_paths, edition_path, summary_quality


def _consolidate(summary_path: Path, section_paths: list, drafts_dir: Path, month: str) -> Path:
    """Assemble summary + sections into edition.md."""
    summary_content = summary_path.read_text(encoding="utf-8")
    # Strip frontmatter from summary
    if summary_content.startswith("---"):
        end = summary_content.find("---", 3)
        if end != -1:
            summary_content = summary_content[end + 3:].strip()

    edition = f"---\nmonth: {month}\npublication_date: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n"
    edition += summary_content + "\n\n---\n\n"

    # Sort sections by canonical order
    sorted_paths = sorted(section_paths, key=lambda p: SECTION_ORDER.index(p.stem)
                          if p.stem in SECTION_ORDER else 99)
    for sp in sorted_paths:
        content = sp.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        edition += content + "\n\n---\n\n"

    out = drafts_dir / "edition.md"
    out.write_text(edition.rstrip("- \n") + "\n", encoding="utf-8")
    logger.info(f"Edition consolidated: {out}")
    return out


def step_visualize(month: str, fiches: list) -> list:
    """Step 4: Render charts."""
    fiches_dir = PROJECT_ROOT / "data" / "processed" / month / "fiches"
    charts_dir = PROJECT_ROOT / "site" / "public" / "charts" / month
    return render_charts(fiches_dir, charts_dir)


def step_build(month: str, edition_path: Path, charts: list):
    """Step 5: Prepare Astro MDX content."""
    if not edition_path:
        logger.warning("No edition to build")
        return

    content = edition_path.read_text(encoding="utf-8")
    # Replace chart placeholders with img tags
    content = re.sub(
        r"\{\{chart:(\w+)\}\}",
        lambda m: f'<img src="/charts/{month}/{m.group(1)}.svg" alt="{m.group(1)}" />',
        content,
    )

    mdx_dir = PROJECT_ROOT / "site" / "src" / "content" / "editions"
    mdx_dir.mkdir(parents=True, exist_ok=True)
    mdx_path = mdx_dir / f"{month}.mdx"
    mdx_path.write_text(content, encoding="utf-8")
    logger.info(f"MDX prepared: {mdx_path}")


def step_commit(month: str):
    """Step 6: Create git branch and commit."""
    from scripts.commit_edition import commit_edition
    commit_edition(month, PROJECT_ROOT)


def write_manifest(month: str, sections: list, summary_quality: str, fiches: list):
    """Write manifest.json for this edition."""
    system_prompt = (PROJECT_ROOT / "context-prep" / "editorial" / "system.md").read_text(encoding="utf-8")
    summary_prompt = (PROJECT_ROOT / "editorial_engine" / "summary_prompt.md").read_text(encoding="utf-8")

    section_names = [p.stem for p in sections] if sections else []
    all_possible = ["output", "prices", "sales", "trade_exports", "trade_imports"]
    skipped = [s for s in all_possible if s not in section_names]

    # Data periods from fiches
    data_periods = {}
    for fp in fiches:
        fiche = json.loads(fp.read_text(encoding="utf-8"))
        data_periods[fiche["section_type"]] = fiche["data"]["current"]["period"]

    manifest = {
        "month": month,
        "publication_date": datetime.now().strftime("%Y-%m-%d"),
        "pipeline_version": "0.1.0",
        "sections_produced": section_names,
        "sections_skipped": {s: "data_unavailable" for s in skipped},
        "summary_quality": summary_quality or "n/a",
        "data_periods": data_periods,
        "prompt_hashes": {
            "system_md": hashlib.sha256(system_prompt.encode()).hexdigest()[:16],
            "summary_prompt_md": hashlib.sha256(summary_prompt.encode()).hexdigest()[:16],
        },
        "llm_model_used": {
            "sections": "claude-sonnet-4-20250514",
            "summary": "claude-sonnet-4-20250514",
        },
        "built_at": datetime.now(timezone.utc).isoformat(),
    }

    out = PROJECT_ROOT / "editorial" / "drafts" / month / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(f"Manifest: {out}")


@click.command()
@click.option("--month", required=True, help="Edition month (YYYY-MM)")
@click.option("--dry-run", is_flag=True, help="Skip commit step")
@click.option("--only", "only_step", type=click.Choice(STEPS), help="Run only this step")
@click.option("--force", is_flag=True, help="Overwrite existing cache")
def main(month, dry_run, only_step, force):
    """Run the Iris monthly pipeline."""
    setup_logging()
    logger.info(f"=== Iris pipeline: {month} {'(dry-run)' if dry_run else ''} ===")

    if not re.match(r"^\d{4}-\d{2}$", month):
        logger.error(f"Invalid month format: {month}. Use YYYY-MM.")
        sys.exit(1)

    try:
        # 1. FETCH
        if not only_step or only_step == "fetch":
            logger.info("--- STEP 1: FETCH ---")
            cache_dir = step_fetch(month, force)
        else:
            cache_dir = PROJECT_ROOT / "data" / "cache" / month

        # 2. PROCESS
        if not only_step or only_step == "process":
            logger.info("--- STEP 2: PROCESS ---")
            fiches = step_process(month, cache_dir)
            if not fiches:
                logger.error("No fiches produced. Aborting.")
                sys.exit(2)
            logger.info(f"Produced {len(fiches)} fiches")
        else:
            fiches_dir = PROJECT_ROOT / "data" / "processed" / month / "fiches"
            fiches = list(fiches_dir.glob("*.json")) if fiches_dir.exists() else []

        # 3. DRAFT
        if not only_step or only_step == "draft":
            logger.info("--- STEP 3: DRAFT ---")
            sections, edition_path, summary_quality = step_draft(month, fiches, dry_run)
            if summary_quality == "failed":
                logger.error("Edition draft failed (output missing or <2 sections)")
                write_manifest(month, sections, "failed", fiches)
                sys.exit(2)
        else:
            sections = []
            edition_path = PROJECT_ROOT / "editorial" / "drafts" / month / "edition.md"
            summary_quality = "unknown"

        # 4. VISUALIZE
        if not only_step or only_step == "visualize":
            logger.info("--- STEP 4: VISUALIZE ---")
            charts = step_visualize(month, fiches)
            logger.info(f"Produced {len(charts)} charts")
        else:
            charts = []

        # 5. BUILD
        if not only_step or only_step == "build":
            logger.info("--- STEP 5: BUILD ---")
            step_build(month, edition_path, charts)

        # Manifest
        write_manifest(month, sections, summary_quality, fiches)

        # 6. COMMIT
        if not only_step or only_step == "commit":
            if dry_run:
                logger.info("--- STEP 6: COMMIT (skipped — dry-run) ---")
            else:
                logger.info("--- STEP 6: COMMIT ---")
                step_commit(month)

        logger.info(f"=== Pipeline complete: {month} ===")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
