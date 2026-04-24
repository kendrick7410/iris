---
name: cms-design
description: Architecture du portail d'édition human-in-the-loop (Azure SWA + Entra ID + Sveltia CMS + Azure Function commit proxy)
status: design approuvé, Phase 2 en attente de blockers B1-B5
---

# Iris CMS — Design human-in-the-loop

## Contexte

Iris est aujourd'hui un pipeline LLM 100% automatisé : fetch → analyse → draft → render → build → deploy. Dr Moncef Hadhri (chef économiste Cefic) doit pouvoir revoir chaque édition avant publication et corriger la formulation de phrases sans passer par Jonathan, sans CLI, sans GitHub. Chaque save doit se propager au site live en ~2 min, sans serveur applicatif à maintenir.

**Framing stratégique** : le CMS transforme Iris d'un pipeline automatique en **produit hybride humain-machine**. C'est une validation structurelle qui répond à l'objection *"c'est un LLM qui écrit ça"*. Le site devra à terme mentionner que chaque édition est revue par l'équipe économique Cefic.

## Décisions architecturales

### D1 — Cas B : le CMS édite le MDX site

Source de vérité côté site aujourd'hui = `site/src/content/editions/*.mdx` (seul consommé par Astro via `getCollection('editions')`). Le CMS édite ces fichiers directement. `editorial/drafts/` reste l'output du pipeline LLM, non édité par Moncef.

Migration future (alignment patch, cf. STATE.md §5.8) : si on fait converger site et drafts, il suffira de changer `folder:` dans `config.yml` du CMS.

### D2 — O2 : Azure Function proxy pour commits GitHub

**Contradiction résolue** : Azure SWA authentifie Moncef via Entra ID (SSO Cefic, pas de compte GitHub), mais Sveltia CMS voudrait parler directement à GitHub. Moncef ne doit pas avoir de compte GitHub.

Solution : une Azure Function `/api/cms-commit` qui :
1. Lit l'identité Azure SWA injectée dans `x-ms-client-principal`
2. Vérifie que l'utilisateur est dans l'allowlist
3. Commit sur `kendrick7410/iris` via un **PAT GitHub fine-grained stocké en secret Azure** (jamais dans le repo)
4. **Set l'auteur du commit à l'identité Entra ID réelle** (`Moncef Hadhri <mha@cefic.be>`) — audit Git fidèle

Sveltia pointe sur cet endpoint au lieu de GitHub direct.

### D3 — Pas de dépendance Netlify

Le proxy OAuth `api.netlify.com` que Sveltia utilise par défaut n'est plus nécessaire, puisque l'Azure Function fait tout le travail et vit sur le même domaine (`iris.cefic.org/api/...`, pas de CORS).

### D4 — H2 éditables

Les titres de section (H2) pilotent aussi les titres de vues dashboard via `[id].astro:46-48`. Moncef peut les modifier ; un `hint` dans le CMS rappelle la contrainte éditoriale Cefic (déclaratif, ancré à un chiffre).

## Flow utilisateur

```
Moncef (Cefic)
   │
   ▼  iris.cefic.org/admin (navigateur)
┌─────────────────────────────┐
│  Azure SWA                  │
│  1. staticwebapp.config.json│  → route /admin/* en allowedRoles: [authenticated]
│  2. redirect Entra ID       │  → login SSO Cefic
│  3. cookie session          │
└─────────────────────────────┘
   │
   ▼  /admin/index.html
┌─────────────────────────────┐
│  Sveltia CMS (SPA)          │
│  - charge config.yml        │
│  - liste les éditions via   │
│    backend: proxy → /api/   │
│  - éditeur markdown         │
└─────────────────────────────┘
   │  save → POST /api/cms-commit
   ▼
┌─────────────────────────────┐
│  Azure Function (api/)      │
│  1. verify x-ms-client-     │
│     principal               │
│  2. allowlist check         │
│  3. validate path+payload   │
│  4. rate-limit              │
│  5. Octokit commit to main  │
│     with author = Entra ID  │
│  6. return commit URL       │
└─────────────────────────────┘
   │
   ▼  push sur main
┌─────────────────────────────┐
│  Azure SWA CI/CD            │
│  - rebuild site (~90s)      │
│  - deploy                   │
└─────────────────────────────┘
   │
   ▼  live sur iris.cefic.org
```

## Contrat d'interface `/api/cms-commit`

### Request

```http
POST /api/cms-commit HTTP/1.1
Cookie: StaticWebAppsAuthCookie=...
x-ms-client-principal: <base64 JSON injecté par SWA>
Content-Type: application/json

{
  "path": "site/src/content/editions/2026-02.mdx",
  "content": "<nouveau contenu MDX complet>",
  "message": "edit: reformulate trade_exports heading",
  "metadata": {
    "edition": "2026-02",
    "reviewed": false
  }
}
```

### Response — succès

```json
{
  "status": "ok",
  "commit_url": "https://github.com/kendrick7410/iris/commit/<sha>",
  "sha": "<sha>"
}
```

### Response — erreurs

| Code | Raison |
|------|--------|
| 401 | `x-ms-client-principal` manquant ou invalide |
| 403 | Utilisateur hors allowlist |
| 400 | Payload invalide (JSON schema) ou path hors `site/src/content/editions/` |
| 429 | Rate-limit (1 commit / 10s par email) |
| 502 | Erreur Octokit (problème GitHub API) |
| 500 | Erreur interne |

## Sécurité

- **PAT GitHub fine-grained** scopé `kendrick7410/iris` uniquement, permission `contents: write`. Stocké en `GITHUB_PAT` dans les App Settings Azure (pas Key Vault pour MVP, à upgrader).
- **Allowlist** d'emails en variable d'env `CMS_ALLOWED_EMAILS` (CSV). MVP : `jonathan@..., mha@cefic.be`.
- **Validation server-side stricte** : path DOIT matcher `^site/src/content/editions/\d{4}-\d{2}\.mdx$`. Rien d'autre n'est committable.
- **Rate-limit** : token-bucket en mémoire du Function host, 1 commit / 10s par email.
- **Audit** : chaque commit porte l'identité réelle comme `author` et `committer`. `git log` = log d'édition humaine gratuit.
- **Pas de suppression** : l'endpoint ne supporte que les overwrites de fichiers existants. Pas de DELETE.

## Open design items (à trancher en Phase 3)

### OD1 — Sveltia backend proxy

Sveltia CMS (comme Decap) n'a pas nativement un backend "custom HTTP proxy". Deux voies :

- **Voie A** : notre Azure Function implémente un sous-ensemble du **protocole git-gateway** (celui que Netlify utilise). Sveltia parle alors `backend: git-gateway` pointé sur `/api/`. Documenté, viable, ~4-6h de dev.
- **Voie B** : plugin custom Sveltia qui enregistre un backend maison via `CMS.registerBackend()`. Plus de contrôle, plus de code custom à maintenir.

Voie A privilégiée pour la compatibilité et la pérennité.

### OD2 — Workflow Azure SWA

`.github/workflows/azure-static-web-apps-*.yml` a aujourd'hui `api_location: ""`. À passer à `api_location: "api"` pour que SWA wire les functions. À faire en Phase 2.

### OD3 — Variable `reviewed` dans le frontmatter MDX

L'ajout du flag `reviewed: true/false` dans le frontmatter des MDX demande d'étendre le schéma `site/src/content/config.ts`. Trivial mais à coordonner avec `pipelines/monthly_run.py` qui écrit actuellement un frontmatter minimal.

## Migration path vers Cas A (alignment patch)

Quand l'alignment patch sera appliqué et que la source de vérité site = `editorial/drafts/<month>/edition.md` :

1. Dans `site/public/admin/config.yml`, changer `folder: site/src/content/editions` → `folder: editorial/drafts`
2. Mettre à jour la validation path dans `api/src/lib/validation.ts` : nouveau pattern autorisé
3. Adapter la config collection Sveltia pour le format drafts (édition découpée en `sections/*.md`)
4. Tester avec l'édition courante avant de désactiver le CMS sur les MDX

Coût estimé : 1-2h. Le reste de l'infra (auth, Azure Function, allowlist) est inchangé.

## Références

- STATE.md §9 — état du chantier CMS
- `api/README.md` — doc technique de l'Azure Function
- `site/public/admin/config.yml` — config Sveltia (à créer Phase 4)
- `staticwebapp.config.json` — config auth SWA (à créer Phase 2.1)
