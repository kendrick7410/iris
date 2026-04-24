/**
 * GitHub commit via Octokit.
 *
 * Uses a fine-grained PAT (env GITHUB_PAT) scoped to
 * `kendrick7410/iris` with `contents: write`. The PAT is the machine
 * identity; the commit's `author` and `committer` are set to the
 * Entra ID identity of the editor so `git log` reflects who actually
 * made the change.
 *
 * Algorithm (contents API):
 *   1. GET /repos/{owner}/{repo}/contents/{path}?ref={branch} → current sha
 *   2. PUT /repos/{owner}/{repo}/contents/{path} with {message, content (b64),
 *      sha, branch, committer, author}
 *
 * Overwrite-only semantics. New paths are rejected by validation.ts anyway.
 */

export interface CommitAuthor {
  name: string;
  email: string;
}

export interface CommitInput {
  path: string;
  content: string; // raw UTF-8, encoded to base64 before PUT
  message: string;
  author: CommitAuthor;
}

export interface CommitResult {
  sha: string;
  commitUrl: string;
}

import { Octokit } from '@octokit/rest';

let octokitInstance: Octokit | null = null;

/** Test hook — inject a mock client. */
export function __setOctokitForTests(client: Octokit | null): void {
  octokitInstance = client;
}

function getOctokit(): Octokit {
  if (octokitInstance) return octokitInstance;
  const pat = process.env.GITHUB_PAT;
  if (!pat) throw new Error('GITHUB_PAT not configured');
  octokitInstance = new Octokit({ auth: pat });
  return octokitInstance;
}

function repoConfig() {
  const owner = process.env.GITHUB_OWNER;
  const repo = process.env.GITHUB_REPO;
  const branch = process.env.GITHUB_BRANCH ?? 'main';
  if (!owner || !repo) throw new Error('GITHUB_OWNER and GITHUB_REPO must be set');
  return { owner, repo, branch };
}

export async function commitFile(input: CommitInput): Promise<CommitResult> {
  const octokit = getOctokit();
  const { owner, repo, branch } = repoConfig();

  // 1. Fetch current sha of the target file. Overwrite-only semantics:
  //    validation.ts already rejected paths that shouldn't exist, so a 404
  //    here is a real error (file missing on main) not a create-intent.
  const existing = await octokit.rest.repos.getContent({
    owner, repo, path: input.path, ref: branch,
  });
  if (Array.isArray(existing.data) || existing.data.type !== 'file') {
    throw new Error(`path is not a file: ${input.path}`);
  }
  const priorSha = existing.data.sha;

  // 2. PUT new content, stamping author + committer with the Entra ID identity.
  const result = await octokit.rest.repos.createOrUpdateFileContents({
    owner, repo, path: input.path, branch, sha: priorSha,
    message: input.message,
    content: Buffer.from(input.content, 'utf8').toString('base64'),
    committer: { name: input.author.name, email: input.author.email },
    author: { name: input.author.name, email: input.author.email },
  });

  const commitSha = result.data.commit.sha ?? '';
  const commitUrl = result.data.commit.html_url ?? '';
  return { sha: commitSha, commitUrl };
}
