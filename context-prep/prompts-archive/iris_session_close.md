# Prompt de clôture de session — Iris

> À coller maintenant. On s'arrête proprement et on reprend demain (VS Code local ou Yaghi).

---

Stop sur l'Étape B. Les modules 1-3 sont validés et testés — c'est un bon point d'arrêt. On reprend demain.

Ton objectif maintenant : **faire en sorte que tu puisses reprendre à froid demain sans rien réexplorer.** Tout ton contexte actuel vit dans cette session et va disparaître. Sérialise-le sur disque.

## Livrable unique — `STATE.md` à la racine du projet

Un document qui permet à n'importe quelle future session de reprendre exactement là où on s'arrête. Structure :

### 1. État du projet

- Date et heure de clôture de session
- Résumé en 3 phrases de ce qu'est Iris (pour une session qui arrive totalement à froid)
- Phase actuelle du projet (Livrable 4, Étape B, checkpoint 1 validé)

### 2. Carte des livrables

Tableau chronologique de ce qui a été produit, où c'est, et son statut :

| Livrable | Artefacts | Emplacement | Statut |
|---|---|---|---|
| L1 Discovery | DISCOVERY.md | racine | ⚠️ biaisé PC-Windows, à réconcilier sur Yaghi |
| L2 Corpus + Synthesis | SYNTHESIS.md | context-prep/corpus/ | ✅ validé, 18 patterns |
| L2 System prompt | system.md | context-prep/editorial/ | ✅ v2 patché, 7+5 patches appliqués |
| L3 Stress-test | test-inputs/, test-outputs/, SUMMARY.md | context-prep/editorial/ | ✅ v1→v2, 6/7 dérives corrigées |
| Sources | SOURCES.md | context-prep/data-sources/ | ✅ validé, 4 APIs Eurostat OK |
| L4 Architecture | ARCHITECTURE.md | context-prep/orchestrator/ | ✅ validé + 5 patches appliqués |
| L4 Étape B modules 1-3 | eurostat.py, comext.py, indicators.py + tests | data/, analysis/, tests/ | ✅ fonctionnels, tests passent |

### 3. Fichiers critiques — pointeurs

Pour chaque document de référence, chemin exact + ce qu'il contient + quand le relire :

- `context-prep/editorial/system.md` — system prompt v2, à charger à chaque appel LLM de rédaction
- `context-prep/editorial/SYNTHESIS.md` — 18 patterns de voix Cefic, référence pour patcher le system prompt
- `context-prep/data-sources/SOURCES.md` — contrat des APIs + schéma du data block
- `context-prep/orchestrator/ARCHITECTURE.md` — spec de l'orchestrateur v1 patchée
- `DISCOVERY.md` — à relire pour reconstruire le contexte environnement, mais biaisé PC (redo sur Yaghi)

### 4. Ce qui reste à faire pour finir le Livrable 4

Liste numérotée, précise, reproductible :

1. Module 4 : `editorial/draft.py` — fonctionnel avec API Anthropic, charge `system.md`, logge dans `llm_log.jsonl`
2. Module 5 : `editorial/summary.py` — fonctionnel avec fallback Opus (critères dans ARCHITECTURE.md §X)
3. Module 6 : `charts/render.py` + `charts/style.py` + 3 templates
4. Module 7 : `pipelines/monthly_run.py` — CLI click, 6 étapes, flags `--month --dry-run --only --force`
5. Module 8 : `site/` — scaffold Astro minimal (`npm create astro@latest -- --template minimal`)
6. Module 9 : `scripts/commit_edition.py`
7. Checkpoint 2 : rapport après modules 4-9
8. Étape C : run end-to-end sur 2026-02, livrer RETROSPECTIVE.md

### 5. Bloqueurs et questions ouvertes

- Clé API Anthropic : présente dans `.env` ? (si oui, confirmer)
- Comext : pas d'accès depuis ce PC, Iris skippera la section trade → testé et documenté
- Yaghi : pas disponible aujourd'hui, migration du projet reportée
- Template UX du site : à fournir par Jonathan, reporté en Livrable 5
- Git remote `kendrick7410/iris` : configuré ? (vérifie `git remote -v`)

### 6. Commandes utiles pour reprendre

```bash
# Depuis la racine du projet Iris, pour reprendre le contexte :
cat STATE.md
cat context-prep/orchestrator/ARCHITECTURE.md
cat context-prep/editorial/system.md
ls -la data/ analysis/ tests/

# Pour relancer les tests modules 1-3 (doivent passer):
python -m tests.test_comext
python -m tests.test_indicators
python -m tests.test_eurostat

# Pour reprendre à l'étape B module 4 :
# (une fois STATE.md lu et contexte restauré)
```

### 7. Environnement

- OS actuel : Windows 11, pas de droits admin
- Python : 3.9.13 (Microsoft Store)
- Chemin projet : `C:\Users\jme\OneDrive - Cefic\Documents\-= Cefic =-\Iris`
- ⚠️ OneDrive sync actif — vérifier conflits de fichiers au matin
- Environnement cible futur : Yaghi (Linux), à bootstrapper plus tard avec migration des modules

### 8. Instructions pour la future session

En une section finale intitulée `## For the next session`, écris littéralement ce message destiné à ton futur toi (ou à un autre Claude) :

> Hi. You are resuming work on Iris, a monthly automated report on the European chemical industry for Cefic. Jonathan Mead is the lead. The project is in mid-implementation of Livrable 4 (orchestrator prototype). Modules 1-3 are done and tested. Before doing anything :
>
> 1. Read this STATE.md fully
> 2. Read `context-prep/orchestrator/ARCHITECTURE.md` — it's the spec you must implement
> 3. Read `context-prep/editorial/system.md` — it's the editorial prompt you'll use
> 4. Run the 3 smoke tests to verify nothing is broken from yesterday
> 5. Ask Jonathan if he wants to continue on this PC or migrate to Yaghi first
>
> Do NOT re-explore the codebase blindly. Do NOT rewrite existing modules. Do NOT re-discover what SOURCES.md already documents. Trust the previous work unless Jonathan says otherwise.
>
> If Jonathan confirms "continue on PC" : proceed with module 4 (`editorial/draft.py`).
> If Jonathan says "Yaghi is ready" : pause, ask him to set up the git clone + pip install + .env on Yaghi, then resume module 4 there.

## Contraintes

- **Pas de commit final.** Juste la création de `STATE.md`. On commitera demain après avoir vérifié que rien n'est cassé.
- **Pas de modif d'autres fichiers.** Uniquement `STATE.md`.
- **Pas d'optimisation de dernière minute.** Arrête proprement même si tu vois un truc à améliorer.
- **Vérifie que `.env` est bien dans `.gitignore`** avant de clore. Pas de clé API qui traîne.

Présente-moi `STATE.md` quand c'est prêt. Ensuite je ferme VS Code tranquille.
