import { app, HttpRequest, HttpResponseInit, InvocationContext } from '@azure/functions';
import { verifyClientPrincipal, isAllowlisted, Principal } from '../lib/auth.js';
import { checkProxyPath } from '../lib/proxy-paths.js';

/**
 * /api/gh/{*path}
 *
 * Proxy for the subset of api.github.com that Sveltia's `github` backend
 * calls when `api_root` points here. Sveltia v0.156+ normalizes any custom
 * api_root as a GitHub Enterprise Server base and prepends `/api/v3` to
 * REST calls (and posts GraphQL to `<root>/api/graphql`). Both flavours
 * land on this same function; the prefix is stripped below.
 *
 * Allowed flows:
 *   GET  /api/gh/api/v3/user                                   (stubbed)
 *   GET  /api/gh/api/v3/repos/{owner}/{repo}/collaborators/:u  (stubbed 204)
 *   GET  /api/gh/api/v3/repos/{owner}/{repo}/git/trees/{branch}?recursive=1
 *   GET  /api/gh/api/v3/repos/{owner}/{repo}/contents/{path}?ref={branch}
 *   GET  /api/gh/api/v3/repos/{owner}/{repo}/branches/{branch}
 *   POST /api/gh/api/graphql                                   (forwarded)
 *
 * The CMS is expected to authenticate via Azure SWA (Entra ID). We verify
 * the injected principal, apply the allowlist, validate the path against a
 * strict allowlist (not a transparent mirror of api.github.com), and then
 * forward to GitHub using the machine PAT.
 *
 * /user is served from the principal rather than proxied: GitHub would
 * otherwise return the PAT owner's identity and the CMS would display the
 * wrong user. /collaborators/:user is stubbed 204 for the same reason —
 * the username Sveltia sends is the Cefic email, which GitHub cannot
 * resolve to a login.
 */

// Test hook — mirrors __setOctokitForTests on github.ts.
type Fetcher = typeof fetch;
let fetchImpl: Fetcher = (...args) => fetch(...args);
export function __setFetchForTests(f: Fetcher | null): void {
  fetchImpl = f ?? ((...args) => fetch(...args));
}

function userStubFromPrincipal(p: Principal) {
  return {
    login: p.email,
    name: p.displayName,
    email: p.email,
    avatar_url: '',
    // Decap checks for a truthy id; any stable value works.
    id: 1,
  };
}

export async function ghProxy(
  req: HttpRequest,
  ctx: InvocationContext,
): Promise<HttpResponseInit> {
  // 1. Auth — same chain as cms-commit.
  let principal: Principal;
  try {
    principal = verifyClientPrincipal(req.headers.get('x-ms-client-principal'));
  } catch (e) {
    ctx.log(`[gh-proxy] principal rejected: ${(e as Error).message}`);
    return { status: 401, jsonBody: { error: 'unauthenticated' } };
  }
  if (!isAllowlisted(principal.email)) {
    ctx.log(`[gh-proxy] forbidden for ${principal.email}`);
    return { status: 403, jsonBody: { error: 'forbidden' } };
  }

  // 2. Resolve target path from the {*path} route parameter.
  //
  // Sveltia v0.156+ normalizes any non-default api_root as a GitHub Enterprise
  // Server base and auto-appends `/api/v3` (see sveltia-cms
  // src/lib/services/backends/git/github/api.js `normalizeRestBaseURL`). Our
  // configured api_root is https://iris.cefic.org/api/gh, so every request
  // arrives here as `api/v3/<real-path>`. Strip it so the rest of the routing
  // (user stub + whitelist) sees the real GitHub path.
  let targetPath = (req.params.path ?? '').replace(/^\/+/, '');
  if (targetPath === 'api/v3' || targetPath === 'api/v3/') {
    targetPath = '';
  } else if (targetPath.startsWith('api/v3/')) {
    targetPath = targetPath.slice('api/v3/'.length);
  }

  // /user is stubbed from the principal — no GitHub call.
  if (targetPath === 'user') {
    return { status: 200, jsonBody: userStubFromPrincipal(principal) };
  }

  // Sveltia v0.156+ calls `/repos/{owner}/{repo}/collaborators/{userName}`
  // right after signIn to verify the user can access the repo (see
  // sveltia-cms src/lib/services/backends/git/github/repository.js
  // `checkRepositoryAccess`). We've already verified the identity via
  // SWA principal + CMS_ALLOWED_EMAILS, and `userName` here is the
  // Cefic email (stubbed as `login` in /user above) which GitHub would
  // not recognize as a login anyway. Stub 204 No Content (= "is a
  // collaborator") so Sveltia proceeds to fetchFiles.
  const collaboratorMatch = /^repos\/([^/]+)\/([^/]+)\/collaborators\/[^/]+$/.exec(targetPath);
  if (collaboratorMatch) {
    const expectedOwner = process.env.GITHUB_OWNER ?? '';
    const expectedRepo = process.env.GITHUB_REPO ?? '';
    if (collaboratorMatch[1] === expectedOwner && collaboratorMatch[2] === expectedRepo) {
      return { status: 204 };
    }
    // Allowlist has already restricted which repo is visible; fall through to
    // the 403 below for any other owner/repo.
  }

  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    ctx.log('[gh-proxy] GITHUB_PAT not configured');
    return { status: 500, jsonBody: { error: 'misconfigured' } };
  }

  // GraphQL — Sveltia uses this for batched file-content fetches and for
  // default-branch discovery. It is a single POST endpoint, so there is no
  // per-path allowlist to apply; the PAT itself is fine-grained and scoped
  // to the iris repo only, which is the real boundary.
  if (targetPath === 'api/graphql') {
    if (req.method !== 'POST') {
      return { status: 405, jsonBody: { error: 'method_not_allowed' } };
    }
    const body = await req.text();
    let upstream: Response;
    try {
      upstream = await fetchImpl('https://api.github.com/graphql', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${pat}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'User-Agent': 'iris-cms-proxy',
        },
        body,
      });
    } catch (e) {
      ctx.log(`[gh-proxy] graphql fetch failed: ${(e as Error).message}`);
      return { status: 502, jsonBody: { error: 'github_unreachable' } };
    }
    const respBody = await upstream.text();
    ctx.log(`[gh-proxy] ${upstream.status} graphql user=${principal.email}`);
    return {
      status: upstream.status,
      body: respBody,
      headers: {
        'content-type': upstream.headers.get('content-type') ?? 'application/json',
      },
    };
  }

  // Everything else is a REST call — method must be GET.
  if (req.method !== 'GET') {
    return { status: 405, jsonBody: { error: 'method_not_allowed' } };
  }

  // 3. Whitelist check.
  const check = checkProxyPath(targetPath);
  if (!check.allowed) {
    ctx.log(`[gh-proxy] path rejected: ${targetPath} (${check.reason})`);
    return { status: 403, jsonBody: { error: 'path_not_allowed', detail: check.reason } };
  }

  // 4. Forward to api.github.com with the PAT.
  const url = new URL(`https://api.github.com/${targetPath}`);
  // Preserve incoming query string (e.g. ?recursive=1, ?ref=main).
  const incoming = new URL(req.url);
  for (const [k, v] of incoming.searchParams) url.searchParams.set(k, v);

  let upstream: Response;
  try {
    upstream = await fetchImpl(url.toString(), {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${pat}`,
        Accept: 'application/vnd.github.v3+json',
        'User-Agent': 'iris-cms-proxy',
      },
    });
  } catch (e) {
    ctx.log(`[gh-proxy] fetch failed: ${(e as Error).message}`);
    return { status: 502, jsonBody: { error: 'github_unreachable' } };
  }

  const body = await upstream.text();
  ctx.log(
    `[gh-proxy] ${upstream.status} path=${targetPath} user=${principal.email}`,
  );
  return {
    status: upstream.status,
    body,
    headers: {
      'content-type': upstream.headers.get('content-type') ?? 'application/json',
    },
  };
}

app.http('gh-proxy', {
  methods: ['GET', 'POST'], // POST is only honored for /api/graphql
  authLevel: 'anonymous', // SWA is upstream trust anchor.
  route: 'gh/{*path}',
  handler: ghProxy,
});
