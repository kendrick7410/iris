/**
 * Azure SWA client principal verification.
 *
 * When a request reaches an SWA-protected route, SWA injects the
 * authenticated user as a base64-encoded JSON blob in `x-ms-client-principal`.
 * We do NOT re-verify signatures here — SWA is our upstream trust anchor.
 * We only parse + validate shape + extract identity.
 *
 * Docs: https://learn.microsoft.com/azure/static-web-apps/user-information
 */

export interface Principal {
  email: string;
  displayName: string;
  identityProvider: string;
  userId: string;
  userRoles: string[];
}

interface RawClaim {
  typ: string;
  val: string;
}

interface RawPrincipal {
  identityProvider?: string;
  userId?: string;
  userDetails?: string;
  userRoles?: string[];
  claims?: RawClaim[];
}

const EMAIL_CLAIM = 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress';

export function verifyClientPrincipal(headerValue: string | null | undefined): Principal {
  if (!headerValue) {
    throw new Error('missing x-ms-client-principal header');
  }

  let raw: RawPrincipal;
  try {
    const decoded = Buffer.from(headerValue, 'base64').toString('utf-8');
    raw = JSON.parse(decoded) as RawPrincipal;
  } catch {
    throw new Error('invalid x-ms-client-principal: not base64-encoded JSON');
  }

  if (!raw || typeof raw !== 'object') {
    throw new Error('invalid principal payload');
  }

  const claimOf = (typ: string): string | undefined =>
    raw.claims?.find((c) => c.typ === typ)?.val;

  const email = (raw.userDetails ?? claimOf(EMAIL_CLAIM) ?? '').trim();
  if (!email) {
    throw new Error('principal has no email (userDetails or emailaddress claim)');
  }

  const displayName = (claimOf('name') ?? raw.userDetails ?? email).trim();

  return {
    email,
    displayName,
    identityProvider: raw.identityProvider ?? 'unknown',
    userId: raw.userId ?? '',
    userRoles: raw.userRoles ?? [],
  };
}

/**
 * Check whether the authenticated email is allowed to commit.
 * Reads CMS_ALLOWED_EMAILS (CSV) from env. Case-insensitive match.
 */
export function isAllowlisted(email: string): boolean {
  const csv = process.env.CMS_ALLOWED_EMAILS ?? '';
  if (!csv) return false;
  const allowed = csv
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
  return allowed.includes(email.trim().toLowerCase());
}
