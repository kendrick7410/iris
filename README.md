# Iris

**Industry Reporting & Intelligence System** — monthly editorial pipeline for Cefic.

## Status

**v0.1** — first dry-run edition produced (February 2026, 3 of 3 available sections). Not yet deployed to production. Target deployment is Yaghi (Linux) with a monthly cron job publishing to Azure Static Web Apps.

## What Iris does

Iris fetches monthly data on the European chemical industry from Eurostat (and Comext in production), computes analytical indicators (YoY, pre-crisis gap, sector benchmarks), drafts the editorial sections through the Anthropic API using a system prompt calibrated on Cefic's register, renders SVG charts, and assembles a markdown edition that is served by a static Astro site.

## Project structure

```
data/              Eurostat / Comext fetchers + raw cache
analysis/          indicator engine → JSON fiches
editorial_engine/  LLM drafting (sections + summary)
charts/            SVG rendering (matplotlib + Cefic style)
pipelines/         CLI orchestrator (monthly_run.py)
scripts/           utilities (commit_edition)
site/              static Astro site rendering MDX editions
context-prep/      editorial references (SYNTHESIS, system prompt, SOURCES, ARCHITECTURE, annotated corpus)
tests/             smoke tests for fetchers and analysis
editorial/drafts/  produced editions (versioned as deliverables)
```

## Requirements

- Python 3.9 or later
- Node.js 20 or later (for the Astro site)
- Anthropic API key
- Comext Parquet access (optional) — enables the trade section when available

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
python pipelines/monthly_run.py --month 2026-02 --dry-run
```

The dry run executes the first five steps (fetch, process, draft, visualize, build) without creating a git commit.

To serve the site locally after an edition is produced:

```bash
cd site && npm install && npm run dev
```

## Further reading

- `STATE.md` — detailed project state, known technical debt, full list of L1–L4 deliverables
- `context-prep/` — design references: annotated corpus, SYNTHESIS of Cefic patterns, calibrated system prompt, orchestrator architecture, data sources

## License

Proprietary. © 2026 Cefic. This repository contains internal code and editorial materials intended for Cefic use. Not licensed for external distribution.
