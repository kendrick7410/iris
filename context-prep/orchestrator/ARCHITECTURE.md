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

---

## A.5 — Livrable 5 : enrichissement éditorial (macro brief + trade drill-down)

Date : 2026-04-21. Déclencheur : deck `china_us_trade_brief_14042026.pptx` (cf. `context-prep/editorial/deck-reference-analysis.md`), qui introduit Pareto, dualité volume/valeur et drill-down CN 8-digit. Ces patterns sont formalisés dans `SYNTHESIS.md` §19–21 et `system.md` §2.8, §5.6–5.8.

L5 **étend** le pipeline v1 — aucun module v1 n'est réécrit. Les contrats d'API internes sont conservés. Les éditions v1 restent lisibles sans migration.

### A.5.1 — Nouveau mouvement : Macro Brief

Chaque édition L5+ ouvre par un **macro brief** qui remplace le summary v1 en tête d'édition :

- **1 titre-diagnostic** (Pattern 4) — déclaration-finding avec chiffre saillant du mois
- **4 KPI cards** (cf. Décision L5.1 pour la 4e) — Output YoY, Trade balance YoY, Producer prices YoY, + 1 variable
- **1 bulletin narratif 80–120 mots** — synthèse du mois intégrant la triple temporalité (Pattern §2.8)

Le macro brief est rédigé **après** les sections individuelles, parce qu'il les résume. C'est une inversion par rapport à v1 (où le summary était rédigé aussi après, mais avec un prompt différent).

**Schéma fiche `macro_brief.json`** (`data/processed/YYYY-MM/fiches/macro_brief.json`) :

```json
{
  "section_type": "macro_brief",
  "period": { "month": "2026-02", "publication_date": "2026-04-21", "window": "February 2026" },
  "kpis": [
    {
      "key": "output_yoy",
      "label": "Chemical output",
      "primary_value": 79.3,
      "primary_unit": "index 2021=100",
      "delta_value": -3.9,
      "delta_unit": "% YoY",
      "direction": "down",
      "source_fiche": "output"
    },
    {
      "key": "trade_balance_yoy",
      "label": "Trade balance",
      "primary_value": 12.4,
      "primary_unit": "€ bn",
      "delta_value": -1.8,
      "delta_unit": "€ bn YoY",
      "direction": "down",
      "source_fiche": "trade_exports|trade_imports"
    },
    {
      "key": "prices_yoy",
      "label": "Producer prices",
      "primary_value": 117.2,
      "primary_unit": "index 2021=100",
      "delta_value": -2.8,
      "delta_unit": "% YoY",
      "direction": "down",
      "source_fiche": "prices"
    },
    {
      "key": "capacity_util",        // cf. Décision L5.1 — may fall back to confidence or omit
      "label": "Capacity utilisation",
      "primary_value": 74.0,
      "primary_unit": "%",
      "delta_value": -0.8,
      "delta_unit": "pp YoY",
      "direction": "down",
      "source_fiche": "capacity"
    }
  ],
  "headline_data": {
    "concentration_pareto": { "top_n": 5, "share_pct": 72.0, "scope": "top-5 export partners cover 72% of value" },
    "volume_value_divergence": { "volume_pct": -3.0, "value_pct": 7.3, "note": "strong divergence" }
  },
  "source": "Cefic analysis based on Eurostat data and Comext (2026)"
}
```

**Prompt dédié** : `editorial/prompts/macro_brief.md`. Contient les règles spécifiques au bulletin (80-120 mots, pas de paragraphe conclusif, triple temporalité encouragée, heading-as-finding, interdiction d'inventer une concentration quand `concentration_pareto.share_pct < 50`). Le système de base `system.md` reste chargé en amont comme pour les sections.

**Arborescence ajoutée :**

```
data/processed/YYYY-MM/fiches/
  └── macro_brief.json                     [NEW — assemblé depuis les autres fiches]
editorial/drafts/YYYY-MM/
  └── macro.md                             [NEW — heading + KPI cards MDX + bulletin]
editorial/prompts/
  └── macro_brief.md                       [NEW]
site/public/charts/YYYY-MM/
  └── macro_kpi_<key>.svg                  [NEW — 4 KPI cards]
```

Intégration dans `edition.md` : `macro.md` remplace `summary.md` en ouverture. L'ordre d'assemblage devient `macro → output → prices → sales → trade_exports → trade_imports`.

### A.5.2 — Enrichissement sections trade

Les fiches `trade_exports.json` et `trade_imports.json` v1 (livrable 4) contiennent : totaux courant/YoY/YTD, top-10 partenaires, breakdown par `chapter_cn`. C'est suffisant pour une narration Pattern 3+6, mais trop plat pour déclencher Patterns 19/20/21.

**Enrichissements L5 (fichier `trade.json` étendu par `comext.py`) :**

1. **Fenêtre 5 ans** (`five_year_window`). Agrégation sur 60 mois glissants (période cible − 5 ans → période cible), pour matérialiser le cadrage longue durée du deck (slides 10, 15, 20, 25).
2. **Top 3 NACE par partenaire**, pour les 5 premiers partenaires. Permet la narration "[US chemical imports rose X% — led by NACE 20.14, ...]".
3. **Drill-down CN 8-digit** pour les **key partners** uniquement (US, CN, GB par défaut — cf. Décision L5.2). Top-5 codes par variation absolue entre fenêtre 5 ans (ou YoY, cf. L5.4).

**Structure `trade.json` étendue** (chaque flow `exports`/`imports`) :

```json
{
  "current":          {"value_eur_bn": ..., "volume_kt": ..., "period": "..."},
  "previous_year":    {... existing ...},
  "ytd":              {... existing ...},
  "five_year_window": {                                         // NEW
    "start": "2021-02",
    "end":   "2026-02",
    "value_eur_bn_start": ..., "value_eur_bn_end": ..., "delta_pct_value": ...,
    "volume_kt_start":    ..., "volume_kt_end":    ..., "delta_pct_volume": ...
  },
  "by_partner": [                                                // EXTENDED
    {
      "rank": 1, "partner": "US", "label": "United States",
      "value_eur_bn": ..., "yoy_pct": ..., "share_pct": ...,
      "five_year_delta_pct_value":  ...,                         // NEW
      "five_year_delta_pct_volume": ...,                         // NEW
      "top_nace": [                                              // NEW — top 3 NACE par partenaire
        {"nace4": "20.14", "label": "Other organic basic chemicals", "value_eur_bn": ..., "share_of_partner_pct": ...},
        ...
      ],
      "drill_down": {                                            // NEW — key partners only
        "window": "2021-02..2026-02",
        "delta_total_eur_bn": 12.3,
        "covers_pct_of_delta": 54,
        "cn8_codes": [
          {"code": "29091990", "label_short": "Acyclic ethers and derivatives",
           "contribution_eur_bn": 7.6, "pct_of_delta": 24}
        ]
      }
    }
  ],
  "by_chapter":     {... existing ...}
}
```

Les champs `top_nace` et `drill_down` sont présents **uniquement** pour les partenaires où les règles de Pattern 19/21 sont satisfaites. Sinon omis (pas de clé à `null` — la clé est simplement absente).

**Impact sur `data/fetchers/comext.py` — extensions, pas réécriture :**

- L'API publique `read_parquet(month, cache_dir) → Path` reste identique.
- Nouveau helper interne `_aggregate_flow()` étendu avec paramètre `key_partners: list[str]` (défaut `["US","CN","GB"]`).
- Nouveau helper `_five_year_window(flow_df, target)` — lecture du parquet déjà en mémoire, pas de relecture disque.
- Nouveau helper `_top_nace_per_partner(flow_df, partner, n=3)` — agrégation supplémentaire `groupby(partner, chapter_cn)` (≈ 20 chapitres × 10 partenaires, négligeable).
- Nouveau helper `_drill_down_cn8(flow_df, partner, start_period, end_period)` — agrégation `groupby(partner, product_nc)` restreinte au partenaire, calcul variation absolue entre périodes, top-5 par |variation|. Jointure `product_dim.parquet` pour `label_short` (troncation 40 car. appliquée ici, côté data). Activé seulement si `(top_5 / total_delta) ≥ 0.5`.

**Budget performance estimé.** Le parquet fait 193 MB / 14M rows. v1 fait ~9 s. L5 ajoute : fenêtre 5 ans (filtre déjà dataframe en mémoire : < 1 s), top_nace × 5 partenaires (5 groupby négligeables), drill_down × 3 partenaires (3 groupby restreintes). Estimation totale : **~12 s** pour le fetcher comext. Toujours dominé par la lecture parquet initiale.

**Mapping NACE 4-digit.** Le deck utilise NACE 4-digit (20.11, 20.14, 21.10, …), absent aujourd'hui du parquet fact (`chapter_cn` est 2-digit CN, pas NACE). Le mapping NACE 4-digit vient de `SubstanceId.csv` (cf. `SOURCES.md` §4.7). **Deux options :**
- **Option A** : enrichir le parquet upstream (Comext ETL ajoute une colonne `nace4` via `SubstanceId.csv`). Contredit la règle "Iris ne touche pas au pipeline Comext".
- **Option B** : Iris joint en lecture seule avec `SubstanceId.csv` (accessible hors parquet). Nouveau fichier `data/ref/SubstanceId.csv` (ou symlink vers `../comext-etl/SubstanceId.csv`). Recommandé.

Décision proposée : **Option B**. Même contrat que Comext Parquet (lecture seule), pas d'intrusion dans l'ETL upstream. Documenté dans `SOURCES.md` §4.7.

### A.5.3 — Nouveaux templates de charts

Trois nouveaux modules sous `charts/templates/`, tous consommant `charts/style.py` (pas de couleurs en dur).

**`stacked_bars_nace.py`** — reproduit slides 11, 16, 21, 26 (stacked) et 12, 17, 22, 27 (clustered avec annotations YoY).

```python
def render(
    by_year_by_nace: dict,                   # {"2021": {"20.14": 12.3, ...}, ...}
    nace_labels: dict,                       # {"20.14": "Other organic basic chemicals", ...}
    dimension: str,                          # "volume" or "value"
    title: str,
    svg_path: Path,
    mode: str = "stacked",                   # "stacked" | "clustered"
    annotate_yoy_last: bool = False,         # adds "+X.X%" labels on last year's bars
    year_range: tuple | None = None,         # (2021, 2025), optional explicit range
) -> Path:
```

**`waterfall_contribution.py`** — reproduit slides 13, 18, 23, 28 avec **bridge/waterfall** au lieu de pie (décision Phase 1 : le pie est hors-corpus Cefic in-depth). Affiche chaque CN8 code comme une barre de contribution, puis "Other products", puis un total ombré.

```python
def render(
    contributions: list[dict],               # [{"label": "29091990 (acyclic ethers)", "value": 7.6}, ...]
    other_value: float,
    total_label: str,
    dimension: str,                          # "volume" or "value"
    unit: str,                               # "mln tonnes" or "€ bn"
    title: str,
    svg_path: Path,
) -> Path:
```

**`kpi_card.py`** — composant "KPI card" pour le macro brief. Valeur principale grosse + label + delta coloré + sparkline 12 mois optionnelle. Produit un SVG standalone (1 SVG par KPI) ; la grille 2×2 est assemblée côté MDX/Astro via un snippet CSS.

```python
def render(
    label: str,
    primary_value: str,                      # pre-formatted, e.g. "79.3"
    primary_unit: str,                       # e.g. "index 2021=100"
    delta_value: float,
    delta_unit: str,                         # e.g. "% YoY", "€ bn YoY", "pp YoY"
    direction: str,                          # "up" | "down" | "flat"
    sparkline_data: list[float] | None,      # 12 months, optional
    svg_path: Path,
    dims: tuple = (280, 160),                # default KPI card size in px
) -> Path:
```

**Dispatcher update (`charts/render.py`) :**

```python
CHART_DISPATCHERS = {
    # v1 (existing)
    "output_index":                          ("index_timeseries", "EU27 chemical output (index 2021=100)"),
    ... existing ...,

    # L5 (new)
    "trade_exports_nace_stacked":            ("stacked_bars_nace", "EU27 extra-EU chemical exports by NACE 4-digit"),
    "trade_imports_nace_stacked":            ("stacked_bars_nace", "EU27 extra-EU chemical imports by NACE 4-digit"),
    "trade_exports_waterfall_cn8":           ("waterfall_contribution", "EU27 export drivers — top CN 8-digit codes"),
    "trade_imports_waterfall_cn8":           ("waterfall_contribution", "EU27 import drivers — top CN 8-digit codes"),
    "macro_kpi_output":                      ("kpi_card", None),
    "macro_kpi_trade_balance":               ("kpi_card", None),
    "macro_kpi_prices":                      ("kpi_card", None),
    "macro_kpi_capacity":                    ("kpi_card", None),  // or "confidence", cf. Décision L5.1
}
```

### A.5.4 — Impact pipeline (nouvelle étape 3.5 + revue SECTION_ORDER)

Flow L5 :

```
CLI: python pipelines/monthly_run.py --month 2026-02
  │
  ├─ 1. FETCH                              [~30s, network + parquet]
  │       [existing — comext.py étendu mais même API, voir A.5.2]
  │
  ├─ 2. PROCESS                            [<5s]
  │       [existing — build_fiches() émet les 5 fiches existantes]
  │
  ├─ 3. DRAFT (sections individuelles)     [~60s, API-bound]
  │       [existing — output/prices/sales/trade_exports/trade_imports]
  │
  ├─ 3.5 MACRO BRIEF                       [NEW, ~25s]
  │   │
  │   │  Input:   editorial/drafts/YYYY-MM/sections/*.md
  │   │           data/processed/YYYY-MM/fiches/*.json
  │   │           editorial/prompts/macro_brief.md
  │   │           context-prep/editorial/system.md
  │   │  Output:  data/processed/YYYY-MM/fiches/macro_brief.json
  │   │           editorial/drafts/YYYY-MM/macro.md
  │   │  Deps:    DRAFT (≥ output + 1 other section) completed
  │   │
  │   ├─ analysis.build_macro_brief_fiche(fiches_dir, sections_dir)
  │   │     - Selects 4 KPI values from available fiches
  │   │     - Applies Pareto / duality / concentration checks
  │   │     - Emits macro_brief.json
  │   │
  │   └─ editorial_engine.draft_macro_brief(fiche, system_prompt, macro_prompt)
  │       - Receives macro_brief.json + sections/*.md (as context, not re-edit)
  │       - Emits macro.md (heading + bulletin ; KPI cards are rendered in VISUALIZE)
  │
  ├─ 4. VISUALIZE                          [~15s, extended]
  │       [+ KPI cards rendering, + stacked bars, + waterfall]
  │
  ├─ 5. BUILD                              [existing, extended]
  │       SECTION_ORDER becomes:
  │         ["macro_brief", "output", "prices", "sales", "trade_exports", "trade_imports"]
  │       _consolidate() assembles macro.md + 5 sections (instead of summary.md + 4).
  │
  └─ 6. COMMIT                             [existing]
```

**Rétro-compatibilité.** Les éditions v1 (février 2026 v1) n'ont **pas** de `macro_brief` : leur `edition.md` est intouché. Le pipeline gère les deux cas :

- Si `editorial/prompts/macro_brief.md` est absent → pipeline v1 (summary + sections).
- Si présent → pipeline L5 (macro + sections).

`manifest.json` gagne un champ `pipeline_version` (`"0.1.0"` pour v1, `"0.2.0"` pour L5). Les tests de régression de v1 (édition 2026-02 existante) doivent continuer à passer sans modification.

**Mise à jour de `context-prep/editorial/system.md` §9 (output contract).** Le `section_type` accepté gagne `"macro_brief"`. La règle "no conclusion" reste, avec une exception explicite pour le bulletin macro : il peut inclure un clôture-diagnostic *si* celle-ci est un chiffre ou une tendance quantifiée, pas une synthèse qualitative. Ce patch est porté **en Phase 4 commit 1** (dans le même commit que les patterns), pas ici.

### A.5.5 — Points de décision ouverts (L5)

**Décision L5.1 — La 4e KPI du macro brief.**

Trois candidats évalués :

| Candidat | Source Eurostat | Latence | Coverage | Pro | Contra |
|---|---|---|---|---|---|
| **Capacity utilisation** | `sts_indt_m` (NACE C20, unit PC) | ~30 j | Trimestriel (publié mensuel parfois) | Indicateur-phare Chemical Trends ; toujours présent dans les rapports Cefic | Trimestriel → certains mois sans update frais |
| **Confidence indicator** | DG ECFIN `bs_...` | ~10 j | Mensuel, live | Très frais, cohérent avec la triple temporalité | Hors corpus Cefic pur — plus DG ECFIN qu'indicateur chimique en tant que tel |
| **TTF gas price** | Eurostat `nrg_prc_...` | ~45 j | Mensuel | Saillant pour l'industrie chimique (coût intrant majeur) | Demande nouveau fetcher (v1.2) — pas dans v1 |

**Proposition : variable selon disponibilité, ordre décroissant.** `build_macro_brief_fiche()` tente dans l'ordre :
1. Capacity utilisation (Eurostat `sts_indt_m`), si un point disponible ≤ 90 j.
2. Confidence indicator (DG ECFIN), si capacity indisponible pour le mois.
3. Omission silencieuse — le macro brief présente 3 KPI cards au lieu de 4. Pas de placeholder.

Implication : liste `kpis` dynamique (longueur 3 ou 4), layout Astro 2×2 s'adapte (1 cell vide ou grille 3×1 responsive).

**Décision L5.2 — Drill-down CN : automatique ou seuillé.**

**Proposition : seuillé.** Le drill-down CN 8-digit est produit si et seulement si :
1. Le partenaire est dans la liste `KEY_PARTNERS` (défaut `["US","CN","GB"]`, override via `--key-partners`).
2. ET le top-5 CN8 codes explique ≥ 50 % de la variation en valeur entre `five_year_window.start` et `five_year_window.end`.

Sinon, pas de drill-down pour ce partenaire. La prose reflète alors Pattern 18 : *"For [partner], the change was broadly distributed across the product mix."* Pas de pis-aller qui affiche 5 codes expliquant 20 %.

**Décision L5.3 — Rétro-compatibilité éditions v1.**

**Proposition : on n'y touche pas.** Cohérent avec la règle "snapshot d'origine" implicite de `system.md` (une publication Cefic n'est jamais rééditée rétroactivement).

Concrètement :
- `editorial/drafts/2026-02/edition.md` reste le run v1, snapshot historique.
- Si on veut une version L5 de février 2026, on la produit sous `editorial/drafts/2026-02-v2/` ou on la laisse au **prochain** cron mensuel (2026-04 ou 2026-05 selon fraîcheur data).
- Site Astro : deux cartes d'édition coexistent (v1 et v2+) — le composant de rendu détecte l'absence de `macro.md` et retombe sur `summary.md`.

**Décision L5.4 — Position du drill-down CN dans la section trade.**

Deux options :
- (a) **Inline** — le drill-down apparaît à l'intérieur de la section trade après le ranking Pattern 6 et avant la source line. 1 paragraphe par key partner, intercalé.
- (b) **Sous-section séparée** — un bloc `### Drill-down` après le by_partner breakdown.

**Proposition : (a) inline.** Cohérent avec la voix Cefic : les sections sont des séquences analytiques, pas des juxtapositions de blocs. Le drill-down émerge naturellement après le ranking. Structure cible :

```markdown
## EU27 chemical exports amounted to €X bn in [month] ...
[opening Pattern 3]
[ranking Pattern 6 — top 5 partners]
[NACE breakdown — top 3 NACE 4-digit, listés par partenaire clé]
[Drill-down inline pour chaque key partner où Pattern 21 s'applique]
Source: Cefic analysis based on Eurostat data (YYYY)
```

Conséquence : les sections trade passent d'environ 150 mots (v1 livré Étape 5) à **~350–450 mots** (L5). Acceptable — le deck de référence (slides 13, 18, 23, 28) fait plus dense encore, et cette longueur reste sous les sections output+prices+sales consolidées.

---

*En attente du feu vert de Jonathan sur les Décisions L5.1 à L5.4 avant implémentation Phase 4.*
