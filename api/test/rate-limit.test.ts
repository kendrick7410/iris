import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkRateLimit, __resetForTests } from '../src/lib/rate-limit.js';

test('checkRateLimit: first call always allowed', () => {
  __resetForTests();
  assert.equal(checkRateLimit('mha@cefic.be', 1_000_000), true);
});

test('checkRateLimit: second call within window is rejected', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  assert.equal(checkRateLimit('mha@cefic.be', 1_001_000), false);
});

test('checkRateLimit: call after window is allowed', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  // Window is 10s by default (RATE_LIMIT_WINDOW_MS in env).
  assert.equal(checkRateLimit('mha@cefic.be', 1_015_000), true);
});

test('checkRateLimit: different users are independent', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  assert.equal(checkRateLimit('jme@cefic.be', 1_001_000), true);
});

test('checkRateLimit: email comparison is case-insensitive', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  assert.equal(checkRateLimit('MHA@CEFIC.BE', 1_001_000), false);
});
