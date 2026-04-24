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

export async function commitFile(input: CommitInput): Promise<CommitResult> {
  // TODO: read GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH from env
  // TODO: instantiate Octokit with auth = PAT
  // TODO: GET current file sha (rest.repos.getContent)
  // TODO: PUT new content (rest.repos.createOrUpdateFileContents)
  //        committer = author = input.author
  // TODO: return { sha, commitUrl } from response
  throw new Error('NOT_IMPLEMENTED: commitFile');
}
