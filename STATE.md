# STATE.md — Point d'arrêt Iris (milestone L5 + base-effect guard)

## 1. État du projet

- **Date de clôture :** 2026-04-21, fin de journée (patch base-effect)
- **Iris** est un pipeline automatisé qui produit un rapport mensuel sur l'industrie chimique européenne pour Cefic. Il extrait des données Eurostat (+ Comext en prod), calcule des indicateurs (YoY, pre-crisis, benchmarks), détecte les effets de base et anomalies commerciales via `analysis/anomaly_detector.py`, génère les sections éditoriales via l'API Anthropic avec un system prompt calibré sur le registre Cefic, et publie le tout sur un site Astro statique. Déploiement cible : Yaghi (Linux), cron mensuel, Azure Static Web Apps.
- **Phase actuelle :** **Livrable 5 (macro brief) + patch base-effect terminés.** L'édition 2026-02-v1 est conservée en l'état (snapshot d'origine, sans caveat — dette documentée). L'édition 2026-02-v2 (dans `editorial/drafts/2026-02-v2/`) démontre le nouveau pipeline : flags D1+D2+D3+D4+D5 levés, severity=critical, paragraphe base-effect produit automatiquement, titre trade_exports porte l'incise em-dash §1.13. Prête pour validation Jonathan.

## 2. Carte complète des livrables

| Livrable | Artefacts clés | Emplacement | Statut |
|---|---|---|---|
| L1 Discovery | `DISCOVERY.md` | racine | ⚠️ biaisé PC-Windows, à réconcilier sur Yaghi |
| L1 Corpus + Synthesis | 6 publications annotées, `SYNTHESIS.md` (18 patterns) | `context-prep/corpus/` | ✅ validé |
| L2 System prompt | `system.md` v2 | `context-prep/editorial/` | ✅ 7+5+3 patches appliqués |
| L3 Stress-test | `test-inputs/`, `test-outputs/`, `SUMMARY.md`, `ITERATION_DIFF.md` | `context-prep/editorial/` | ✅ 6/7 dérives corrigées |
| Sources | `SOURCES.md` | `context-prep/data-sources/` | ✅ 4 APIs Eurostat OK |
| L4-A Architecture | `ARCHITECTURE.md` | `context-prep/orchestrator/` | ✅ validé + 5 patches |
| L4-B Modules 1-3 | `eurostat.py`, `comext.py`, `indicators.py` + tests | `data/fetchers/`, `analysis/`, `tests/` | ✅ tests passent |
| L4-B Modules 4-5 | `draft.py`, `summary.py`, `summary_prompt.md` | `editorial_engine/` | ✅ fonctionnels |
| L4-B Module 6 | `style.py`, `render.py`, 3 templates (`index_timeseries`, `yoy_bars`, `sector_comparison`) | `charts/` | ✅ fonctionnel (1 bug connu, cf §4) |
| L4-B Module 7 | `monthly_run.py` CLI click | `pipelines/` | ✅ fonctionnel, exit codes 0/1/2 |
| L4-B Module 8 | Scaffold Astro minimal | `site/` | ✅ structure en place, UX à enrichir |
| L4-B Module 9 | `commit_edition.py` | `scripts/` | ⚠️ écrit, jamais exécuté avec succès (pas de repo git dans Iris, cf §6) |
| L4-C Run dry-run | `edition.md`, `manifest.json`, `summary.md`, 3 sections, 4 charts SVG, MDX, `RETROSPECTIVE.md` | `editorial/drafts/2026-02/` | ✅ première édition produite |

## 3. Fichiers critiques — pointeurs

| Fichier | Chemin | Quand le relire |
|---|---|---|
| System prompt v2 | `context-prep/editorial/system.md` | À charger à chaque appel LLM de rédaction (consommé par `editorial_engine/draft.py`) |
| SYNTHESIS.md | `context-prep/corpus/SYNTHESIS.md` | Référence pour tout arbitrage éditorial, patch du system prompt |
| SOURCES.md | `context-prep/data-sources/SOURCES.md` | Contrat APIs, schéma data block, unit=I21, s_adj, latences |
| ARCHITECTURE.md | `context-prep/orchestrator/ARCHITECTURE.md` | Spec orchestrateur v1 patchée |
| Style guide Cefic | `cefic_economic_outlook_style_guide.md` | 68 Ko, source primaire pour arbitrage ton / registre |
| Feedback Jonathan | `p01.txt` | Réponses aux 3 questions éditoriales (charts, heading, phrases courtes) |
| Édition février 2026 (v1, snapshot) | `editorial/drafts/2026-02/edition.md` | Référence historique — publiée **sans caveat base-effect** (incident à ne pas reproduire) |
| Édition février 2026 (v2, post-patch) | `editorial/drafts/2026-02-v2/edition.md` | Référence qualité post-anomaly guard — à comparer avec v1 pour validation |
| Trace investigation 2026-02 | `context-prep/investigation/2026-02-trace.md` | Analyse factuelle du bug, cause racine (front-loading pré-tarifs US Q1 2025) |
| RETROSPECTIVE dry-run | `editorial/drafts/2026-02/RETROSPECTIVE.md` | Liste des 3 dettes techniques et des accrocs du run L4 |
| Manifest édition | `editorial/drafts/2026-02/manifest.json` | Hashes prompts, périodes data, modèles LLM — traçabilité |
| Fetchers Eurostat | `data/fetchers/eurostat.py` | Module stable, ne pas toucher sans raison |
| Fetcher Comext | `data/fetchers/comext.py` | Stable + émet `monthly_history` (36 mois) depuis 2026-04-21 |
| Indicateurs | `analysis/indicators.py` | Stable, inclut `enrich_with_anomalies()` |
| **Anomaly detector** | `analysis/anomaly_detector.py` | Module pur, 5 détecteurs D1-D5, AnomalyReport dataclass. Tests : `tests/test_anomaly_detector.py` (15 tests) |
| Draft LLM | `editorial_engine/draft.py` | Module stable — note : chemin réel `editorial_engine/`, pas `editorial/` |
| Summary LLM | `editorial_engine/summary.py` | Module stable, fallback Opus non encore déclenché |
| Macro brief LLM | `editorial_engine/macro_brief.py` | Stable, word budget étendu 80-150 quand `anomaly_active=True` |
| Pipeline CLI | `pipelines/monthly_run.py` | Point d'entrée : `--month`, `--dry-run`, `--only`, `--force`, `--variant` |
| Commit helper | `scripts/commit_edition.py` | ⚠️ dépend d'un repo git dans Iris (inexistant aujourd'hui) |

## 4. Dettes techniques identifiées

Depuis `editorial/drafts/2026-02/RETROSPECTIVE.md` :

1. **Renderer charts ne lit pas la série temporelle complète.**
   - **Impact :** moyen. Un chart (`turnover_index`) a avorté avec "Not enough timeseries points". Les charts output + prices ont fonctionné.
   - **Solution :** passer `cache_dir` au renderer en plus du `fiches_dir`, ou enrichir la fiche avec la série complète issue de `data/cache/YYYY-MM/production.json`.
   - **Effort :** ~1h (choisir option, patcher `charts/render.py`, retester).

2. **Section sales sous-exploite les données single-month.**
   - **Impact :** moyen. Quand `ytd: null` (janvier = 1 seul mois), le LLM tombe sur un cas non-templated et ranking par index absolu au lieu du YoY.
   - **Solution :** ajouter dans `context-prep/editorial/system.md` une règle "for single-month data (January), lead with YoY comparison against January of the previous year".
   - **Effort :** ~30min (patch prompt + retest section sales).

3. **Pas de test d'intégration automatisé.**
   - **Impact :** moyen à élevé (bloque la CI future). Les unit tests passent mais aucun test ne vérifie qu'une run end-to-end produit `edition.md` + manifest + sections attendues.
   - **Solution :** `tests/test_pipeline_integration.py` avec mock des API calls (Anthropic + Eurostat) et vérification du manifest.
   - **Effort :** ~2-3h.

**Dettes complémentaires détectées hors RETROSPECTIVE :**

4. **`scripts/commit_edition.py` ne peut pas fonctionner sans repo git dans Iris.** Le script tourne git depuis `project_root` et, en l'absence d'un `.git` local, remonte jusqu'au repo home de Jonathan (vide, sans commits → `git checkout -b` échoue). Bloquant pour l'automatisation Yaghi si on ne règle pas d'abord la section 5.0 ci-dessous.

5. **Bug I15→I21 de nouveau à surveiller** après migration Yaghi : vérifier que `fetchers/eurostat.py` utilise bien `unit=I21` sur tous les datasets STS récents.

6. ~~**Base-effect / anomaly detection absent du pipeline.**~~ **Résolu le 2026-04-21** (post-incident édition 2026-02). Module `analysis/anomaly_detector.py` ajouté avec 5 détecteurs (D1 Comext/IPI divergence, D2 value/volume divergence, D3 Z-score sur base N-1, D4 concentration top-2 partenaires, D5 comparaison N-2). Enrichissement automatique des fiches par `enrich_with_anomalies()` dans `analysis/indicators.py`. Patches `system.md` §1.13 (anomaly disclosure MUST), §1.14 (temporal scope consistency), §5.9 (base-effect template), pattern SYNTHESIS #22. Édition 2026-02-v1 conservée en l'état (snapshot d'origine), 2026-02-v2 régénérée dans `editorial/drafts/2026-02-v2/` avec paragraphe base-effect automatique + incise em-dash dans le titre trade_exports. Trace d'investigation dans `context-prep/investigation/2026-02-trace.md`. Pipeline regen : `python pipelines/monthly_run.py --month YYYY-MM --variant vN --force`.

## 5. Ce qui reste à faire (roadmap)

### 5.0 — PRIORITÉ 1 : git init + premier commit structuré du repo Iris

**Session dédiée, pas à la va-vite.** Le projet n'a pas de repo git local (le `.git` actuel est le home de Jonathan, vide et sans commits). À faire dans une session courte et cadrée, avant tout autre chantier de demain :

- Choisir et valider le `.gitignore` final (le `.gitignore` actuel à la racine est un bon point de départ, à vérifier).
- `git init` dans `Iris/`.
- Premier commit structuré (éventuellement plusieurs commits atomiques : scaffolding → modules → edition 2026-02).
- Vérifier que `.env` n'est PAS committé (déjà dans `.gitignore` ✅).
- Décider du remote : `kendrick7410/iris` existe sur GitHub, le lier ou non.
- Une fois le repo sain, rejouer `scripts/commit_edition.py` sur l'édition 2026-02 pour créer la branche `edition/2026-02` proprement.

### 5.1 — Review éditoriale humaine de `edition.md` par Jonathan

C'est le vrai test qualitatif, pas un auto-check. Si verdict "v1 publiable", on avance. Si dérives notables, itération `system.md` v3.

### 5.2 — Migration sur Yaghi

Quand le serveur est dispo : discovery Yaghi, adaptation des chemins, test pipeline complet sur Linux, configuration cron mardi 09:00.

### 5.3 — Activation section trade

Sur Yaghi via Parquet Comext — test du stub `comext.py` en réel.

### 5.4 — Template UX du site (Livrable 5)

Le template visuel du site Astro doit **hériter de la charte graphique du repo GitHub `docs-cefic`** (couleurs, typographies, logos). Avant de toucher aux composants Astro :

1. Vérifier l'accessibilité du repo `docs-cefic` (public / privé, droits d'accès Jonathan).
2. Cloner ou lire `docs-cefic` et en extraire la charte (variables CSS, tokens, assets logos, polices).
3. Reporter ces éléments dans `site/` (thème Astro, `public/`, layouts).
4. Ensuite seulement enrichir les composants.

### 5.5 — Traitement des 3 dettes techniques

Cf §4 (charts renderer, règle single-month, test intégration).

### 5.6 — Premier vrai déploiement Azure Static Web Apps

### 5.7 — Production de l'édition mars 2026

Pour valider la reproductibilité et la cohérence éditoriale entre éditions.

## 6. Bloqueurs et questions ouvertes

- **Git remote :** non configuré. `git remote -v` dans `C:/Users/jme` = vide. Le repo `kendrick7410/iris` existe sur GitHub mais n'est lié à rien localement.
- **Repo git Iris :** n'existe pas. Le `.git` le plus proche est `C:/Users/jme/.git` (home de Jonathan, zéro commit, zéro branche, zéro pollution ✅). `commit_edition.py` a donc échoué silencieusement — pas de dégât, mais à régler en 5.0.
- **Yaghi :** pas disponible aujourd'hui. Migration reportée.
- **Comext :** pas testé en réel sur ce PC. Stub actif dans `comext.py`, sections trade skippées dans l'édition février (`data_unavailable`).
- **Clé API Anthropic :** présente dans `.env` ✅. Confirmé : `.env` est bien dans `.gitignore` (ligne 2). Zéro risque de fuite au prochain commit.
- **Template UX site :** pas fourni par Jonathan.
- **Test d'intégration :** absent (dette §4.3).
- **Accroc chart `turnover_index`** dans l'édition février : à corriger (dette §4.1).

## 7. Commandes utiles pour reprendre

```bash
# Depuis la racine du projet Iris :
cd "C:\Users\jme\OneDrive - Cefic\Documents\-= Cefic =-\Iris"

# Restaurer le contexte :
cat STATE.md
cat context-prep/orchestrator/ARCHITECTURE.md
cat editorial/drafts/2026-02/edition.md
cat editorial/drafts/2026-02/RETROSPECTIVE.md

# Vérifier que rien n'est cassé :
python -m tests.test_comext
python -m tests.test_indicators
python -m tests.test_eurostat    # ~30s, appels API live

# Relancer une édition dry-run si besoin :
python pipelines/monthly_run.py --month 2026-02 --dry-run --force

# Construire le site :
cd site && npm install && npm run build
```

## 8. Environnement actuel

- **OS :** Windows 11 Enterprise, pas de droits admin
- **Python :** 3.9.13 (Microsoft Store)
- **Node.js :** 20.17.0, npm 11.8.0
- **Chemin projet :** `C:\Users\jme\OneDrive - Cefic\Documents\-= Cefic =-\Iris`
- **⚠️ OneDrive sync actif** — vérifier conflits de fichiers au matin
- **Packages Python :** anthropic, httpx, pdfplumber, PyMuPDF, matplotlib, pandas, dotenv, click (tous installés)
- **`gh` CLI :** non installé (pas de droits admin). Git ligne de commande uniquement.
- **Proxy SSL Cefic :** nécessite `httpx.Client(verify=False)` pour l'API Anthropic.
- **Cible future :** Yaghi (Linux), migration à venir.

## For the next session

> Hi. You are resuming work on Iris, a monthly automated report on the European chemical industry for Cefic. Jonathan Mead is the lead. The project is at a **milestone** — Livrable 4 complete, first dry-run edition produced (February 2026). Before doing anything:
>
> 1. Read this `STATE.md` fully
> 2. Read `editorial/drafts/2026-02/edition.md` — this is the output to assess and build upon
> 3. Read `editorial/drafts/2026-02/RETROSPECTIVE.md` — debts to address
> 4. Run the 3 smoke tests — they must pass (`test_comext`, `test_indicators`, `test_eurostat`)
> 5. Ask Jonathan what he wants to do next. The default priority is **§5.0 — git init + structured first commit of the Iris repo**, because it's blocking `scripts/commit_edition.py` and Yaghi migration. Other candidates :
>    - Editorial review of `edition.md` (his judgment is the real quality gate)
>    - Migrate to Yaghi
>    - Work on UX template for the Astro site
>    - Address specific technical debts (§4.1 charts, §4.2 single-month rule, §4.3 integration test)
>    - Produce a second edition (March 2026) to test reproducibility
>
> **Do NOT re-explore the codebase blindly. Do NOT rewrite existing modules. Do NOT re-discover what `SOURCES.md` or `ARCHITECTURE.md` already cover.** Trust the previous work unless Jonathan flags a specific issue.
>
> **Respect checkpoints.** Previous session burned through A/B/C validation points without stopping. This must not repeat on sensitive operations (Yaghi migration, deployment, edition publication, git init of the Iris repo).
>
> **Key technical gotchas:**
> - Eurostat STS datasets require `unit=I21` (not I15) for recent data.
> - Anthropic API requires `httpx.Client(verify=False)` on Cefic network (SSL proxy).
> - Turnover data (`sts_intv_m`) lags production by ~1 month — the fiche handles this via `period.note`.
> - The system prompt is at `context-prep/editorial/system.md`, NOT at `editorial/system.md`.
> - The LLM-facing modules live in `editorial_engine/`, while `editorial/drafts/` holds produced outputs — don't confuse the two.
> - `scripts/commit_edition.py` will fail until §5.0 is resolved (no git repo in the Iris directory today).
