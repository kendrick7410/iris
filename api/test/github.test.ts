import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { Octokit } from '@octokit/rest';
import { commitFile, __setOctokitForTests } from '../src/lib/github.js';

function makeMockOctokit(opts: {
  existingSha?: string;
  isDirectory?: boolean;
  captureCreateOrUpdate?: (args: unknown) => void;
  throwOnCreate?: Error;
}): Octokit {
  return {
    rest: {
      repos: {
        getContent: async () => {
          if (opts.isDirectory) {
            return { data: [] } as unknown as Awaited<ReturnType<Octokit['rest']['repos']['getContent']>>;
          }
          return {
            data: { type: 'file', sha: opts.existingSha ?? 'prior-sha' },
          } as unknown as Awaited<ReturnType<Octokit['rest']['repos']['getContent']>>;
        },
        createOrUpdateFileContents: async (args: unknown) => {
          opts.captureCreateOrUpdate?.(args);
          if (opts.throwOnCreate) throw opts.throwOnCreate;
          return {
            data: {
              commit: {
                sha: 'new-commit-sha',
                html_url: 'https://github.com/kendrick7410/iris/commit/new-commit-sha',
              },
            },
          } as unknown as Awaited<ReturnType<Octokit['rest']['repos']['createOrUpdateFileContents']>>;
        },
      },
    },
  } as unknown as Octokit;
}

function setEnv() {
  process.env.GITHUB_OWNER = 'kendrick7410';
  process.env.GITHUB_REPO = 'iris';
  process.env.GITHUB_BRANCH = 'main';
  process.env.GITHUB_PAT = 'test-pat';
}

test('commitFile: happy path returns sha + commit url', async () => {
  setEnv();
  __setOctokitForTests(makeMockOctokit({}));
  const result = await commitFile({
    path: 'site/src/content/editions/2026-02.mdx',
    content: 'hello',
    message: 'edit: rephrase',
    author: { name: 'Moncef Hadhri', email: 'mha@cefic.be' },
  });
  assert.equal(result.sha, 'new-commit-sha');
  assert.match(result.commitUrl, /new-commit-sha$/);
});

test('commitFile: stamps author + committer from input', async () => {
  setEnv();
  const captured: { args: Record<string, unknown> | null } = { args: null };
  __setOctokitForTests(
    makeMockOctokit({
      captureCreateOrUpdate: (args) => {
        captured.args = args as Record<string, unknown>;
      },
    }),
  );
  await commitFile({
    path: 'site/src/content/editions/2026-02.mdx',
    content: 'hello',
    message: 'edit',
    author: { name: 'Moncef Hadhri', email: 'mha@cefic.be' },
  });
  assert.ok(captured.args, 'createOrUpdate should have been called');
  assert.deepEqual(captured.args!.author, { name: 'Moncef Hadhri', email: 'mha@cefic.be' });
  assert.deepEqual(captured.args!.committer, { name: 'Moncef Hadhri', email: 'mha@cefic.be' });
});

test('commitFile: base64-encodes content before PUT', async () => {
  setEnv();
  const captured: { args: Record<string, unknown> | null } = { args: null };
  __setOctokitForTests(
    makeMockOctokit({
      captureCreateOrUpdate: (args) => {
        captured.args = args as Record<string, unknown>;
      },
    }),
  );
  await commitFile({
    path: 'site/src/content/editions/2026-02.mdx',
    content: 'hello',
    message: 'edit',
    author: { name: 'x', email: 'x@x' },
  });
  assert.equal(captured.args!.content, Buffer.from('hello', 'utf8').toString('base64'));
});

test('commitFile: passes prior sha from getContent to createOrUpdate', async () => {
  setEnv();
  const captured: { args: Record<string, unknown> | null } = { args: null };
  __setOctokitForTests(
    makeMockOctokit({
      existingSha: 'abc123',
      captureCreateOrUpdate: (args) => {
        captured.args = args as Record<string, unknown>;
      },
    }),
  );
  await commitFile({
    path: 'site/src/content/editions/2026-02.mdx',
    content: 'x',
    message: 'y',
    author: { name: 'x', email: 'x@x' },
  });
  assert.equal(captured.args!.sha, 'abc123');
});

test('commitFile: throws if path resolves to a directory', async () => {
  setEnv();
  __setOctokitForTests(makeMockOctokit({ isDirectory: true }));
  await assert.rejects(
    commitFile({
      path: 'site/src/content/editions/2026-02.mdx',
      content: 'x',
      message: 'y',
      author: { name: 'x', email: 'x@x' },
    }),
    /not a file/,
  );
});

test('commitFile: propagates Octokit errors', async () => {
  setEnv();
  __setOctokitForTests(
    makeMockOctokit({ throwOnCreate: new Error('422 Unprocessable') }),
  );
  await assert.rejects(
    commitFile({
      path: 'site/src/content/editions/2026-02.mdx',
      content: 'x',
      message: 'y',
      author: { name: 'x', email: 'x@x' },
    }),
    /422/,
  );
});
