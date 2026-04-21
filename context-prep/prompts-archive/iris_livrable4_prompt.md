# Prompt Livrable 4 — Orchestrateur Iris

> À coller dans la session Claude Code en cours.
> `system.md` v2 est validé et stable pour v1 (6/7 dérives corrigées).
> On passe à la machine qui produit une édition mensuelle de bout en bout.

---

Go Livrable 4. Objectif : spécifier et prototyper l'orchestrateur Iris qui prend des données brutes (APIs Eurostat + futures données Comext) et produit une édition mensuelle complète — résumé exécutif + 4 sections — sous forme de site Astro statique prêt à déployer.

## Contraintes de design non-négociables

1. **Python simple, pas de framework d'orchestration.** Scripts linéaires, fonctions pures quand possible, logs structurés. Pas de Prefect, Dagster, Airflow, LangChain. Un `monthly_run.py` lisible de 200-400 lignes qui appelle des modules spécialisés.

2. **Séparation nette data/éditorial/site.** Python produit des artefacts sur disque. Astro les consomme au build. Aucun appel direct Python→Astro ou Astro→Python pendant l'exécution.

3. **Tout doit tourner en local Windows ET sur Yaghi Linux.** Pas de chemin en dur, tout via `pathlib` et variables d'env. Le script doit passer `python pipelines/monthly_run.py --month 2026-02` sur les deux OS.

4. **Idempotent.** Rejouer la commande pour le même mois doit produire le même résultat (aux détails près du LLM — voir règle 5).

5. **Reproductibilité LLM.** Chaque appel API Anthropic est loggé avec prompt complet + réponse + timestamp dans `editorial/drafts/YYYY-MM/llm_log.jsonl`. Permet de rejouer un mois sans refaire les fetches.

6. **Pas de publication automatique.** Le pipeline produit sur une branche `edition/YYYY-MM`. Jonathan valide par PR. Aucune commande ne push ni ne merge.

7. **Pas de complexité prématurée.** Si une règle métier n'est pas claire, mets un `TODO:` explicite et continue. On raffine en itération, pas en devinant.

## Livrable — 3 étapes séquentielles

### Étape A — Spécification d'architecture

**Avant de coder, produis `context-prep/orchestrator/ARCHITECTURE.md`** qui détaille :

#### A.1 — Flow d'une édition mensuelle

Diagramme textuel (pas de Mermaid) du flow complet :

```
CLI: python pipelines/monthly_run.py --month 2026-02
  │
  ├─ 1. FETCH
  │   ├─ eurostat.fetch_production(month) → data/cache/YYYY-MM/production.json
  │   ├─ eurostat.fetch_prices(month)     → data/cache/YYYY-MM/prices.json
  │   ├─ eurostat.fetch_turnover(month)   → data/cache/YYYY-MM/turnover.json
  │   ├─ eurostat.fetch_gdp(month)        → data/cache/YYYY-MM/gdp.json
  │   └─ comext.read_parquet(month)       → data/cache/YYYY-MM/trade.json (stub if no Yaghi)
  │
  ├─ 2. PROCESS
  │   └─ analysis.build_fiches(cache)     → data/processed/YYYY-MM/fiches/*.json
  │      (one fiche per section, format aligned with system.md §10)
  │
  ├─ 3. DRAFT
  │   ├─ editorial.draft_section(fiche) × N → editorial/drafts/YYYY-MM/sections/*.md
  │   ├─ editorial.draft_summary(sections)  → editorial/drafts/YYYY-MM/summary.md
  │   └─ editorial.consolidate(sections)    → editorial/drafts/YYYY-MM/edition.md
  │
  ├─ 4. VISUALIZE
  │   └─ charts.render(fiches)            → site/src/charts/YYYY-MM/*.svg
  │
  ├─ 5. BUILD
  │   ├─ site.prepare_content(edition)    → site/src/content/editions/YYYY-MM.mdx
  │   └─ [manual step documented] `cd site && npm run build`
  │
  └─ 6. COMMIT
      └─ git.commit_edition(month)        → branch edition/YYYY-MM, no push
```

Pour chaque étape : input exact, output exact, dépendances.

#### A.2 — Modèle de données

Pour chaque artefact produit, donne son schéma :

- **Fiche d'indicateur** (`data/processed/YYYY-MM/fiches/*.json`) — aligné sur `system.md` §10 et `SOURCES.md` §7. Réconcilie définitivement les deux si ce n'est déjà fait.
- **Section rédigée** (`editorial/drafts/YYYY-MM/sections/*.md`) — frontmatter YAML (section_type, order, chart_ids) + corps markdown.
- **Résumé exécutif** (`summary.md`) — 4 bullets (per `SYNTHESIS.md` Pattern 12) + titre-diagnostic. Produit après les 4 sections, en prenant les sections comme input au LLM.
- **Édition consolidée** (`edition.md`) — assemblage summary + 4 sections dans l'ordre éditorial canonique : Output → Prices → Turnover → Trade.
- **Manifest de mois** (`editions/YYYY-MM/manifest.json`) — métadonnées : périodes de données, sources, chart IDs, hash des prompts LLM utilisés.

#### A.3 — Arborescence finale du projet

Adaptée depuis le scaffold préparé plus tôt + les réalités de `SOURCES.md`. Précise quels fichiers sont versionnés Git vs gitignored.

#### A.4 — Points de décision ouverts

Liste ce qui reste à trancher avec Jonathan avant de coder sérieusement :
- Gestion des erreurs : si 1 section échoue sur 4, on publie partiellement ou on abandonne l'édition ?
- Format des charts : SVG statique pour v1 (print-ready, accessible), interactif ECharts en v1.1 ?
- Où vit le manifest des éditions publiées (pour ne pas en re-générer une déjà faite) ?
- Quel modèle LLM ? Sonnet (rapide, moins cher) ou Opus (plus précis) pour la rédaction ? Recommandation argumentée.

**STOP après A. Présente-moi `ARCHITECTURE.md` et attends ma validation avant de coder.**

### Étape B — Prototype fonctionnel (après validation de A)

Implémente le pipeline complet en **mode scaffold fonctionnel** : chaque étape existe, fait son travail minimal, mais certaines parties peuvent être des stubs documentés.

Priorité d'implémentation :

1. **`data/fetchers/eurostat.py` — fonctionnel réel.** Les 4 APIs marchent déjà (SOURCES.md). Ce module tire les données, les normalise, les sauve en JSON structuré. Doit gérer les erreurs réseau avec retry simple.

2. **`data/fetchers/comext.py` — stub documenté.** Une fonction `read_parquet(month)` qui cherche les Parquet à `COMEXT_DATA_PATH` (env var) ; si introuvable, renvoie une fiche "trade_unavailable" clairement marquée. Aucun code de fallback inventé — si pas de Comext, pas de section trade.

3. **`analysis/indicators.py` — fonctionnel.** Prend les caches JSON, calcule YoY, pre-crisis deltas, YTD avg, benchmarks sectoriels. Produit les fiches d'indicateur au format `system.md` §10.

4. **`editorial/draft.py` — fonctionnel avec API Anthropic.** Fonction `draft_section(fiche, system_prompt) -> str`. Charge `system.md` patché comme system, envoie la fiche en user, retourne le markdown. Model: `claude-sonnet-4-5` (ou disponible). Température 0.3. Log intégral dans `llm_log.jsonl`.

5. **`editorial/summary.py` — fonctionnel.** Prend les 4 sections rédigées, les passe au LLM avec un system prompt dédié (à créer : `context-prep/editorial/summary_prompt.md`) qui impose l'arc en 4 bullets du Pattern 12. Produit `summary.md`.

6. **`charts/render.py` — stub initial.** Une fonction qui génère un SVG minimal par chart_id référencé dans les fiches. Utilise `matplotlib` avec sortie SVG, design épuré (à raffiner en Livrable 5 avec le template UX). Pour v1 : axes simples, titre, source line en pied de chart. Pas interactif.

7. **`pipelines/monthly_run.py` — fonctionnel.** CLI avec `click`. Flags : `--month YYYY-MM` (requis), `--dry-run` (tout sauf commit), `--only STEP` (fetch|process|draft|visualize|build|commit), `--force` (écrase cache existant). Logs structurés (JSON lines vers stderr). Exit codes propres (0 succès, 1 erreur, 2 data incomplète).

8. **`site/` — initialisation Astro minimale.** `npm create astro@latest -- --template minimal`. Page d'accueil avec liste des éditions, page par édition qui lit la MDX générée. Pas de design raffiné (Livrable 5).

9. **`scripts/commit_edition.py` — fonctionnel basique.** Crée branche `edition/YYYY-MM`, ajoute les fichiers produits, commit avec message templaté. **Jamais de push**.

Pour chacun des 9 modules, produis : le fichier, un test smoke (`tests/test_<module>.py`) qui vérifie que la fonction principale se charge et s'exécute sur des inputs minimaux, et une docstring en tête du fichier qui explique son contrat.

### Étape C — Validation end-to-end sur février 2026

Une fois B complet, lance la commande :

```
python pipelines/monthly_run.py --month 2026-02 --dry-run
```

Objectif : produire une édition de février 2026 complète (summary + 3 sections — pas trade puisque Comext non accessible) sous forme de fichiers sur disque + site Astro buildable.

Livrables à me présenter :

1. Le `edition.md` complet de février 2026
2. Le `manifest.json` du mois
3. La sortie du build Astro (chemin vers `site/dist/` + screenshot si possible)
4. Les logs du run (`run.log` ou équivalent) avec les 6 étapes visibles
5. Un court `RETROSPECTIVE.md` : ce qui a bien marché, ce qui a accroché, les 3 plus grosses dettes techniques à traiter en itération

## Ce que tu ne fais PAS dans ce livrable

- Pas de deploy Azure Static Web Apps (Livrable 5+)
- Pas de config cron (Yaghi requis)
- Pas de raffinement UX du site (Livrable 5 avec template fourni par Jonathan)
- Pas de charts interactifs
- Pas de section Trade (Comext sur Yaghi requis)
- Pas de gestion des révisions Eurostat multi-mois (mentionnée dans system.md, implémentation v1.1)

## Contraintes transversales

- **Commits locaux intermédiaires** après chaque étape A/B/C majeure. Pas de push.
- **Gitignore rigoureux** : `data/cache/**`, `data/processed/**`, `editorial/drafts/**/llm_log.jsonl` (peut contenir des extraits de prompt système), `.env`, `site/node_modules/`, `site/dist/`. Mais versionne `editorial/drafts/**/edition.md` et `manifest.json` — ce sont les artefacts éditoriaux finaux.
- **Zéro clé API en dur.** Tout via `.env` chargé par `python-dotenv`. Vérifie que `.env` est bien dans `.gitignore` avant premier commit.
- **Conserve `context-prep/` intact.** Ce dossier temporaire sera réconcilié avec la structure finale quand on bootstrappera Iris proprement sur Yaghi. Pour l'instant, le prototype vit **à côté**, pas **à la place**.
- **Si une étape demande plus de 45 min de debug, stoppe et rapporte.** Mieux vaut un pipeline partiel documenté qu'un pipeline complet mais bancal.

## Checkpoints

Présente-moi dans cet ordre :

1. **Fin de A** : `ARCHITECTURE.md` — je valide
2. **Mi-B** : après implémentation des fetchers + analysis (modules 1-3), rapport court
3. **Fin de B** : tous les modules + tests, rapport court
4. **Fin de C** : édition février 2026 complète + site buildé + rétrospective

Entre chaque checkpoint, attends mon feu vert. Pas d'exception.

Go.
