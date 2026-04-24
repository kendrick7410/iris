import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { HttpRequest, InvocationContext } from '@azure/functions';
import { ghProxy, __setFetchForTests } from '../src/functions/gh-proxy.js';

const mockPrincipal = {
  identityProvider: 'aad',
  userId: '1',
  userDetails: 'mha@cefic.be',
  userRoles: ['authenticated'],
  claims: [{ typ: 'name', val: 'Moncef Hadhri' }],
};
const validPrincipalHeader = Buffer.from(JSON.stringify(mockPrincipal)).toString('base64');

function mockCtx(): InvocationContext {
  return { log: () => {}, error: () => {}, warn: () => {} } as unknown as InvocationContext;
}

function mockReq(opts: {
  path?: string;
  principal?: string | null;
  query?: Record<string, string>;
  method?: string;
  body?: string;
}): HttpRequest {
  const headers = new Map<string, string>();
  if (opts.principal !== null && opts.principal !== undefined) {
    headers.set('x-ms-client-principal', opts.principal);
  }
  const qs = opts.query
    ? '?' + new URLSearchParams(opts.query).toString()
    : '';
  const url = `https://iris.cefic.org/api/gh/${opts.path ?? ''}${qs}`;
  return {
    url,
    method: opts.method ?? 'GET',
    headers: {
      get: (k: string) => headers.get(k.toLowerCase()) ?? headers.get(k) ?? null,
    },
    params: { path: opts.path ?? '' },
    text: async () => opts.body ?? '',
  } as unknown as HttpRequest;
}

function setBaseEnv() {
  process.env.CMS_ALLOWED_EMAILS = 'mha@cefic.be,jme@cefic.be';
  process.env.GITHUB_OWNER = 'kendrick7410';
  process.env.GITHUB_REPO = 'iris';
  process.env.GITHUB_PAT = 'test-pat';
}

/** Returns a mock fetch that records the call and returns the given response. */
function mockFetch(response: { status: number; body: string; contentType?: string }) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fn: typeof fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    calls.push({ url, init });
    return {
      status: response.status,
      text: async () => response.body,
      headers: {
        get: (h: string) =>
          h.toLowerCase() === 'content-type'
            ? (response.contentType ?? 'application/json')
            : null,
      },
    } as unknown as Response;
  }) as typeof fetch;
  return { fn, calls };
}

test('gh-proxy: 401 when principal missing', async () => {
  setBaseEnv();
  const res = await ghProxy(
    mockReq({ path: 'repos/kendrick7410/iris/branches/main', principal: null }),
    mockCtx(),
  );
  assert.equal(res.status, 401);
});

test('gh-proxy: 403 when email not in allowlist', async () => {
  setBaseEnv();
  process.env.CMS_ALLOWED_EMAILS = 'other@example.com';
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/branches/main',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  assert.equal(res.status, 403);
});

test('gh-proxy: 403 when path not in allowlist', async () => {
  setBaseEnv();
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/issues',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  assert.equal(res.status, 403);
});

test('gh-proxy: /user returns stub from principal, no upstream call', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({ status: 200, body: '{}' });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({ path: 'user', principal: validPrincipalHeader }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 200);
  const body = res.jsonBody as Record<string, unknown>;
  assert.equal(body.login, 'mha@cefic.be');
  assert.equal(body.name, 'Moncef Hadhri');
  assert.equal(body.email, 'mha@cefic.be');
  assert.equal(calls.length, 0, 'fetch must not be called for /user');
});

// Sveltia v0.156+ prepends `/api/v3` to every call (it treats any custom
// api_root as a GHES base). Our proxy strips that prefix transparently so
// routing still works. The next two tests pin that behavior.

test('gh-proxy: strips api/v3/ prefix for /user (Sveltia v0.156 compat)', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({ status: 200, body: '{}' });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({ path: 'api/v3/user', principal: validPrincipalHeader }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 200);
  const body = res.jsonBody as Record<string, unknown>;
  assert.equal(body.login, 'mha@cefic.be');
  assert.equal(calls.length, 0, 'fetch must not be called for /user');
});

test('gh-proxy: strips api/v3/ prefix for repo paths (Sveltia v0.156 compat)', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({
    status: 200,
    body: '{"name":"main","commit":{"sha":"abc"}}',
  });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({
      path: 'api/v3/repos/kendrick7410/iris/branches/main',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 200);
  assert.equal(calls.length, 1);
  // Upstream URL must NOT contain the /api/v3/ prefix — that was Sveltia’s
  // synthetic addition, not a real api.github.com path.
  assert.match(
    calls[0].url,
    /^https:\/\/api\.github\.com\/repos\/kendrick7410\/iris\/branches\/main$/,
  );
});

// Sveltia calls /repos/{owner}/{repo}/collaborators/{userName} after signIn
// to confirm repo access. We stub 204 ("is a collaborator") since identity
// was already verified by SWA + CMS_ALLOWED_EMAILS.

test('gh-proxy: collaborator check stubs 204 for matching owner/repo', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({ status: 200, body: '{}' });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({
      path: 'api/v3/repos/kendrick7410/iris/collaborators/jme%40cefic.be',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 204);
  assert.equal(calls.length, 0, 'fetch must not be called for stubbed collaborator check');
});

test('gh-proxy: collaborator check rejected for wrong owner/repo', async () => {
  setBaseEnv();
  const res = await ghProxy(
    mockReq({
      path: 'api/v3/repos/attacker/secret/collaborators/someone',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  assert.equal(res.status, 403);
});

// GraphQL endpoint — Sveltia uses it for fetchFileContents. POST only.

test('gh-proxy: forwards POST /api/graphql to api.github.com/graphql', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({
    status: 200,
    body: '{"data":{"repository":{"defaultBranchRef":{"name":"main"}}}}',
  });
  __setFetchForTests(fn);
  const queryBody = '{"query":"query { repository(owner:\\"x\\", name:\\"y\\") { id } }"}';
  const res = await ghProxy(
    mockReq({
      path: 'api/graphql',
      principal: validPrincipalHeader,
      method: 'POST',
      body: queryBody,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://api.github.com/graphql');
  assert.equal(calls[0].init!.method, 'POST');
  assert.equal(calls[0].init!.body, queryBody);
  const headers = (calls[0].init!.headers ?? {}) as Record<string, string>;
  assert.equal(headers.Authorization, 'Bearer test-pat');
});

test('gh-proxy: GET on /api/graphql returns 405', async () => {
  setBaseEnv();
  const res = await ghProxy(
    mockReq({
      path: 'api/graphql',
      principal: validPrincipalHeader,
      method: 'GET',
    }),
    mockCtx(),
  );
  assert.equal(res.status, 405);
});

test('gh-proxy: POST on a REST path returns 405', async () => {
  setBaseEnv();
  const res = await ghProxy(
    mockReq({
      path: 'api/v3/repos/kendrick7410/iris/branches/main',
      principal: validPrincipalHeader,
      method: 'POST',
    }),
    mockCtx(),
  );
  assert.equal(res.status, 405);
});

test('gh-proxy: happy path — branches forwards to github with PAT', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({
    status: 200,
    body: '{"name":"main","commit":{"sha":"abc"}}',
  });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/branches/main',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);

  assert.equal(res.status, 200);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /^https:\/\/api\.github\.com\/repos\/kendrick7410\/iris\/branches\/main$/);
  const headers = (calls[0].init!.headers ?? {}) as Record<string, string>;
  assert.equal(headers.Authorization, 'Bearer test-pat');
});

test('gh-proxy: preserves query string (recursive=1)', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({ status: 200, body: '{"tree":[]}' });
  __setFetchForTests(fn);
  await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/git/trees/main',
      principal: validPrincipalHeader,
      query: { recursive: '1' },
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.match(calls[0].url, /recursive=1/);
});

test('gh-proxy: contents — allowed editions path', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({
    status: 200,
    body: '{"type":"file","content":"base64blob"}',
  });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/contents/site/src/content/editions/2026-02.mdx',
      principal: validPrincipalHeader,
      query: { ref: 'main' },
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 200);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /contents\/site\/src\/content\/editions\/2026-02\.mdx/);
  assert.match(calls[0].url, /ref=main/);
});

test('gh-proxy: contents — rejects path outside editions folder', async () => {
  setBaseEnv();
  const { fn, calls } = mockFetch({ status: 200, body: '{}' });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/contents/api/local.settings.json',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 403);
  assert.equal(calls.length, 0, 'fetch must not be called when path is rejected');
});

test('gh-proxy: 502 when fetch throws', async () => {
  setBaseEnv();
  const failingFetch = (async () => {
    throw new Error('network error');
  }) as unknown as typeof fetch;
  __setFetchForTests(failingFetch);
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/branches/main',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 502);
});

test('gh-proxy: forwards upstream status (e.g. 404)', async () => {
  setBaseEnv();
  const { fn } = mockFetch({ status: 404, body: '{"message":"Not Found"}' });
  __setFetchForTests(fn);
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/branches/nonexistent',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  __setFetchForTests(null);
  assert.equal(res.status, 404);
});

test('gh-proxy: 500 when GITHUB_PAT unset', async () => {
  setBaseEnv();
  delete process.env.GITHUB_PAT;
  const res = await ghProxy(
    mockReq({
      path: 'repos/kendrick7410/iris/branches/main',
      principal: validPrincipalHeader,
    }),
    mockCtx(),
  );
  assert.equal(res.status, 500);
});
