import { test } from 'node:test';
import assert from 'node:assert/strict';
import { verifyClientPrincipal, isAllowlisted } from '../src/lib/auth.js';

// Matches test/fixtures/mock-principal.json — inlined so tests don't depend on
// tsc copying non-TS assets into dist/.
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
const mockHeaderValue = Buffer.from(JSON.stringify(mockPrincipal)).toString('base64');

test('verifyClientPrincipal: decodes valid header → Principal', () => {
  const p = verifyClientPrincipal(mockHeaderValue);
  assert.equal(p.email, 'mha@cefic.be');
  assert.equal(p.displayName, 'Moncef Hadhri');
  assert.equal(p.identityProvider, 'aad');
  assert.ok(p.userRoles.includes('authenticated'));
});

test('verifyClientPrincipal: throws on missing header', () => {
  assert.throws(() => verifyClientPrincipal(null), /missing/);
  assert.throws(() => verifyClientPrincipal(undefined), /missing/);
  assert.throws(() => verifyClientPrincipal(''), /missing/);
});

test('verifyClientPrincipal: throws on malformed base64', () => {
  assert.throws(() => verifyClientPrincipal('!!not-valid-base64-at-all!!'), /invalid/);
});

test('verifyClientPrincipal: throws when principal has no email', () => {
  const stripped = { ...mockPrincipal, userDetails: '', claims: [] };
  const header = Buffer.from(JSON.stringify(stripped)).toString('base64');
  assert.throws(() => verifyClientPrincipal(header), /email/);
});

test('verifyClientPrincipal: falls back to emailaddress claim when userDetails missing', () => {
  const { userDetails: _unused, ...rest } = mockPrincipal;
  void _unused;
  const header = Buffer.from(JSON.stringify(rest)).toString('base64');
  const p = verifyClientPrincipal(header);
  assert.equal(p.email, 'mha@cefic.be');
});

test('isAllowlisted: true for known email (case-insensitive)', () => {
  process.env.CMS_ALLOWED_EMAILS = 'mha@cefic.be,jme@cefic.be';
  assert.equal(isAllowlisted('mha@cefic.be'), true);
  assert.equal(isAllowlisted('MHA@CEFIC.BE'), true);
  assert.equal(isAllowlisted('  mha@cefic.be  '), true);
});

test('isAllowlisted: false for unknown email', () => {
  process.env.CMS_ALLOWED_EMAILS = 'mha@cefic.be';
  assert.equal(isAllowlisted('stranger@example.com'), false);
});

test('isAllowlisted: false when env var unset or empty', () => {
  delete process.env.CMS_ALLOWED_EMAILS;
  assert.equal(isAllowlisted('mha@cefic.be'), false);
  process.env.CMS_ALLOWED_EMAILS = '';
  assert.equal(isAllowlisted('mha@cefic.be'), false);
});
