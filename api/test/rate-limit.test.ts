import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkRateLimit, __resetForTests } from '../src/lib/rate-limit.js';

test.skip('checkRateLimit: first call always allowed', () => {
  __resetForTests();
  assert.equal(checkRateLimit('mha@cefic.be', 1_000_000), true);
});

test.skip('checkRateLimit: second call within window is rejected', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  assert.equal(checkRateLimit('mha@cefic.be', 1_001_000), false); // 1s later, window=10s
});

test.skip('checkRateLimit: call after window is allowed', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  assert.equal(checkRateLimit('mha@cefic.be', 1_015_000), true); // 15s later
});

test.skip('checkRateLimit: different users are independent', () => {
  __resetForTests();
  checkRateLimit('mha@cefic.be', 1_000_000);
  assert.equal(checkRateLimit('jonathan@example.com', 1_001_000), true);
});
