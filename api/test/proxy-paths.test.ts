import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkProxyPath } from '../src/lib/proxy-paths.js';

function setRepo() {
  process.env.GITHUB_OWNER = 'kendrick7410';
  process.env.GITHUB_REPO = 'iris';
}

test('allows git/trees/{branch}', () => {
  setRepo();
  assert.equal(checkProxyPath('repos/kendrick7410/iris/git/trees/main').allowed, true);
  assert.equal(checkProxyPath('repos/kendrick7410/iris/git/trees/feature-branch').allowed, true);
});

test('allows branches/{branch}', () => {
  setRepo();
  assert.equal(checkProxyPath('repos/kendrick7410/iris/branches/main').allowed, true);
});

test('allows contents/ under the editions folder', () => {
  setRepo();
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/contents/site/src/content/editions/2026-02.mdx').allowed,
    true,
  );
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/contents/site/src/content/editions/').allowed,
    true,
  );
});

test('rejects contents/ outside the editions folder', () => {
  setRepo();
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/contents/.env').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/contents/api/local.settings.json').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/contents/editorial/drafts/2026-02/edition.md').allowed,
    false,
  );
});

test('rejects path traversal in contents/', () => {
  setRepo();
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/contents/site/src/content/editions/../../../etc/passwd').allowed,
    false,
  );
});

test('rejects the wrong owner or repo', () => {
  setRepo();
  assert.equal(
    checkProxyPath('repos/someone-else/iris/git/trees/main').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('repos/kendrick7410/not-iris/git/trees/main').allowed,
    false,
  );
});

test('rejects /user (served upstream, not proxied)', () => {
  setRepo();
  assert.equal(checkProxyPath('user').allowed, false);
});

test('rejects arbitrary GitHub endpoints even for the right repo', () => {
  setRepo();
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/issues').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/actions/runs').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/collaborators').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('user/emails').allowed,
    false,
  );
  assert.equal(
    checkProxyPath('notifications').allowed,
    false,
  );
});

test('rejects when GITHUB_OWNER/REPO env missing', () => {
  delete process.env.GITHUB_OWNER;
  delete process.env.GITHUB_REPO;
  assert.equal(
    checkProxyPath('repos/kendrick7410/iris/git/trees/main').allowed,
    false,
  );
});

test('rejects empty path', () => {
  setRepo();
  assert.equal(checkProxyPath('').allowed, false);
});
