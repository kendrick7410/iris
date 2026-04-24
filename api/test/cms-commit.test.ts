/**
 * Integration tests for the cms-commit handler.
 *
 * Octokit is replaced via __setOctokitForTests, so no network calls.
 * Request objects are minimal HttpRequest-likes built per test.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { HttpRequest, InvocationContext } from '@azure/functions';
import type { Octokit } from '@octokit/rest';

import { cmsCommit } from '../src/functions/cms-commit.js';
import { __setOctokitForTests } from '../src/lib/github.js';
import { __resetForTests as resetRateLimit } from '../src/lib/rate-limit.js';

const mockPrincipal = {
  identityProvider: 'aad',
  userId: '00000000-0000-0000-0000-000000000001',
  userDetails: 'mha@cefic.be',
  userRoles: ['authenticated'],
  claims: [
    { typ: 'name', val: 'Moncef Hadhri' },
    {
      typ: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
      val: 'mha@cefic.be',
    },
  ],
};
const validPrincipalHeader = Buffer.from(JSON.stringify(mockPrincipal)).toString('base64');

function mockCtx(): InvocationContext {
  return { log: () => {}, error: () => {}, warn: () => {} } as unknown as InvocationContext;
}

function mockReq(opts: {
  principal?: string | null;
  body?: unknown;
}): HttpRequest {
  const headers = new Map<string, string>();
  if (opts.principal !== null && opts.principal !== undefined) {
    headers.set('x-ms-client-principal', opts.principal);
  }
  return {
    headers: {
      get: (k: string) => headers.get(k.toLowerCase()) ?? headers.get(k) ?? null,
    },
    json: async () => opts.body,
  } as unknown as HttpRequest;
}

function mockOctokit(overrides?: { throwOnCreate?: Error }): Octokit {
  return {
    rest: {
      repos: {
        getContent: async () => ({
          data: { type: 'file', sha: 'prior-sha' },
        }) as unknown as Awaited<ReturnType<Octokit['rest']['repos']['getContent']>>,
        createOrUpdateFileContents: async () => {
          if (overrides?.throwOnCreate) throw overrides.throwOnCreate;
          return {
            data: {
              commit: {
                sha: 'new-sha',
                html_url: 'https://github.com/kendrick7410/iris/commit/new-sha',
              },
            },
          } as unknown as Awaited<ReturnType<Octokit['rest']['repos']['createOrUpdateFileContents']>>;
        },
      },
    },
  } as unknown as Octokit;
}

function setBaseEnv() {
  process.env.CMS_ALLOWED_EMAILS = 'mha@cefic.be,jme@cefic.be';
  process.env.GITHUB_OWNER = 'kendrick7410';
  process.env.GITHUB_REPO = 'iris';
  process.env.GITHUB_BRANCH = 'main';
  process.env.GITHUB_PAT = 'test-pat';
}

const validBody = () => ({
  path: 'site/src/content/editions/2026-02.mdx',
  content: '---\nmonth: 2026-02\n---\n\n## Heading\n\nBody.\n',
  message: 'edit: rephrase',
});

test('cms-commit: 401 when x-ms-client-principal is missing', async () => {
  setBaseEnv();
  resetRateLimit();
  const res = await cmsCommit(mockReq({ principal: null, body: validBody() }), mockCtx());
  assert.equal(res.status, 401);
});

test('cms-commit: 403 when user not in allowlist', async () => {
  setBaseEnv();
  resetRateLimit();
  process.env.CMS_ALLOWED_EMAILS = 'someone-else@example.com';
  const res = await cmsCommit(
    mockReq({ principal: validPrincipalHeader, body: validBody() }),
    mockCtx(),
  );
  assert.equal(res.status, 403);
});

test('cms-commit: 400 on invalid payload shape', async () => {
  setBaseEnv();
  resetRateLimit();
  const res = await cmsCommit(
    mockReq({ principal: validPrincipalHeader, body: { path: 'bad', content: 'x' } }),
    mockCtx(),
  );
  assert.equal(res.status, 400);
});

test('cms-commit: 400 on path outside whitelist', async () => {
  setBaseEnv();
  resetRateLimit();
  const res = await cmsCommit(
    mockReq({
      principal: validPrincipalHeader,
      body: { ...validBody(), path: 'editorial/drafts/2026-02/edition.md' },
    }),
    mockCtx(),
  );
  assert.equal(res.status, 400);
});

test('cms-commit: 429 on rate limit', async () => {
  setBaseEnv();
  resetRateLimit();
  __setOctokitForTests(mockOctokit());
  const first = await cmsCommit(
    mockReq({ principal: validPrincipalHeader, body: validBody() }),
    mockCtx(),
  );
  assert.equal(first.status, 200);
  const second = await cmsCommit(
    mockReq({ principal: validPrincipalHeader, body: validBody() }),
    mockCtx(),
  );
  assert.equal(second.status, 429);
});

test('cms-commit: 200 happy path returns commit info', async () => {
  setBaseEnv();
  resetRateLimit();
  __setOctokitForTests(mockOctokit());
  const res = await cmsCommit(
    mockReq({ principal: validPrincipalHeader, body: validBody() }),
    mockCtx(),
  );
  assert.equal(res.status, 200);
  const body = res.jsonBody as Record<string, unknown>;
  assert.equal(body.status, 'ok');
  assert.equal(body.sha, 'new-sha');
  assert.match(body.commit_url as string, /new-sha$/);
});

test('cms-commit: 502 when Octokit throws', async () => {
  setBaseEnv();
  resetRateLimit();
  __setOctokitForTests(mockOctokit({ throwOnCreate: new Error('422') }));
  const res = await cmsCommit(
    mockReq({ principal: validPrincipalHeader, body: validBody() }),
    mockCtx(),
  );
  assert.equal(res.status, 502);
});
