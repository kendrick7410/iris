/**
 * Allowlist of GitHub API paths the CMS proxy is permitted to forward.
 *
 * The proxy is NOT a transparent mirror of api.github.com. An authenticated
 * Cefic user going through SWA + Entra ID could otherwise call
 * /api/gh/user/emails or /api/gh/notifications and surface data attached to
 * the machine PAT. Each allowed path is listed explicitly.
 *
 * Contents paths are further narrowed to the editions folder so Sveltia/
 * Decap can only read files the CMS is supposed to edit.
 */

export interface ProxyPathCheck {
  allowed: boolean;
  reason?: string;
}

const CONTENTS_PATH_PREFIX = 'site/src/content/editions/';

/**
 * Expected owner/repo pair for the proxy. Read from env at call time so
 * tests can swap via process.env without module reload.
 */
function expectedRepo(): { owner: string; repo: string } {
  const owner = process.env.GITHUB_OWNER ?? '';
  const repo = process.env.GITHUB_REPO ?? '';
  return { owner, repo };
}

/**
 * Inspect a path of the form `repos/{owner}/{repo}/...` (no leading slash)
 * and decide whether the proxy should forward it.
 */
export function checkProxyPath(path: string): ProxyPathCheck {
  if (!path) return { allowed: false, reason: 'empty path' };

  // /user is used by the CMS on boot to confirm auth. We special-case it
  // upstream (stub response from principal) instead of proxying.
  if (path === 'user') return { allowed: false, reason: 'served upstream, not proxied' };

  const { owner, repo } = expectedRepo();
  if (!owner || !repo) return { allowed: false, reason: 'GITHUB_OWNER/GITHUB_REPO unset' };

  const prefix = `repos/${owner}/${repo}/`;
  if (!path.startsWith(prefix)) {
    return { allowed: false, reason: `path outside repos/${owner}/${repo}/` };
  }
  const tail = path.slice(prefix.length);

  // Tree of the branch — reads the whole repo file listing. Repo is private;
  // Moncef already has effective read access via the CMS. Acceptable.
  if (/^git\/trees\/[^/]+$/.test(tail)) return { allowed: true };

  // Branch metadata (sha of HEAD) — no file contents exposed.
  if (/^branches\/[^/]+$/.test(tail)) return { allowed: true };

  // Contents: must be under the editions folder, no traversal.
  if (tail.startsWith('contents/')) {
    const contentsPath = tail.slice('contents/'.length);
    if (contentsPath.includes('..') || contentsPath.startsWith('/')) {
      return { allowed: false, reason: 'path traversal in contents' };
    }
    if (!contentsPath.startsWith(CONTENTS_PATH_PREFIX) && contentsPath !== CONTENTS_PATH_PREFIX.replace(/\/$/, '')) {
      return { allowed: false, reason: `contents outside ${CONTENTS_PATH_PREFIX}` };
    }
    return { allowed: true };
  }

  return { allowed: false, reason: 'endpoint not in allowlist' };
}
