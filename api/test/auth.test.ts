import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { verifyClientPrincipal, isAllowlisted } from '../src/lib/auth.js';

const mockPrincipal = JSON.parse(
  readFileSync(resolve(import.meta.dirname, 'fixtures/mock-principal.json'), 'utf8'),
);
const mockHeaderValue = Buffer.from(JSON.stringify(mockPrincipal)).toString('base64');

test.skip('verifyClientPrincipal: decodes valid header → Principal', () => {
  const p = verifyClientPrincipal(mockHeaderValue);
  assert.equal(p.email, 'mha@cefic.be');
  assert.equal(p.displayName, 'Moncef Hadhri');
  assert.equal(p.identityProvider, 'aad');
  assert.ok(p.userRoles.includes('authenticated'));
});

test.skip('verifyClientPrincipal: throws on missing header', () => {
  assert.throws(() => verifyClientPrincipal(null), /missing/);
  assert.throws(() => verifyClientPrincipal(undefined), /missing/);
  assert.throws(() => verifyClientPrincipal(''), /missing/);
});

test.skip('verifyClientPrincipal: throws on malformed base64', () => {
  assert.throws(() => verifyClientPrincipal('not-base64!!'), /invalid/);
});

test.skip('isAllowlisted: true for known email (case-insensitive)', () => {
  process.env.CMS_ALLOWED_EMAILS = 'mha@cefic.be,jonathan@example.com';
  assert.equal(isAllowlisted('mha@cefic.be'), true);
  assert.equal(isAllowlisted('MHA@CEFIC.BE'), true);
});

test.skip('isAllowlisted: false for unknown email', () => {
  process.env.CMS_ALLOWED_EMAILS = 'mha@cefic.be';
  assert.equal(isAllowlisted('stranger@example.com'), false);
});
