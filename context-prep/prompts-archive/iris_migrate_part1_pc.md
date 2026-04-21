# Prompt migration — Partie 1/2 : Préparation sur le PC

> À coller dans Claude Code **sur ton PC Windows**.
> Objectif : nettoyer le projet local, initialiser le repo Git proprement, pusher sur GitHub. Ensuite on bascule sur Yaghi.

---

On prépare la migration d'Iris vers Yaghi. Le pont sera Git : push depuis ce PC, clone sur Yaghi. Rien de fancy.

**Important : tu ne migres rien cette fois. Tu prépares uniquement la source que Yaghi clonera.** La partie 2 se fera depuis Yaghi directement.

## Étape 1 — Audit de l'état actuel

Avant tout, fais un audit complet et **présente-moi le rapport avant d'agir**. Je valide, puis tu nettoies.

### 1.1 État Git

```bash
cd "/c/Users/jme/OneDrive - Cefic/Documents/-= Cefic =-/Iris"
git rev-parse --show-toplevel
git status --short | head -50
git log --oneline -10 2>&1 || echo "No commits yet"
git remote -v
```

Rappel : la dernière vérification avait montré que le projet Iris n'était **pas** un vrai repo (le git parent renvoyait le home dir `C:/Users/jme`). Confirme si c'est toujours le cas. Si c'est le cas, le projet n'a encore jamais été committé correctement.

### 1.2 Inventaire des fichiers à transférer

```bash
# Volume total du projet
du -sh .

# Ce qui est volumineux (plus de 1 MB)
find . -type f -size +1M 2>/dev/null | head -20

# Ce qui est suspect (cache, logs, node_modules, __pycache__)
find . -type d -name "__pycache__" -o -name "node_modules" -o -name ".venv" -o -name "dist" 2>/dev/null
```

### 1.3 Fichiers sensibles

```bash
# Y a-t-il un .env ?
ls -la .env 2>/dev/null && echo "⚠️ .env present — DO NOT commit"

# Est-il dans .gitignore ?
grep -E "^\.env$|^\*\.env$" .gitignore 2>/dev/null && echo "OK" || echo "⚠️ Add .env to .gitignore"

# Y a-t-il d'autres secrets qui traînent ?
grep -rE "sk-ant-|api[_-]?key|secret" --include="*.py" --include="*.md" --include="*.json" . 2>/dev/null | grep -v ".gitignore" | head -10
```

### 1.4 Présente-moi le rapport

Un bloc résumé qui me dit :
- Est-ce un vrai repo Git ou non
- S'il y a des commits existants (bizarres ou légitimes)
- Volume total du projet + plus gros contributeurs
- Fichiers suspects à gitignore
- Secrets détectés s'il y en a

**STOP. Attends ma validation avant Étape 2.**

## Étape 2 — Nettoyage et .gitignore robuste

Après mon feu vert, produire un `.gitignore` solide à la racine. Voici le squelette à compléter selon ce que ton audit aura révélé :

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
env/
*.egg-info/
.pytest_cache/

# Environment
.env
.env.local
*.env

# OS / Editor
.DS_Store
Thumbs.db
.vscode/
.idea/

# OneDrive noise
*.lnk
desktop.ini

# Data artifacts (rebuilt by pipeline)
data/cache/
data/processed/
editorial/drafts/*/llm_log.jsonl

# Node / Astro
site/node_modules/
site/dist/
site/.astro/

# Logs
*.log
logs/

# Context-prep (transient work, versioned selectively)
# Keep: SYNTHESIS.md, system.md, SOURCES.md, ARCHITECTURE.md
# Ignore: test-inputs/, test-outputs/, corpus/ (raw fetched content)
context-prep/corpus/
context-prep/editorial/test-inputs/
context-prep/editorial/test-outputs/
```

Ajuste selon ce que l'audit révèle.

**Point important** : `editorial/drafts/2026-02/edition.md` et `manifest.json` **doivent être versionnés** (ce sont les livrables éditoriaux). Seuls les `llm_log.jsonl` sont exclus (ils contiennent le prompt system complet et sont volumineux).

## Étape 3 — git init propre et premier commit

```bash
# Si le projet n'est pas un repo Git ou a un historique cassé
rm -rf .git  # UNIQUEMENT si l'audit a confirmé qu'il n'y a rien à préserver
git init
git branch -M main

# Vérifier que rien de sensible n'est tracké
git add --dry-run . | grep -iE "\.env$|secret|key" && echo "⚠️ STOP" || echo "OK"

# Premier commit structuré
git add .gitignore
git commit -m "chore: initial gitignore"

git add README.md STATE.md
git commit -m "docs: project state at L4 milestone"

git add context-prep/editorial/SYNTHESIS.md context-prep/editorial/system.md
git add context-prep/data-sources/SOURCES.md
git add context-prep/orchestrator/ARCHITECTURE.md
git commit -m "docs: editorial and architecture references"

git add data/ analysis/ editorial/ charts/ pipelines/ scripts/ tests/ requirements.txt
git commit -m "feat: Iris orchestrator v1 — 9 modules, all tests passing"

git add editorial/drafts/2026-02/edition.md editorial/drafts/2026-02/manifest.json editorial/drafts/2026-02/RETROSPECTIVE.md
git add editorial/drafts/2026-02/sections/ editorial/drafts/2026-02/summary.md
git commit -m "feat: first dry-run edition — February 2026"

git add site/
git commit -m "feat: Astro site scaffold"
```

Adapte les chemins et fichiers selon la réalité du projet. L'idée : **une série de commits thématiques lisibles**, pas un seul commit monstre "initial commit everything".

## Étape 4 — Remote et push

```bash
git remote add origin https://github.com/kendrick7410/iris.git
git push -u origin main
```

Si l'auth HTTPS échoue sans `gh` CLI, note-le et propose à Jonathan d'utiliser un Personal Access Token ou de passer en SSH. **Ne l'aide pas à saisir son PAT ici — il le fera manuellement dans son terminal.**

## Étape 5 — Livrable final

Présente-moi :

1. Le log des commits (`git log --oneline`)
2. La taille du repo poussé (`git count-objects -vH`)
3. L'URL GitHub du repo avec le commit récent
4. Un `MIGRATION_CHECKLIST.md` à la racine qui liste, pour la suite sur Yaghi :
   - Version Python requise (3.9+)
   - Commande de clone Git
   - Création du venv
   - Installation des dépendances
   - Création du `.env` avec les 2 variables requises : `ANTHROPIC_API_KEY`, `COMEXT_DATA_PATH`
   - Commandes de vérification (3 smoke tests, un dry-run sur 2026-02)
   - Point d'attention : le stub Comext deviendra actif dès que `COMEXT_DATA_PATH` pointe vers un dossier avec les Parquet → première édition Yaghi pourra inclure la section trade

**Ne push PAS automatiquement.** Présente d'abord les commits locaux et le `MIGRATION_CHECKLIST.md`, puis Jonathan valide le push manuellement ou te donne le feu vert.
