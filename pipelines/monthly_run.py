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
from analysis.indicators import build_fiches, build_macro_brief_fiche
from editorial_engine.draft import draft_section
from editorial_engine.summary import draft_summary
from editorial_engine.macro_brief import draft_macro_brief
from charts.render import render_charts

logger = logging.getLogger("iris")

STEPS = ["fetch", "process", "draft", "visualize", "build", "commit"]
SECTION_ORDER = ["output", "prices", "sales", "trade_exports", "trade_imports"]
PIPELINE_VERSION = "0.2.0"   # L5 — macro brief enabled; v1 editions stay at 0.1.0


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


def _drafts_dir(month: str, variant: str | None = None) -> Path:
    """Drafts directory, optionally suffixed by a variant tag for regen tests."""
    name = f"{month}-{variant}" if variant else month
    return PROJECT_ROOT / "editorial" / "drafts" / name


FRAGMENTED_EUROPE_RE = re.compile(
    r"[Tt]hese\s+chemical\s+\w+\s+trends\s+by\s+country\s+show\s+a\s+fragmented\s+Europe\.?",
)


def _enforce_fragmented_europe_cap(section_paths: list) -> dict:
    """Enforce §5.3 condition 4: the phrase is used at most once per edition.

    Iterates section files in draft order; keeps the first occurrence and
    strips subsequent ones (and the sentence that contains them). Returns a
    report dict with counts per section so the post-run report can show what
    the LLM produced before enforcement.
    """
    per_section = {}
    seen = False
    for path in sorted(section_paths, key=lambda p: p.name):
        text = path.read_text(encoding="utf-8")
        matches = FRAGMENTED_EUROPE_RE.findall(text)
        per_section[path.stem] = {"occurrences_before": len(matches),
                                   "occurrences_after": 0, "stripped": False}
        if not matches:
            continue
        if not seen:
            # First edition occurrence — keep it, count it.
            seen = True
            per_section[path.stem]["occurrences_after"] = 1
            continue
        # Strip ALL occurrences in this file (it's a repeat in the edition).
        new_text = FRAGMENTED_EUROPE_RE.sub("", text)
        # Clean up dangling spaces / empty lines created by the strip.
        new_text = re.sub(r"[ \t]+\n", "\n", new_text)
        new_text = re.sub(r"\n{3,}", "\n\n", new_text)
        path.write_text(new_text, encoding="utf-8")
        per_section[path.stem]["stripped"] = True
        logger.warning(
            f"§5.3 enforcement: stripped {len(matches)}× 'fragmented Europe' "
            f"closing from {path.name} (already used earlier in this edition)."
        )
    return {"per_section": per_section, "edition_uses_phrase": seen}


def step_draft(month: str, fiches: list, dry_run: bool, variant: str | None = None) -> tuple:
    """Step 3: Draft editorial sections. Summary/macro-brief are step 3.5."""
    system_prompt_path = PROJECT_ROOT / "context-prep" / "editorial" / "system.md"
    drafts_dir = _drafts_dir(month, variant)
    sections_dir = drafts_dir / "sections"
    log_path = drafts_dir / "llm_log.jsonl"
    sections_dir.mkdir(parents=True, exist_ok=True)

    section_paths = []
    # Skip macro_brief fiche here — it is produced at step 3.5 from the drafted sections
    section_fiches = [f for f in fiches
                      if json.loads(f.read_text(encoding="utf-8"))["section_type"] != "macro_brief"]

    for fiche_path in section_fiches:
        result = draft_section(fiche_path, system_prompt_path, sections_dir, log_path)
        if result:
            section_paths.append(result)

    # §5.3 condition 4 — once-per-edition enforcement for "fragmented Europe".
    enforcement = _enforce_fragmented_europe_cap(section_paths)
    _log_enforcement(drafts_dir, enforcement)

    output_present = any("output" in str(p) for p in section_paths)
    if not output_present:
        logger.error("Output section failed — edition cannot proceed")
        return section_paths, None, "failed"
    if len(section_paths) < 2:
        logger.error(f"Only {len(section_paths)} sections produced, need ≥2")
        return section_paths, None, "failed"

    return section_paths, None, "ok"


def _log_enforcement(drafts_dir: Path, enforcement: dict) -> None:
    """Persist the enforcement report alongside the edition for traceability."""
    out = drafts_dir / "enforcement_report.json"
    out.write_text(json.dumps(enforcement, indent=2), encoding="utf-8")


def step_macro_brief(month: str, fiches: list, section_paths: list,
                     variant: str | None = None) -> tuple:
    """Step 3.5: Build macro_brief fiche and draft the macro brief.

    Returns (macro_md_path, quality). Falls back to summary mode if the
    macro brief overlay prompt is absent (backward compatibility for v1).
    """
    system_prompt_path = PROJECT_ROOT / "context-prep" / "editorial" / "system.md"
    macro_prompt_path = PROJECT_ROOT / "editorial" / "prompts" / "macro_brief.md"
    summary_prompt_path = PROJECT_ROOT / "editorial_engine" / "summary_prompt.md"
    drafts_dir = _drafts_dir(month, variant)
    fiches_dir = PROJECT_ROOT / "data" / "processed" / month / "fiches"
    log_path = drafts_dir / "llm_log.jsonl"

    # Backward-compat: if no macro_brief prompt file, fall back to v1 summary
    if not macro_prompt_path.exists():
        logger.info("No macro_brief prompt — falling back to summary (v1 mode)")
        return draft_summary(section_paths, summary_prompt_path, drafts_dir, log_path, month)

    # Assemble macro_brief fiche
    cache_dir = PROJECT_ROOT / "data" / "cache" / month
    macro_fiche = build_macro_brief_fiche(fiches_dir, cache_dir)

    # Draft macro brief
    macro_path, quality = draft_macro_brief(
        fiche_path=macro_fiche,
        system_prompt_path=system_prompt_path,
        macro_prompt_path=macro_prompt_path,
        section_paths=section_paths,
        output_dir=drafts_dir,
        log_path=log_path,
        month=month,
    )
    return macro_path, quality


def _consolidate(opening_path: Path, section_paths: list, drafts_dir: Path, month: str) -> Path:
    """Assemble opening (macro brief or legacy summary) + sections into edition.md."""
    opening_content = opening_path.read_text(encoding="utf-8")
    # Strip frontmatter
    if opening_content.startswith("---"):
        end = opening_content.find("---", 3)
        if end != -1:
            opening_content = opening_content[end + 3:].strip()

    edition = f"---\nmonth: {month}\npublication_date: {datetime.now().strftime('%Y-%m-%d')}\npipeline_version: {PIPELINE_VERSION}\n---\n\n"
    edition += opening_content + "\n\n---\n\n"

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


def write_manifest(month: str, sections: list, summary_quality: str, fiches: list,
                   variant: str | None = None):
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

    macro_prompt_path = PROJECT_ROOT / "editorial" / "prompts" / "macro_brief.md"
    macro_prompt_hash = None
    if macro_prompt_path.exists():
        macro_prompt = macro_prompt_path.read_text(encoding="utf-8")
        macro_prompt_hash = hashlib.sha256(macro_prompt.encode()).hexdigest()[:16]

    manifest = {
        "month": month,
        "publication_date": datetime.now().strftime("%Y-%m-%d"),
        "pipeline_version": PIPELINE_VERSION,
        "sections_produced": section_names,
        "sections_skipped": {s: "data_unavailable" for s in skipped},
        "summary_quality": summary_quality or "n/a",
        "data_periods": data_periods,
        "prompt_hashes": {
            "system_md": hashlib.sha256(system_prompt.encode()).hexdigest()[:16],
            "summary_prompt_md": hashlib.sha256(summary_prompt.encode()).hexdigest()[:16],
            "macro_brief_prompt_md": macro_prompt_hash,
        },
        "llm_model_used": {
            "sections": "claude-sonnet-4-20250514",
            "summary": "claude-sonnet-4-20250514",
        },
        "built_at": datetime.now(timezone.utc).isoformat(),
    }

    out = _drafts_dir(month, variant) / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(f"Manifest: {out}")


@click.command()
@click.option("--month", required=True, help="Edition month (YYYY-MM)")
@click.option("--dry-run", is_flag=True, help="Skip commit step")
@click.option("--only", "only_step", type=click.Choice(STEPS), help="Run only this step")
@click.option("--force", is_flag=True, help="Overwrite existing cache")
@click.option("--variant", default=None,
              help="Optional variant tag (e.g. 'v2'). Drafts land in "
                   "editorial/drafts/{month}-{variant}/ instead of overwriting "
                   "the canonical edition directory.")
def main(month, dry_run, only_step, force, variant):
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

        # 3. DRAFT (sections only)
        if not only_step or only_step == "draft":
            logger.info("--- STEP 3: DRAFT (sections) ---")
            sections, _, draft_status = step_draft(month, fiches, dry_run, variant)
            if draft_status == "failed":
                logger.error("Edition draft failed (output missing or <2 sections)")
                write_manifest(month, sections, "failed", fiches, variant)
                sys.exit(2)

            # 3.5 MACRO BRIEF (or summary fallback)
            logger.info("--- STEP 3.5: MACRO BRIEF ---")
            opening_path, summary_quality = step_macro_brief(month, fiches, sections, variant)

            # Consolidate
            drafts_dir = _drafts_dir(month, variant)
            if opening_path:
                edition_path = _consolidate(opening_path, sections, drafts_dir, month)
            else:
                edition_path = None
                summary_quality = summary_quality or "failed"
        else:
            sections = []
            edition_path = _drafts_dir(month, variant) / "edition.md"
            summary_quality = "unknown"

        # 4. VISUALIZE
        if not only_step or only_step == "visualize":
            logger.info("--- STEP 4: VISUALIZE ---")
            charts = step_visualize(month, fiches)
            logger.info(f"Produced {len(charts)} charts")
        else:
            charts = []

        # 5. BUILD (skipped for variants — would overwrite canonical MDX)
        if (not only_step or only_step == "build") and not variant:
            logger.info("--- STEP 5: BUILD ---")
            step_build(month, edition_path, charts)
        elif variant:
            logger.info(f"--- STEP 5: BUILD (skipped — variant={variant}) ---")

        # Manifest
        write_manifest(month, sections, summary_quality, fiches, variant)

        # 6. COMMIT
        if not only_step or only_step == "commit":
            if dry_run or variant:
                reason = "dry-run" if dry_run else f"variant={variant}"
                logger.info(f"--- STEP 6: COMMIT (skipped — {reason}) ---")
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
