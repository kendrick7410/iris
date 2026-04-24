/**
 * Minimal per-user rate limiter.
 *
 * In-memory token bucket keyed by email. Scoped to the Function host
 * process: if SWA scales to multiple workers, each gets its own window.
 * That's fine for the editorial use case (1-2 editors, low traffic);
 * upgrade to a distributed store (Azure Table / Redis) if we ever
 * open the CMS to more users.
 */

const WINDOW_MS = Number(process.env.RATE_LIMIT_WINDOW_MS ?? 10_000);

const lastCommitAt = new Map<string, number>();

/**
 * Returns true if the commit is allowed, false if the user must wait.
 * Updates the internal window on a successful call.
 */
export function checkRateLimit(email: string, now: number = Date.now()): boolean {
  // TODO: compare now - lastCommitAt.get(email) against WINDOW_MS
  // TODO: if allowed, set lastCommitAt.set(email, now) and return true
  // TODO: otherwise return false
  throw new Error('NOT_IMPLEMENTED: checkRateLimit');
}

/**
 * Test helper — reset state between test cases.
 * Never called from production code paths.
 */
export function __resetForTests(): void {
  lastCommitAt.clear();
}
