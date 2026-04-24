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

## Open design items

### OD1 — Protocole backend Sveltia/Decap (décision : **Voie A**, cf. ci-dessous)

**Contexte.** Sveltia (comme son parent Decap, ex-Netlify CMS) attend un backend qui parle une API Git. Les backends natifs `github` / `gitlab` utilisent OAuth de l'utilisateur final pour s'authentifier ; `git-gateway` (legacy Netlify) proxie ces appels via un service intermédiaire qui injecte un token partagé. **Notre contrainte** : Moncef n'a pas de compte GitHub, l'auth passe par Azure SWA + Entra ID, et le token doit rester server-side (PAT machine).

Deux voies pour coller le CMS à notre Azure Function.

---

#### Voie A — Proxy type git-gateway (GitHub Contents API subset)

**Idée** : notre Azure Function expose un sous-ensemble de l'API GitHub que Decap/Sveltia appelle. On utilise le backend `github` natif en redirigeant `api_root` vers notre domaine, et on court-circuite le flux OAuth via un hack localStorage dans `admin/index.html`.

**Endpoints à proxifier** (pour le scope édition sans création/suppression/workflow) :

| Méthode | Chemin | Usage CMS |
|---------|--------|-----------|
| `GET` | `/repos/{owner}/{repo}/git/trees/{branch}?recursive=1` | Lister les éditions de la collection |
| `GET` | `/repos/{owner}/{repo}/contents/{path}?ref={branch}` | Ouvrir une édition pour édition |
| `GET` | `/repos/{owner}/{repo}/branches/{branch}` | Vérifier le head du branch |
| `PUT` | `/repos/{owner}/{repo}/contents/{path}` | Sauvegarder (déjà dans `/api/cms-commit`) |

Soit **3 nouveaux endpoints GET** (lecture) + réutilisation du `/api/cms-commit` actuel pour le PUT. Chaque endpoint :
1. Vérifie `x-ms-client-principal` (même chaîne que `cms-commit`)
2. Allowlist + rate-limit
3. Restreint `path` au whitelist (`site/src/content/editions/*.mdx`)
4. Forwarde vers `api.github.com` en injectant le PAT, renvoie la réponse telle quelle

**Contournement OAuth côté CMS** : on inject dans `admin/index.html` un script qui pose le token factice en localStorage avant que Sveltia/Decap démarre. Le CMS pense être authentifié, appelle le backend avec un `Authorization: Bearer <dummy>` — que notre proxy ignore (notre auth = la session SWA).

```html
<!-- admin/index.html, avant le bundle Sveltia -->
<script>
  localStorage.setItem('decap-cms-user', JSON.stringify({
    backendName: 'github',
    token: 'proxy-handles-auth',
    login: 'proxy',
    name: 'proxy',
  }));
</script>
```

Effort estimé : **~4-6 h**. Risques :
- Hack localStorage peut casser si Sveltia change le format de son user state. Mitigation : pinner la version du bundle Sveltia, tests E2E pour détecter régression.
- Chaque nouvelle feature du CMS (preview, media, editorial workflow) ajoute potentiellement des endpoints à proxifier.

---

#### Voie B — Backend custom via `registerBackend`

**Idée** : écrire une classe Backend en JS qui implémente l'interface Decap (`getEntry`, `listEntries`, `persistEntry`, etc.), l'enregistrer via `CMS.registerBackend('iris-proxy', IrisBackend)` dans `admin/index.html`, et configurer `backend: { name: 'iris-proxy' }` dans `config.yml`. Cette classe parle directement à nos endpoints custom (pas besoin de mimer l'API GitHub).

Interface à implémenter :

```js
class IrisBackend {
  authComponent() { /* no-op, SWA auth is upstream */ }
  restoreUser() { return Promise.resolve({ name: 'swa-user' }); }
  async getEntry(collection, slug, path) { /* GET /api/cms-read */ }
  async listEntries(collection) { /* GET /api/cms-list */ }
  async persistEntry(entry, ...) { /* POST /api/cms-commit */ }
}
```

Endpoints Azure Function : 2-3 custom et propres à nous.

Effort estimé : **~8-12 h**. Risques :
- L'interface Backend de Decap est documentée mais peu stable ; Sveltia l'a peut-être modifiée ou restreinte dans son fork Svelte (versus JSX Decap original).
- L'écriture d'un backend custom demande de comprendre le cycle de vie interne du CMS (dirty state, optimistic updates, media handling). Plus de surface à débugger.
- Plus de code frontend propriétaire à maintenir à chaque upgrade Sveltia.

---

#### Décision : **Voie A**

**Raison principale** : périmètre d'implémentation plus petit (3 endpoints proxy + 1 hack localStorage) et s'appuie sur du code Sveltia battle-tested plutôt que sur un plugin fait maison. Le jour où Sveltia ajoute un vrai support SSO, la migration consiste à supprimer le hack localStorage — le reste de l'architecture (Azure Function, allowlist, PAT) reste pertinent.

La Voie B est plus "propre" en théorie mais :
- ~2× plus d'effort
- Dépend plus fortement de l'API interne Sveltia (risque de casse à chaque upgrade)
- N'élimine pas la nécessité d'endpoints côté Function, juste les déguise différemment

**Plan d'implémentation Voie A (Phase 3)** :

1. **Azure Function** : ajouter 3 handlers GET proxy (`github-tree`, `github-content`, `github-branch`) qui réutilisent `auth.ts` + `validation.ts` (path whitelist élargi pour accepter aussi les lectures) et forwardent vers `api.github.com` via Octokit ou fetch direct. ~2 h.
2. **`site/public/admin/index.html`** : bundle Sveltia + script localStorage + redirect init. ~30 min.
3. **`site/public/admin/config.yml`** : collection `editions`, champ `reviewed`, `api_root: https://iris.cefic.org/api/gh` (ou équivalent). ~1 h.
4. **Tests E2E manuels** : ouvrir `/admin`, ouvrir une édition, modifier une phrase, save, vérifier commit GitHub + rebuild Azure. ~1 h.
5. **Documentation GUIDE.md** pour Moncef (Phase 6.3 du plan original).

Total Voie A : ~5 h net après le onboarding IT.

**Fallback** : si le hack localStorage casse à l'usage (Sveltia refuse le user state sans vraie OAuth), pivoter vers Voie B sans refaire l'infra Azure Function — juste remplacer l'hack par une classe Backend.

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

## Décisions de config CMS (Phase 3.3)

### Cas B confirmé, source de vérité = MDX site

Le CMS édite `site/src/content/editions/*.mdx` directement (collection `editions` dans `config.yml`, `folder: site/src/content/editions`). Pas de couche intermédiaire, pas de structure sectionnée — la flat MDX écrite par `pipelines/monthly_run.py` est éditée telle quelle.

Migration future (§5.8) : bascule de `folder:` vers `editorial/drafts/...` une fois l'alignment patch appliqué.

### `publish_mode: simple` (pas d'editorial workflow)

Chaque save Moncef = commit direct sur `main`. Pas de branche de review, pas de PR. Rationale :
- Moncef EST l'autorité éditoriale (senior economist, relecteur humain). Pas besoin d'une étape de validation supplémentaire.
- Un save = une phrase reformulée, périmètre minimal, risque faible.
- Si besoin de PR review plus tard (ex: second économiste Cefic onboarded), bascule `editorial_workflow` triviale dans `config.yml`.

### Pas de `media_folder`

Moncef n'upload pas d'images. Les charts SVG sont générés par `pipelines/monthly_run.py` (`charts/render.py`) et committés sous `site/public/charts/{month}/` par le pipeline, pas par le CMS. Désactiver le media_folder évite qu'il apparaisse dans l'UI et que Moncef tente accidentellement un upload qui irait 404 (le PAT a `contents: write` mais pas de permission large).

### `create: false`, `delete: false`

Moncef ne crée pas d'éditions (c'est le rôle du pipeline mensuel). Il ne supprime pas d'archives. L'UI Sveltia masque ces actions quand `create`/`delete` sont `false`. Deuxième barrière côté Function : `validation.ts` rejette tout path hors `site/src/content/editions/\d{4}-\d{2}\.mdx$` — les créations seraient bloquées server-side aussi.

### Déviation assumée : `body: text` vs `sections: list`

**Spec initiale** : `sections: list of {heading, body, chart_id}` avec chaque heading repris comme titre de vue dashboard.

**Implémenté** : un seul champ `body` en widget `text` qui édite tout le contenu post-frontmatter.

**Raison** : le MDX courant est plat (H2 + `---` + `<img/>` inline), sans structure `sections:` en frontmatter. Livrer la spec sectionnée demande :
1. Réécriture du pipeline pour assembler un tableau `sections[]` dans le frontmatter
2. Réécriture du template Astro `[id].astro` pour lire `entry.data.sections` au lieu de `entry.body`
3. Migration des éditions existantes

Soit ~2-3 jours. Logique avec l'alignment patch (§5.8) : quand on refactor pipeline + template pour lire `editorial/drafts/*/sections/*.md`, on en profite pour passer au format sectionné côté CMS.

**Widget `text` (pas `markdown`)** : protection contre la réécriture automatique de Sveltia qui pourrait massacrer les `<img/>` JSX, reformater les `---` separators ou altérer l'espacement. Moncef voit le MDX brut — moins joli, mais zéro corruption des références aux charts.

**Garde-fous compensatoires** (en attendant le passage sectionné) :
- Hint explicite sur le champ `body` : ne pas toucher aux chiffres, aux `<img/>`, aux `---`
- Côté Function : `validation.ts` cap la taille du payload à 256 KB et refuse tout path hors éditions
- Côté pipeline : `reviewed: true` gèle la régénération → un save Moncef reste intact même si le pipeline tourne

## Tenant ID substitution

Le `AAD_TENANT_ID` (GUID du tenant Cefic Entra ID) n'est **jamais committé** dans le repo. `staticwebapp.config.json` porte le placeholder `$AAD_TENANT_ID` dans le champ `openIdIssuer`, et le workflow GitHub Actions substitue la valeur au moment du build via `envsubst`.

### Pourquoi

Le tenant ID n'est pas un secret (il apparaît dans toutes les URLs OAuth publiques), mais :
- Règle interne Cefic : tout identifiant institutionnel reste hors repo (ceinture + bretelles).
- Template réutilisable : si un second environnement (staging, autre tenant) est monté plus tard, le même `staticwebapp.config.json` sert en changeant juste le secret GitHub.
- Audit git plus lisible : une revue du repo ne montre jamais de GUIDs Azure.

### Comment ça marche

1. `site/public/staticwebapp.config.json` (dans le public d'Astro pour qu'il soit copié tel quel à la racine de `site/dist/`, où SWA le lit) contient `"openIdIssuer": "https://login.microsoftonline.com/$AAD_TENANT_ID/v2.0"`.
2. Le workflow `.github/workflows/azure-static-web-apps-delightful-cliff-04d721f03.yml` a une étape **"Substitute AAD_TENANT_ID into staticwebapp.config.json"** entre le checkout et le `Azure/static-web-apps-deploy`.
3. Cette étape :
   - Lit `AAD_TENANT_ID` depuis les secrets GitHub Actions (`${{ secrets.AAD_TENANT_ID }}`).
   - Fail-fast si le secret est absent, avec un message pointant sur où l'ajouter.
   - `envsubst '$AAD_TENANT_ID' < config > config.tmp && mv` — seul cet nom est substitué, tout autre `$...` est préservé.
   - Post-check : `grep -F '$AAD_TENANT_ID'` — si le placeholder subsiste (renaming oublié, typo), on sort en erreur avant que SWA déploie une config cassée.
   - Log le `openIdIssuer` résolu pour confiance visuelle dans les logs du run.
4. `Azure/static-web-apps-deploy@v1` uploade alors la version substituée.

### Comment vérifier que ça marche

- **Pendant le run GitHub Actions** : le step "Substitute AAD_TENANT_ID..." doit afficher `openIdIssuer resolved to: https://login.microsoftonline.com/<vrai GUID>/v2.0`. Si `$AAD_TENANT_ID` apparaît tel quel dans ce log, la substitution a échoué.
- **Après déploiement** : tenter `/admin` en navigation privée. Redirect attendu vers `login.microsoftonline.com/<GUID>/oauth2/v2.0/authorize?...` avec le bon tenant dans l'URL.
- **Si auth tenant-missing** (erreur Azure "Tenant not found") : le secret est vide ou mal orthographié. Vérifier `Settings → Secrets → Actions → AAD_TENANT_ID`.

### Troubleshooting

| Symptôme | Cause probable | Fix |
|----------|----------------|-----|
| Workflow échoue au step "Substitute" avec "AAD_TENANT_ID secret is not set" | Secret absent ou mal nommé côté GitHub | `gh secret set AAD_TENANT_ID --body "<guid>"` ou via l'UI |
| Workflow échoue avec "Placeholder `$AAD_TENANT_ID` still present" | `envsubst` pas installé sur le runner, ou le placeholder a été renommé dans la config sans mettre à jour le step | `envsubst` est dans `gettext-base` (préinstallé sur ubuntu-latest). Sinon `apt-get install -y gettext-base` en prélude. |
| Au runtime, `/admin` renvoie "AADSTS90002 — Tenant not found" | Le secret contient une valeur erronée (mauvais GUID) | Corriger le secret, re-trigger le workflow |
| Au runtime, `/admin` rend la page en clair sans redirect | `staticwebapp.config.json` absent du build output Astro (route rules non chargées côté SWA) | Vérifier qu'il est bien dans `site/public/staticwebapp.config.json` pour qu'Astro le copie dans `site/dist/`. SWA cherche le fichier à la racine de l'output, pas à la racine du repo. |

## Sveltia version lock

Sveltia CMS est verrouillé sur une version spécifique dans `site/public/admin/index.html`. Le `auth-stub` (hack localStorage, cf. OD1) s'appuie sur des détails internes qui peuvent changer sans semver — d'où le pinning strict.

### Version courante

| | |
|---|---|
| Version | **0.156.3** |
| Pinné le | 2026-04-24 |
| CDN | `https://cdn.jsdelivr.net/npm/@sveltia/cms@0.156.3/dist/sveltia-cms.mjs` |
| Changelog | `https://github.com/sveltia/sveltia-cms/releases/tag/v0.156.3` |

### Points sensibles qui dépendent de la version

Si un de ces points change dans une future version, le hack peut casser silencieusement (pas d'erreur, juste le CMS qui renvoie Moncef sur un écran de login GitHub).

| # | Dépendance | Source | Signal de casse |
|---|------------|--------|-----------------|
| 1 | Clé localStorage primaire `sveltia-cms.user` | `src/lib/services/user/auth.js` (`getUserCache`) | Au boot, le CMS affiche l'écran "Sign in with GitHub" au lieu d'ouvrir l'éditeur directement |
| 2 | Shape de l'objet `User` (au moins : `backendName`, `token`, `login`, `name`) | `src/lib/types/private` | Idem — le user stub est rejeté silencieusement |
| 3 | Validation du token côté client (ex: vérification de signature, appel `/user` avec assertions) | `signInAutomatically()` / backend github | Stub rejeté même avec la bonne shape |
| 4 | Champ de config `api_root` et son interprétation | Doc backend GitHub Sveltia | Les appels CMS partent vers `api.github.com` au lieu de notre proxy → 401/404 côté GitHub avec notre token factice |
| 5 | Structure des appels GET que le github backend émet (path patterns) | backend source | Le proxy renvoie 403 (path whitelist) sur des endpoints que Sveltia appelle désormais |
| 6 | Format de la réponse `/user` (stub renvoyé par notre Function) | backend source (validation de la shape user) | Le CMS rejette l'identité renvoyée par notre stub |

### Procédure d'upgrade

Ne **jamais** bumper en prod directement. Étapes :

1. **Préparer une branche** `chore/sveltia-upgrade-vX.Y.Z` depuis `main`.
2. **Lire le changelog** entre version actuelle et version cible. Identifier tout ce qui touche :
   - `src/lib/services/user/*` (auth flow, localStorage)
   - `src/lib/services/backends/github*` (appels API)
   - Config schema (`api_root`, `backend.*`)
3. **Bumper** `site/public/admin/index.html` :
   - URL du `<script type="module" src="...">`
   - Commentaire de tête "pinned YYYY-MM-DD"
   - Lien changelog
4. **Relire le hack `sveltia-auth-stub`** ligne par ligne et confronter aux commits upstream sur `src/lib/services/user/auth.js`. Si un des 6 points sensibles ci-dessus a changé, adapter le stub.
5. **Tester en local** avec les App Settings Azure pointant sur un fork de prod ou un repo sandbox :
   - Login SWA Entra ID → `/admin/` → ne PAS être redirigé sur l'écran "Sign in with GitHub"
   - Ouvrir une édition existante → le contenu s'affiche correctement dans l'éditeur
   - Modifier un mot → Save → vérifier que le commit apparaît sur le repo sandbox avec l'identité Entra ID
   - Vérifier les logs Azure Function : aucun 403 de `/api/gh/*`, status 200 sur `/api/cms-commit`
6. **Déployer en prod** seulement après les 4 checks réussis. Garder la version précédente taggée en git (`git tag sveltia-pre-vX.Y.Z <sha>`) pour revert rapide.
7. **Mettre à jour cette section** : nouvelle version, nouvelle date.

### Fallback si ça casse

Si le hack n'est plus tenable après upgrade (ou si Sveltia ajoute un vrai support SSO client-side qui court-circuite notre proxy), pivoter sur **Voie B** (custom backend via `CMS.registerBackend()`). Les endpoints Azure Function (`/api/gh/*`, `/api/cms-commit`) restent identiques ; seul `site/public/admin/` change :
- Supprimer le `sveltia-auth-stub`
- Ajouter un bundle JS local `iris-backend.js` qui implémente `getEntry/listEntries/persistEntry` contre nos endpoints custom
- Changer `config.yml` : `backend: { name: 'iris-proxy' }`

Effort estimé : ~1 jour si le besoin se présente.

## Références

- STATE.md §9 — état du chantier CMS
- `api/README.md` — doc technique de l'Azure Function
- `site/public/admin/index.html` — scaffold CMS (Phase 3.2, fait)
- `site/public/admin/config.yml` — config Sveltia (Phase 3.3, à créer)
- `site/public/staticwebapp.config.json` — config auth SWA (sous `public/` pour être copié en sortie de build par Astro ; tenant ID substitué au build via workflow + secret GitHub)
