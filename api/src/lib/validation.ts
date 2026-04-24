/**
 * Server-side validation of the CMS commit payload.
 *
 * The Azure Function must never trust the client. Even though Sveltia is the
 * intended caller, treat the payload as adversarial: an authenticated user
 * could craft a request bypassing the SPA and pointing to a non-editions
 * file. The path whitelist is the single hardest guardrail in this system.
 */

export interface CommitPayload {
  path: string;
  content: string;
  message: string;
  metadata?: Record<string, unknown>;
}

// Whitelist: only MDX edition files under site/src/content/editions can be edited.
// YYYY-MM.mdx, no subdirectories, no escape sequences.
const ALLOWED_PATH_PATTERN = /^site\/src\/content\/editions\/\d{4}-\d{2}\.mdx$/;

const MAX_CONTENT_BYTES = 256 * 1024; // 256 KB hard cap — edition files are ~10-20 KB today
const MAX_MESSAGE_LENGTH = 500;

export function validateCommitPayload(raw: unknown): CommitPayload {
  if (!raw || typeof raw !== 'object') {
    throw new Error('payload must be a JSON object');
  }
  // TODO: type-guard fields (path, content, message present as strings)
  // TODO: enforce ALLOWED_PATH_PATTERN on path — reject otherwise (403-ish semantics via 400)
  // TODO: enforce MAX_CONTENT_BYTES on content
  // TODO: enforce MAX_MESSAGE_LENGTH on message
  // TODO: sanitise metadata (strip unknown keys, keep only { edition, reviewed })
  // TODO: return the validated shape
  throw new Error('NOT_IMPLEMENTED: validateCommitPayload');
}

/**
 * Extracted for unit testing — exported so test/validation.test.ts
 * can exercise the pattern directly without a payload wrapper.
 */
export function isPathAllowed(path: string): boolean {
  return ALLOWED_PATH_PATTERN.test(path);
}
