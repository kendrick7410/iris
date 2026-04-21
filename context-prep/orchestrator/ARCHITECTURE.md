# Iris Orchestrator — Architecture v1

Date: 2026-04-18

---

## A.1 — Flow d'une édition mensuelle

```
CLI: python pipelines/monthly_run.py --month 2026-02
  │
  ├─ 1. FETCH                          [~30s, network-bound]
  │   │
  │   │  Input:  --month YYYY-MM
  │   │  Output: data/cache/YYYY-MM/*.json (one per dataset)
  │   │  Skip if: cache files exist and --force not set
  │   │
  │   ├─ eurostat.fetch_production(month)
  │   │     API: sts_inpr_m, unit=I21, s_adj=SCA
  │   │     Geos: EU27_2020 + DE,FR,IT,NL,ES,BE,PL
  │   │     NACE: C20 + C,C21,C24,C29 (benchmarks)
  │   │     Window: month M + M-12 (YoY)
  │   │     Pre-crisis: 2014-01 to 2019-12 (unit=I15, converted to I21)
  │   │     → data/cache/YYYY-MM/production.json
  │   │
  │   ├─ eurostat.fetch_prices(month)
  │   │     API: sts_inppd_m, unit=I21, s_adj=NSA
  │   │     Same geos/NACE as production
  │   │     → data/cache/YYYY-MM/prices.json
  │   │
  │   ├─ eurostat.fetch_turnover(month)
  │   │     API: sts_intv_m, unit=I21, s_adj=SCA
  │   │     Note: latest available may be month-1 (higher latency)
  │   │     → data/cache/YYYY-MM/turnover.json
  │   │
  │   ├─ eurostat.fetch_gdp(month)
  │   │     API: nama_10_gdp, unit=CLV10_MEUR, na_item=B1GQ
  │   │     → data/cache/YYYY-MM/gdp.json
  │   │
  │   └─ comext.read_parquet(month)
  │         Source: $COMEXT_DATA_PATH/*.parquet
  │         If path not set or files missing: write trade_unavailable.json
  │         → data/cache/YYYY-MM/trade.json
  │
  ├─ 2. PROCESS                        [<5s, CPU-bound]
  │   │
  │   │  Input:  data/cache/YYYY-MM/*.json
  │   │  Output: data/processed/YYYY-MM/fiches/*.json
  │   │  Deps:   FETCH completed
  │   │
  │   └─ analysis.build_fiches(cache_dir, month)
  │         For each available dataset:
  │           - Calculate YoY delta_pct
  │           - Calculate pre-crisis delta_pct (if baseline exists)
  │           - Calculate YTD averages (if month > January)
  │           - Build by_country and by_sector dicts
  │           - Emit fiche JSON per system.md §10 schema
  │         → data/processed/YYYY-MM/fiches/output.json
  │         → data/processed/YYYY-MM/fiches/prices.json
  │         → data/processed/YYYY-MM/fiches/sales.json
  │         → data/processed/YYYY-MM/fiches/trade_exports.json (or skipped)
  │         → data/processed/YYYY-MM/fiches/trade_imports.json (or skipped)
  │
  ├─ 3. DRAFT                          [~60s, API-bound]
  │   │
  │   │  Input:  data/processed/YYYY-MM/fiches/*.json
  │   │          context-prep/editorial/system.md
  │   │  Output: editorial/drafts/YYYY-MM/sections/*.md
  │   │          editorial/drafts/YYYY-MM/summary.md
  │   │          editorial/drafts/YYYY-MM/edition.md
  │   │          editorial/drafts/YYYY-MM/llm_log.jsonl
  │   │  Deps:   PROCESS completed
  │   │
  │   ├─ For each fiche:
  │   │     editorial.draft_section(fiche, system_prompt)
  │   │       → API call: model=claude-sonnet-4-5, temp=0.3
  │   │       → Retry: 3 attempts with exponential backoff (2s, 8s, 32s)
  │   │         Retry on: timeout, 429 (rate limit), 5xx
  │   │         No retry on: 400/401/403 (config error)
  │   │       → Log: {timestamp, section_type, system_hash, user_msg, response, model, tokens}
  │   │       → editorial/drafts/YYYY-MM/sections/{section_type}.md
  │   │       → If failed after 3 retries: mark draft_failed in manifest, skip section
  │   │
  │   │  Section ordering: output → prices → sales → trade_exports → trade_imports
  │   │  If a fiche is missing (e.g. trade), section is not generated.
  │   │  If ≥3 sections fail: exit code 1, no branch created.
  │   │  If ≤2 fail AND output succeeds: partial publication (see error handling).
  │   │
  │   ├─ editorial.draft_summary(sections)
  │   │     Input: concatenated sections + summary_prompt.md
  │   │     → editorial/drafts/YYYY-MM/summary.md
  │   │
  │   └─ editorial.consolidate(summary, sections)
  │         Assembles: summary + sections in order → edition.md
  │         Inserts frontmatter YAML: month, publication_date, sections list
  │         → editorial/drafts/YYYY-MM/edition.md
  │
  ├─ 4. VISUALIZE                      [~10s, CPU-bound]
  │   │
  │   │  Input:  data/processed/YYYY-MM/fiches/*.json
  │   │  Output: site/public/charts/YYYY-MM/*.svg
  │   │  Deps:   PROCESS completed (independent of DRAFT)
  │   │
  │   └─ charts.render(fiches_dir, output_dir)
  │         For each fiche, for each chart_id:
  │           - matplotlib figure → SVG
  │           - Embed source line in chart footer
  │           - Filename: {chart_id}.svg
  │         → site/public/charts/YYYY-MM/output_index.svg
  │         → site/public/charts/YYYY-MM/output_yoy_country.svg
  │         → etc.
  │
  ├─ 5. BUILD                          [~15s, npm-bound]
  │   │
  │   │  Input:  editorial/drafts/YYYY-MM/edition.md
  │   │          site/public/charts/YYYY-MM/*.svg
  │   │  Output: site/src/content/editions/YYYY-MM.mdx
  │   │          site/dist/ (after manual astro build)
  │   │  Deps:   DRAFT + VISUALIZE completed
  │   │
  │   ├─ site.prepare_content(edition_md)
  │   │     Converts edition.md to MDX:
  │   │       - Replaces {{chart:chart_id}} with <img src="/charts/YYYY-MM/{chart_id}.svg" />
  │   │       - Preserves frontmatter
  │   │     → site/src/content/editions/YYYY-MM.mdx
  │   │
  │   └─ [MANUAL] cd site && npm run build
  │         Documented, not automated. Jonathan runs after reviewing edition.md.
  │         → site/dist/
  │
  └─ 6. COMMIT                         [<5s, git-bound]
      │
      │  Input:  all produced artifacts
      │  Output: local git branch edition/YYYY-MM
      │  Deps:   BUILD completed (or --dry-run skips this)
      │
      └─ scripts.commit_edition(month)
            git checkout -b edition/YYYY-MM
            git add editorial/drafts/YYYY-MM/edition.md
            git add editorial/drafts/YYYY-MM/manifest.json
            git add editorial/drafts/YYYY-MM/sections/*.md
            git add editorial/drafts/YYYY-MM/summary.md
            git add site/src/content/editions/YYYY-MM.mdx
            git add site/public/charts/YYYY-MM/*.svg
            git commit -m "edition: YYYY-MM"
            *** NEVER push ***
```

### Parallélisation

Étapes 3 (DRAFT) et 4 (VISUALIZE) sont indépendantes et pourraient tourner en parallèle. Pour v1, on les exécute séquentiellement (simplicité). En v1.1, les sections DRAFT peuvent être parallélisées via `asyncio` + `anthropic.AsyncAnthropic`.

### Gestion d'erreur par étape

| Étape | Si échec | Comportement |
|---|---|---|
| FETCH (1 dataset) | API timeout / 4xx / 5xx | Log l'erreur, continue les autres. La section correspondante sera omise. |
| FETCH (tous datasets) | Aucune donnée récupérée | Exit code 2 ("data incomplète"). Stop. |
| PROCESS | Calcul échoue | Log, omit la fiche. Rare (pas de I/O). |
| DRAFT (1 section) | API error / timeout | Retry 1x après 30s. Si échec, log, omit la section. |
| DRAFT (summary) | Nécessite ≥2 sections | Si <2 sections rédigées, skip summary. Exit code 2. |
| VISUALIZE | matplotlib error | Log, skip le chart. Edition.md garde le placeholder `{{chart:id}}`. |
| BUILD | MDX conversion error | Log, stop. Pas de build partiel. |
| COMMIT | Git error | Log. Edition.md reste sur disque, non committé. |

**Règle : l'édition est publiée si ≥2 sections produites ET Output présent.** La section Output est le chiffre d'actualité le plus attendu d'un rapport mensuel chimie — sans elle, l'édition n'a pas de colonne vertébrale éditoriale.

Si Output absent : exit code 2, alerte dans les logs, aucune branche `edition/YYYY-MM` créée. Le pipeline sauvegarde les fiches et sections déjà produites dans `data/processed/` et `editorial/drafts/` pour un rejeu ultérieur.

Si ≥3 sections échouent (draft API failure) : exit code 1, aucune branche créée.

---

## A.2 — Modèle de données

### Fiche d'indicateur

`data/processed/YYYY-MM/fiches/{section_type}.json`

Schéma définitif, réconcilié entre `system.md` §10 et `SOURCES.md` §7 :

```json
{
  "section_type": "output | prices | sales | trade_exports | trade_imports",
  "period": {
    "month": "2026-02",
    "publication_date": "2026-04-18",
    "window": "January-February 2026",
    "window_months": 2,
    "window_ordinal": "first two"
  },
  "data": {
    "current": {
      "value": 79.3,
      "unit": "index 2021=100",
      "period": "2026-02",
      "s_adj": "SCA"
    },
    "previous_year": {
      "value": 82.5,
      "period": "2025-02",
      "delta_pct": -3.9
    },
    "pre_crisis_avg": {
      "value": 96.7,
      "base": "2014-2019 average, I15 converted to I21",
      "delta_pct": -18.0
    },
    "ytd": {
      "current_avg": 79.1,
      "previous_year_avg": 82.5,
      "delta_pct": -4.1
    },
    "by_country": {
      "DE": { "current": 77.3, "previous_year": 80.1, "yoy_pct": -3.5 },
      "FR": { "current": 93.5, "previous_year": 92.5, "yoy_pct": 1.1 }
    },
    "by_sector": {
      "C":   { "label": "Total manufacturing", "current": 100.2, "previous_year": 100.6, "yoy_pct": -0.4 },
      "C20": { "label": "Chemicals", "current": 79.3, "previous_year": 82.5, "yoy_pct": -3.9 }
    },
    "source": "Cefic analysis based on Eurostat data (sts_inpr_m, 2026)"
  },
  "charts": ["output_index", "output_yoy_country"],
  "editorial_context": {
    "latest_structural_break": "March 2022",
    "notable_events": [],
    "pre_crisis_reference": "2014-2019 average"
  }
}
```

Notes :
- `pre_crisis_avg` est `null` si non calculable (ex: prices, pas de baseline I15 disponible).
- `ytd` est `null` si mois = janvier (un seul mois, pas de YTD pertinent).
- `by_country` contient toujours les 7 top chimistes : DE, FR, IT, NL, ES, BE, PL.
- `data.source` est la métadonnée de traçabilité — le LLM ne la copie PAS dans la source line publiée (cf. `system.md` §9.7).

### Charte graphique (charts/style.py)

```python
# charts/style.py — contract v1
CEFIC_COLORS = {
    "primary": "#003399",      # Cefic blue (from cefic.org branding)
    "positive": "#2E8B57",     # Muted green
    "negative": "#C0392B",     # Muted red
    "benchmark": "#888888",    # Grey for pre-crisis and comparators
    "grid": "#E0E0E0",        # Light grey grid
    "highlight": "#E67E22",    # Orange accent for key data points
}
FONT_STACK = ["Arial", "Helvetica", "sans-serif"]
DEFAULT_DIMS = {"width_px": 800, "height_px": 450, "dpi": 96}

def format_source_line(year: int, note: str = "") -> str:
    """Returns the verbatim Cefic source line per system.md Template 5.4."""
```

### Section rédigée

`editorial/drafts/YYYY-MM/sections/{section_type}.md`

```markdown
---
section_type: output
order: 1
charts:
  - output_index
  - output_yoy_country
period: 2026-02
generated_at: 2026-04-18T14:30:00Z
model: claude-sonnet-4-5
---

## EU27 chemical output remains 18% below pre-crisis levels in February 2026

[... prose ...]

{{chart:output_index}}
Source: Cefic analysis based on Eurostat data (2026)

[... transition sentence ...]

{{chart:output_yoy_country}}
Source: Cefic analysis based on Eurostat data (2026)
```

### Résumé exécutif

`editorial/drafts/YYYY-MM/summary.md`

```markdown
---
type: summary
period: 2026-02
sections_used: [output, prices, sales]
generated_at: 2026-04-18T14:31:00Z
model: claude-sonnet-4-5
---

## The EU27 chemical industry [diagnostic in one sentence]

- [Bullet 1: situation actuelle — production, demande]
- [Bullet 2: pression concurrentielle — prix, imports]
- [Bullet 3: driver structurel — énergie, régulation]
- [Bullet 4: indicateur avancé — investissement, fermetures]
```

Produit par un system prompt dédié (`summary_prompt.md`) qui impose l'arc en 4 bullets du Pattern 12.

### Édition consolidée

`editorial/drafts/YYYY-MM/edition.md`

```markdown
---
month: 2026-02
publication_date: 2026-04-18
sections: [output, prices, sales]
trade_available: false
---

[summary.md content]

---

[sections/output.md content]

---

[sections/prices.md content]

---

[sections/sales.md content]
```

Assemblage mécanique : frontmatter consolidé + summary + sections dans l'ordre canonique, séparés par `---`.

### Manifest

`editorial/drafts/YYYY-MM/manifest.json`

```json
{
  "month": "2026-02",
  "publication_date": "2026-04-18",
  "pipeline_version": "0.1.0",
  "sections_produced": ["output", "prices", "sales"],
  "sections_skipped": {"trade_exports": "COMEXT_DATA_PATH not set", "trade_imports": "COMEXT_DATA_PATH not set"},
  "data_periods": {
    "output": "2026-02",
    "prices": "2026-02",
    "sales": "2026-01"
  },
  "eurostat_latest_fetch": "2026-04-18T14:00:00Z",
  "llm_model": "claude-sonnet-4-5",
  "llm_calls": 4,
  "system_prompt_hash": "sha256:abc123...",
  "exit_code": 0
}
```

---

## A.3 — Arborescence finale du projet

```
iris/
├── .env                              # ANTHROPIC_API_KEY, COMEXT_DATA_PATH  [gitignored]
├── .env.example                      # Template sans valeurs               [versioned]
├── .gitignore                                                              [versioned]
├── CLAUDE.md                                                               [versioned]
├── README.md                                                               [versioned]
├── requirements.txt                                                        [versioned]
├── package.json                      # Workspace root (si monorepo)        [versioned]
│
├── context-prep/                     # Travail éditorial pré-bootstrap     [versioned]
│   ├── corpus/                       #   Publications annotées
│   ├── data-sources/                 #   SOURCES.md
│   ├── editorial/                    #   system.md, test-inputs, test-outputs
│   └── orchestrator/                 #   ARCHITECTURE.md (ce fichier)
│
├── data/
│   ├── cache/                        # Raw API responses                   [gitignored]
│   │   └── YYYY-MM/
│   │       ├── production.json
│   │       ├── prices.json
│   │       ├── turnover.json
│   │       ├── gdp.json
│   │       └── trade.json
│   ├── processed/                    # Computed fiches                     [gitignored]
│   │   └── YYYY-MM/
│   │       └── fiches/
│   │           ├── output.json
│   │           ├── prices.json
│   │           ├── sales.json
│   │           └── trade_exports.json
│   └── baselines/                    # Pre-crisis averages, conversion     [versioned]
│       └── precrisis_i21.json        #   factors (computed once, cached)
│
├── editorial/
│   ├── system.md                     # Production system prompt            [versioned]
│   ├── summary_prompt.md             # Summary-specific system prompt      [versioned]
│   └── drafts/                                                             [partially versioned]
│       └── YYYY-MM/
│           ├── sections/             # Individual section .md              [versioned]
│           ├── summary.md                                                  [versioned]
│           ├── edition.md                                                  [versioned]
│           ├── manifest.json                                               [versioned]
│           └── llm_log.jsonl         # Full prompt/response log           [gitignored]
│
├── pipelines/
│   └── monthly_run.py                # Main CLI entry point                [versioned]
│
├── data/fetchers/
│   ├── __init__.py
│   ├── eurostat.py                   # 4 Eurostat API fetchers             [versioned]
│   └── comext.py                     # Parquet reader (stub until Yaghi)   [versioned]
│
├── analysis/
│   ├── __init__.py
│   └── indicators.py                 # YoY, pre-crisis, YTD, benchmarks   [versioned]
│
├── editorial_engine/
│   ├── __init__.py
│   ├── draft.py                      # Section drafting via Anthropic API  [versioned]
│   └── summary.py                    # Summary generation                  [versioned]
│
├── charts/
│   ├── __init__.py
│   ├── style.py                      # Palette, fonts, dimensions, source line formatter  [versioned]
│   ├── render.py                     # Orchestrator: fiche → SVG           [versioned]
│   └── templates/
│       ├── __init__.py
│       ├── index_timeseries.py       # Index 2021=100 line charts          [versioned]
│       ├── yoy_bars.py               # YoY ranking bar charts             [versioned]
│       └── sector_comparison.py      # C20 vs C21/C24/C29 benchmarks      [versioned]
│
├── scripts/
│   └── commit_edition.py             # Git branch + commit                 [versioned]
│
├── site/                             # Astro static site                   [versioned]
│   ├── astro.config.mjs
│   ├── package.json
│   ├── src/
│   │   ├── content/
│   │   │   └── editions/
│   │   │       └── YYYY-MM.mdx       # Generated per-edition              [versioned]
│   │   ├── layouts/
│   │   │   └── EditionLayout.astro
│   │   └── pages/
│   │       ├── index.astro
│   │       └── editions/
│   │           └── [...slug].astro
│   ├── public/
│   │   └── charts/
│   │       └── YYYY-MM/              # Generated SVG charts               [versioned]
│   ├── node_modules/                                                      [gitignored]
│   └── dist/                                                              [gitignored]
│
└── tests/
    ├── test_eurostat.py
    ├── test_comext.py
    ├── test_indicators.py
    ├── test_draft.py
    ├── test_summary.py
    ├── test_render.py
    └── test_monthly_run.py
```

### Gitignore rules

```gitignore
# Secrets
.env

# Data (cached, not reproducible without API)
data/cache/
data/processed/

# LLM logs (may contain system prompt excerpts)
editorial/drafts/**/llm_log.jsonl

# Site build artifacts
site/node_modules/
site/dist/
site/.astro/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# OS
.DS_Store
Thumbs.db
```

---

## A.4 — Points de décision ouverts

### 1. Publication partielle ou abandon ?

**Proposition : publier partiellement si ≥2 sections sur 4 sont produites.**

Rationale : le Chemical Trends Report de Cefic couvre des fenêtres temporelles différentes par indicateur dans le même rapport (Pattern 18). Une édition avec 3 sections sur 4 est plus utile qu'aucune édition. Le manifest.json documente explicitement quelles sections sont absentes et pourquoi.

Si <2 sections : exit code 2, pas d'édition, log expliquant la cause. Jonathan décide manuellement s'il publie un résumé ad hoc.

### 2. Format des charts : SVG statique vs interactif ?

**Proposition v1 : SVG statique via matplotlib.**

- Print-ready (PDF export direct si besoin)
- Pas de JS runtime nécessaire
- Accessible (alt-text via `<img alt="...">`)
- Aligné avec le format PDF du Chemical Trends Report actuel
- Design sobre : axes, titre, source line en pied

**v1.1 : migration vers ECharts / Observable Plot** pour les tooltips et le responsive. Nécessite un site dynamique (Astro islands), pas un pur static build.

### 3. Manifest des éditions publiées — où ?

**Proposition : `editorial/editions_index.json`** — un fichier unique versionné qui liste toutes les éditions produites.

```json
{
  "editions": [
    { "month": "2026-02", "status": "draft", "sections": ["output","prices","sales"] },
    { "month": "2026-03", "status": "published", "sections": ["output","prices","sales","trade_exports"] }
  ]
}
```

Le pipeline le lit avant de commencer pour vérifier si l'édition existe déjà. Si oui et `--force` n'est pas set, exit avec un message.

Schéma complet :

```json
{
  "schema_version": "1.0",
  "editions": [
    {
      "month": "2026-02",
      "status": "complete | partial | skipped | failed",
      "sections_produced": ["output", "prices", "sales"],
      "sections_skipped": ["trade_exports", "trade_imports"],
      "skip_reasons": {"trade_exports": "comext_unavailable", "trade_imports": "comext_unavailable"},
      "summary_quality": "ok | degraded",
      "prompt_hashes": {
        "system_md": "sha256:...",
        "summary_prompt_md": "sha256:..."
      },
      "llm_model_used": {
        "sections": "claude-sonnet-4-5",
        "summary": "claude-sonnet-4-5"
      },
      "llm_log_path": "editorial/drafts/2026-02/llm_log.jsonl",
      "built_at": "2026-04-18T14:32:00Z",
      "commit_sha": "abc123...",
      "data_snapshot": {
        "eurostat_last_period_available": "2026-02",
        "comext_last_period_available": null
      }
    }
  ]
}
```

`prompt_hashes` permet de savoir avec quelle version du prompt une édition a été produite — audit et reproductibilité.

### 4. Modèle LLM : Sonnet vs Opus ?

**Recommandation : Sonnet pour la rédaction des sections, Sonnet pour le summary.**

Arguments :
- Le system prompt est extrêmement contraint (templates verbatim, listes de connecteurs, anti-patterns). Un modèle plus petit mais bien guidé est aussi bon qu'un gros modèle sur ce type de tâche.
- Les tests du Livrable 3 ont été faits avec Sonnet et ont produit des sorties conformes à 6/7 critères dès la v1.
- Coût : ~3-4 appels API par édition. Sonnet ≈ $0.15/édition vs Opus ≈ $1.50/édition. Pour un run mensuel c'est négligeable, mais pour le debugging itératif c'est 10x.
- Latence : Sonnet ~5-10s par section, Opus ~30-60s. Pas critique en mensuel mais agréable en dev.

**Fallback Opus pour summary.** Re-tenter la génération avec Opus si le summary produit par Sonnet remplit au moins un de ces critères :
- Moins de 80 mots ou plus de 250 mots
- Nombre de bullets ≠ 4
- Présence d'au moins un connecteur de la liste noire `system.md` §4
- Moins de 3 chiffres distincts dans le texte

Si Opus échoue aussi sur ces critères, garder la meilleure des deux sorties (moins de violations) et flaguer dans `manifest.json` avec `summary_quality: "degraded"`. La génération n'échoue pas — le reviewer humain tranche en PR.

---

### 5. Notes ouvertes (v1.1, non-bloquant)

- **Prompts spécialisés par section.** `system.md` générique couvre Output/Prices/Turnover. Quand Trade sera ajouté (v1.1 avec Comext), évaluer si un `system_trade_overlay.md` est nécessaire pour les patterns spécifiques (ranking partenaires, fragmented Europe conditionnel).
- **Linter éditorial automatique.** Check des sections produites contre `SYNTHESIS.md` avant commit (longueur moyenne, connecteurs bannis, densité chiffrée). Reporté en v1.1. Pour v1, le reviewer humain en PR est le linter.

---

*En attente du feu vert de Jonathan pour passer à l'Étape B.*
