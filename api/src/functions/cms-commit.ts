import { app, HttpRequest, HttpResponseInit, InvocationContext } from '@azure/functions';
import { verifyClientPrincipal, isAllowlisted, Principal } from '../lib/auth.js';
import { validateCommitPayload, CommitPayload } from '../lib/validation.js';
import { checkRateLimit } from '../lib/rate-limit.js';
import { commitFile, CommitResult } from '../lib/github.js';

/**
 * POST /api/cms-commit
 *
 * Sveltia CMS → this endpoint → GitHub.
 *
 * Orchestration only. Each step delegates to a lib/ module. Keep this
 * handler small and declarative so the contract stays readable.
 *
 * See context-prep/cms-design.md for the full interface contract.
 */
export async function cmsCommit(
  req: HttpRequest,
  ctx: InvocationContext,
): Promise<HttpResponseInit> {
  // 1. Verify Azure SWA principal (Entra ID identity injected by SWA).
  let principal: Principal;
  try {
    principal = verifyClientPrincipal(req.headers.get('x-ms-client-principal'));
  } catch (e) {
    ctx.log(`[cms-commit] principal rejected: ${(e as Error).message}`);
    return { status: 401, jsonBody: { error: 'unauthenticated' } };
  }

  // 2. Allowlist check.
  if (!isAllowlisted(principal.email)) {
    ctx.log(`[cms-commit] forbidden for ${principal.email}`);
    return { status: 403, jsonBody: { error: 'forbidden' } };
  }

  // 3. Parse + validate payload (path whitelist, JSON shape).
  let payload: CommitPayload;
  try {
    payload = validateCommitPayload(await req.json());
  } catch (e) {
    ctx.log(`[cms-commit] invalid payload: ${(e as Error).message}`);
    return { status: 400, jsonBody: { error: 'invalid_payload', detail: (e as Error).message } };
  }

  // 4. Rate limit (per email).
  if (!checkRateLimit(principal.email)) {
    return { status: 429, jsonBody: { error: 'rate_limited' } };
  }

  // 5. Commit via Octokit, stamped with the Entra ID author.
  let result: CommitResult;
  try {
    result = await commitFile({
      path: payload.path,
      content: payload.content,
      message: payload.message,
      author: {
        name: principal.displayName,
        email: principal.email,
      },
    });
  } catch (e) {
    ctx.log(`[cms-commit] github error: ${(e as Error).message}`);
    return { status: 502, jsonBody: { error: 'github_error', detail: (e as Error).message } };
  }

  ctx.log(
    `[cms-commit] ok path=${payload.path} author=${principal.email} sha=${result.sha}`,
  );
  return {
    status: 200,
    jsonBody: {
      status: 'ok',
      sha: result.sha,
      commit_url: result.commitUrl,
    },
  };
}

app.http('cms-commit', {
  methods: ['POST'],
  authLevel: 'anonymous', // SWA handles auth upstream; principal header is our trust anchor.
  route: 'cms-commit',
  handler: cmsCommit,
});
