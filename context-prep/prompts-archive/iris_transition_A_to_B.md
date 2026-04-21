# Transition Étape A → Étape B

> À coller pour déclencher l'implémentation après les 5 patches d'architecture.

---

`ARCHITECTURE.md` validé avec 5 patches à appliquer d'abord, puis feu vert pour l'Étape B (prototype fonctionnel).

## Patches à appliquer à `ARCHITECTURE.md`

### Patch 1 — Publication partielle : Output obligatoire

Dans la section sur la gestion d'erreur / publication partielle, remplacer la règle actuelle (≥2 sections sur 4) par :

> **Publication partielle** : l'édition est publiée si **≥2 sections produites ET Output présent**. La section Output est le chiffre d'actualité le plus attendu d'un rapport mensuel chimie — sans elle, l'édition n'a pas de colonne vertébrale éditoriale.
>
> Si Output absent : exit code 2, alerte dans `RETROSPECTIVE.md`, aucune branche `edition/YYYY-MM` créée. Le pipeline sauvegarde les fiches et sections déjà produites dans `data/processed/` et `editorial/drafts/` pour un rejeu ultérieur.

### Patch 2 — Fallback Opus : critères de déclenchement

Dans la section sur le choix du modèle LLM, remplacer "Opus en fallback si summary insuffisant" par :

> **Fallback Opus pour summary.** Re-tenter la génération avec Opus si le summary produit par Sonnet remplit au moins un de ces critères :
> - moins de 80 mots ou plus de 250 mots
> - nombre de bullets ≠ 4
> - présence d'au moins un connecteur de la liste noire `system.md` §4
> - moins de 3 chiffres distincts dans le texte
>
> Si Opus échoue aussi sur ces critères, garder la meilleure des deux sorties (moins de violations) et flaguer dans `manifest.json` avec `summary_quality: "degraded"`. La génération n'échoue pas — le reviewer humain tranche en PR.

### Patch 3 — Arborescence charts/ avec style.py

Dans l'arborescence finale (A.3), remplacer le dossier `charts/` par :

```
charts/
├── __init__.py
├── style.py              # palette CEFIC_COLORS, FONT_STACK, DEFAULT_DIMS, format_source_line()
├── render.py             # orchestrateur : prend une fiche, retourne un SVG
└── templates/
    ├── __init__.py
    ├── index_timeseries.py    # pour les index 2021=100 (output, prices, turnover)
    ├── yoy_bars.py            # pour les rankings par YoY
    └── sector_comparison.py   # pour les benchmarks C20 vs C21/C24/C29
```

Ajouter en section A.2 un sous-schéma "Charte graphique" :

```python
# charts/style.py — contract v1
CEFIC_COLORS = {
    "primary": "#...",      # à définir, dérivé de la charte Cefic observée
    "positive": "#...",
    "negative": "#...",
    "benchmark": "#...",    # gris neutre pour pre-crisis et benchmarks
    "grid": "#..."
}
FONT_STACK = ["Arial", "Helvetica", "sans-serif"]
DEFAULT_DIMS = {"width_px": 800, "height_px": 450, "dpi": 96}

def format_source_line(dataset_code: str, year: int, note: str = "") -> str:
    """Returns the verbatim Cefic source line per system.md Template 5.4."""
```

### Patch 4 — Schéma de `editions_index.json`

Ajouter en A.2 le schéma explicite :

```json
{
  "schema_version": "1.0",
  "editions": [
    {
      "month": "2026-02",
      "status": "complete | partial | skipped | failed",
      "sections_produced": ["output", "prices", "turnover"],
      "sections_skipped": ["trade"],
      "skip_reasons": {"trade": "comext_unavailable"},
      "summary_quality": "ok | degraded",
      "prompt_hashes": {
        "system_md": "sha256:...",
        "summary_prompt_md": "sha256:..."
      },
      "llm_model_used": {
        "sections": "claude-sonnet-4-5",
        "summary": "claude-sonnet-4-5 | claude-opus-4-5"
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

### Patch 5 — Gestion erreurs API Anthropic

Ajouter en A.1 dans l'étape DRAFT :

> **Retry et échec API.** Chaque appel LLM a un retry automatique : 3 tentatives avec backoff exponentiel (2s, 8s, 32s). Conditions de retry : timeout, rate limit (429), erreurs 5xx. Pas de retry sur 400/401/403 (erreur de config).
>
> Si une section échoue après 3 retries :
> - Elle est marquée `draft_failed` dans le manifest, exclue de l'édition
> - Le pipeline continue avec les autres sections
> - Si plus de 2 sections échouent (≥3 sur 4) : exit code 1, aucune branche créée
> - Si ≤2 sections échouent ET Output réussit : publication partielle (voir Patch 1)

### Bonus — Note A.4

Ajouter en A.4 (points ouverts pour plus tard, non-bloquant) :

> - **Prompts spécialisés par section.** `system.md` générique couvre Output/Prices/Turnover. Quand Trade sera ajouté (v1.1 avec Comext), évaluer si un `system_trade_overlay.md` est nécessaire pour les patterns spécifiques (ranking partenaires, fragmented Europe conditionnel).
> - **Linter éditorial automatique.** Check des sections produites contre `SYNTHESIS.md` avant commit (longueur moyenne, connecteurs bannis, densité chiffrée). Reporté en v1.1. Pour v1, le reviewer humain en PR est le linter.

## Une fois les 5 patches appliqués

Présente-moi le diff (ou le contenu des 5 sections modifiées) pour validation rapide, puis enchaîne directement sur l'Étape B — prototype fonctionnel.

**Rappel des checkpoints Étape B :**
1. Après implémentation des modules 1-3 (fetchers + analysis) : rapport court
2. Après tous les modules + tests : rapport court
3. Étape C : run end-to-end sur février 2026

Ne brûle pas les checkpoints — même si tu es en flow, stoppe aux points prévus. Un bug de contrat détecté à mi-B est 10x moins cher qu'à la fin de C.

Go.
