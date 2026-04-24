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
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('payload must be a JSON object');
  }
  const obj = raw as Record<string, unknown>;

  const requireString = (key: string): string => {
    const v = obj[key];
    if (typeof v !== 'string' || !v) {
      throw new Error(`missing or invalid field: ${key}`);
    }
    return v;
  };

  const path = requireString('path');
  const content = requireString('content');
  const message = requireString('message');

  if (!isPathAllowed(path)) {
    throw new Error(`path not allowed: ${path}`);
  }
  if (Buffer.byteLength(content, 'utf8') > MAX_CONTENT_BYTES) {
    throw new Error(`content exceeds max size (${MAX_CONTENT_BYTES} bytes)`);
  }
  if (message.length > MAX_MESSAGE_LENGTH) {
    throw new Error(`message exceeds ${MAX_MESSAGE_LENGTH} chars`);
  }

  // Sanitise metadata: keep only known keys.
  let metadata: Record<string, unknown> | undefined;
  const rawMeta = obj.metadata;
  if (rawMeta && typeof rawMeta === 'object' && !Array.isArray(rawMeta)) {
    const m = rawMeta as Record<string, unknown>;
    metadata = {};
    if (typeof m.edition === 'string') metadata.edition = m.edition;
    if (typeof m.reviewed === 'boolean') metadata.reviewed = m.reviewed;
  }

  return { path, content, message, metadata };
}

/**
 * Extracted for unit testing — exported so test/validation.test.ts
 * can exercise the pattern directly without a payload wrapper.
 */
export function isPathAllowed(path: string): boolean {
  return ALLOWED_PATH_PATTERN.test(path);
}
