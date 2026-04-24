# Iris CMS — Azure Function API

Proxy de commits pour le CMS Iris. Reçoit les sauvegardes de Sveltia CMS depuis
le portail `/admin`, authentifie l'éditeur via Azure SWA (Entra ID), et commit
sur `kendrick7410/iris` en préservant l'identité Cefic comme auteur du commit.

Design complet : [`context-prep/cms-design.md`](../context-prep/cms-design.md).

## État actuel

**Scaffold uniquement.** Handlers et libs sont des stubs qui jettent
`NOT_IMPLEMENTED`. Les tests sont `test.skip()` sur tout sauf la validation
path (seule logique déjà exprimée). Voir STATE.md §9 pour la roadmap.

## Structure

```
api/
├── host.json                    # Azure Functions runtime config
├── package.json                 # Node 20, @azure/functions v4, @octokit/rest
├── tsconfig.json
├── .funcignore
├── local.settings.json.example  # copier → local.settings.json, remplir
├── src/
│   ├── functions/
│   │   └── cms-commit.ts        # HTTP POST /api/cms-commit
│   └── lib/
│       ├── auth.ts              # verifyClientPrincipal, isAllowlisted
│       ├── validation.ts        # validateCommitPayload, isPathAllowed
│       ├── rate-limit.ts        # checkRateLimit (in-memory, per email)
│       └── github.ts            # commitFile (Octokit)
└── test/
    ├── auth.test.ts
    ├── validation.test.ts       # isPathAllowed actif, reste skip
    ├── rate-limit.test.ts
    ├── cms-commit.test.ts
    └── fixtures/
        └── mock-principal.json  # identité Moncef type Entra ID
```

## Contract

### Request

```http
POST /api/cms-commit
x-ms-client-principal: <base64 JSON injecté par Azure SWA>
Content-Type: application/json

{
  "path": "site/src/content/editions/2026-02.mdx",
  "content": "<MDX complet>",
  "message": "edit: rephrase",
  "metadata": { "edition": "2026-02", "reviewed": false }
}
```

### Response codes

| Code | Raison |
|------|--------|
| 200  | Commit réussi, body `{ status, sha, commit_url }` |
| 400  | Payload invalide ou path hors whitelist |
| 401  | Principal Entra ID absent ou malformé |
| 403  | Utilisateur hors allowlist |
| 429  | Rate limit (1 commit / 10s par email) |
| 502  | Erreur GitHub API |

## Env vars requises (Azure App Settings)

- `GITHUB_PAT` — fine-grained PAT, scope `kendrick7410/iris`, `contents: write`
- `GITHUB_OWNER` — `kendrick7410`
- `GITHUB_REPO` — `iris`
- `GITHUB_BRANCH` — `main`
- `CMS_ALLOWED_EMAILS` — CSV des emails autorisés
- `RATE_LIMIT_WINDOW_MS` — fenêtre rate-limit (default 10000)

En local : copier `local.settings.json.example` vers `local.settings.json` (gitignored).

## Dev local

```bash
cd api
npm install
npm run build
npm test                 # tests Node natifs (node --test)
npm start                # lance func start (requires Azure Functions Core Tools v4)
```

Puis depuis un autre terminal :

```bash
# Test sans principal → expect 401
curl -X POST http://localhost:7071/api/cms-commit \
  -H 'Content-Type: application/json' \
  -d '{"path":"site/src/content/editions/2026-02.mdx","content":"x","message":"y"}'

# Test avec principal mocké (base64 du fixture)
PRINCIPAL=$(base64 -w0 test/fixtures/mock-principal.json)
curl -X POST http://localhost:7071/api/cms-commit \
  -H "x-ms-client-principal: $PRINCIPAL" \
  -H 'Content-Type: application/json' \
  -d '{"path":"site/src/content/editions/2026-02.mdx","content":"x","message":"y"}'
```

## Déploiement

Pas encore wiré. Voir OD2 dans `context-prep/cms-design.md` : quand
l'implémentation sera prête, passer `api_location: ""` à `api_location: "api"`
dans `.github/workflows/azure-static-web-apps-delightful-cliff-04d721f03.yml`
pour que SWA build et déploie ces functions avec le site.
