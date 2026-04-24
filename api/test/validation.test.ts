import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateCommitPayload, isPathAllowed } from '../src/lib/validation.js';

test('isPathAllowed: accepts valid edition paths', () => {
  assert.equal(isPathAllowed('site/src/content/editions/2026-02.mdx'), true);
  assert.equal(isPathAllowed('site/src/content/editions/2025-12.mdx'), true);
});

test('isPathAllowed: rejects out-of-tree paths', () => {
  assert.equal(isPathAllowed('../../../etc/passwd'), false);
  assert.equal(isPathAllowed('site/src/pages/index.astro'), false);
  assert.equal(isPathAllowed('editorial/drafts/2026-02/edition.md'), false);
  assert.equal(isPathAllowed('.github/workflows/deploy.yml'), false);
});

test('isPathAllowed: rejects subdirectories and wrong extensions', () => {
  assert.equal(isPathAllowed('site/src/content/editions/2026-02/nested.mdx'), false);
  assert.equal(isPathAllowed('site/src/content/editions/2026-02.md'), false);
  assert.equal(isPathAllowed('site/src/content/editions/bad-slug.mdx'), false);
});

test('validateCommitPayload: happy path', () => {
  const payload = validateCommitPayload({
    path: 'site/src/content/editions/2026-02.mdx',
    content: '---\nmonth: 2026-02\n---\n\n## Heading\n\nBody.\n',
    message: 'edit: rephrase',
  });
  assert.equal(payload.path, 'site/src/content/editions/2026-02.mdx');
  assert.equal(payload.message, 'edit: rephrase');
});

test('validateCommitPayload: sanitises metadata to known keys', () => {
  const payload = validateCommitPayload({
    path: 'site/src/content/editions/2026-02.mdx',
    content: 'x',
    message: 'y',
    metadata: { edition: '2026-02', reviewed: true, sneaky: 'drop me' },
  });
  assert.deepEqual(payload.metadata, { edition: '2026-02', reviewed: true });
});

test('validateCommitPayload: rejects missing fields', () => {
  assert.throws(() => validateCommitPayload({ path: 'x', content: 'y' }), /message/);
  assert.throws(
    () => validateCommitPayload({ path: 'site/src/content/editions/2026-02.mdx', message: 'y' }),
    /content/,
  );
});

test('validateCommitPayload: rejects non-object', () => {
  assert.throws(() => validateCommitPayload(null), /object/);
  assert.throws(() => validateCommitPayload('not-an-object'), /object/);
  assert.throws(() => validateCommitPayload([]), /object/);
});

test('validateCommitPayload: rejects path outside whitelist', () => {
  assert.throws(
    () =>
      validateCommitPayload({
        path: 'editorial/drafts/2026-02/edition.md',
        content: 'x',
        message: 'y',
      }),
    /path not allowed/,
  );
});

test('validateCommitPayload: rejects oversize content', () => {
  const huge = 'x'.repeat(300 * 1024);
  assert.throws(
    () =>
      validateCommitPayload({
        path: 'site/src/content/editions/2026-02.mdx',
        content: huge,
        message: 'y',
      }),
    /max size/,
  );
});

test('validateCommitPayload: rejects overly long message', () => {
  assert.throws(
    () =>
      validateCommitPayload({
        path: 'site/src/content/editions/2026-02.mdx',
        content: 'x',
        message: 'y'.repeat(501),
      }),
    /chars/,
  );
});
