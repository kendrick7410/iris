import { app, HttpRequest, HttpResponseInit, InvocationContext } from '@azure/functions';
import { verifyClientPrincipal, isAllowlisted, Principal } from '../lib/auth.js';
import { checkProxyPath } from '../lib/proxy-paths.js';

/**
 * GET /api/gh/{*path}
 *
 * Read-only proxy for the GitHub Contents API subset that Sveltia/Decap's
 * `github` backend calls when `api_root` is set to this endpoint.
 *
 *   GET /api/gh/repos/{owner}/{repo}/git/trees/{branch}?recursive=1
 *   GET /api/gh/repos/{owner}/{repo}/contents/{path}?ref={branch}
 *   GET /api/gh/repos/{owner}/{repo}/branches/{branch}
 *   GET /api/gh/user                       (stubbed — see below)
 *
 * The CMS is expected to authenticate via Azure SWA (Entra ID). We verify
 * the injected principal, apply the allowlist, validate the path against a
 * strict allowlist (not a transparent mirror of api.github.com), and then
 * forward to GitHub using the machine PAT.
 *
 * /user is served from the principal rather than proxied: GitHub would
 * otherwise return the PAT owner's identity and the CMS would display the
 * wrong user.
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
  const targetPath = (req.params.path ?? '').replace(/^\/+/, '');

  // /user is stubbed from the principal — no GitHub call.
  if (targetPath === 'user') {
    return { status: 200, jsonBody: userStubFromPrincipal(principal) };
  }

  // 3. Whitelist check.
  const check = checkProxyPath(targetPath);
  if (!check.allowed) {
    ctx.log(`[gh-proxy] path rejected: ${targetPath} (${check.reason})`);
    return { status: 403, jsonBody: { error: 'path_not_allowed', detail: check.reason } };
  }

  // 4. Forward to api.github.com with the PAT.
  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    ctx.log('[gh-proxy] GITHUB_PAT not configured');
    return { status: 500, jsonBody: { error: 'misconfigured' } };
  }

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
  methods: ['GET'],
  authLevel: 'anonymous', // SWA is upstream trust anchor.
  route: 'gh/{*path}',
  handler: ghProxy,
});
