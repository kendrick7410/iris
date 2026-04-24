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

export function verifyClientPrincipal(headerValue: string | null | undefined): Principal {
  if (!headerValue) {
    throw new Error('missing x-ms-client-principal header');
  }
  // TODO: decode base64 → JSON → validate shape → return Principal
  // TODO: extract email from userDetails OR from claims (emailaddress claim)
  // TODO: extract displayName from 'name' claim, fallback to userDetails
  throw new Error('NOT_IMPLEMENTED: verifyClientPrincipal');
}

/**
 * Check whether the authenticated email is allowed to commit.
 * Reads CMS_ALLOWED_EMAILS (CSV) from env. Case-insensitive match.
 */
export function isAllowlisted(email: string): boolean {
  // TODO: parse process.env.CMS_ALLOWED_EMAILS, normalise, compare
  throw new Error('NOT_IMPLEMENTED: isAllowlisted');
}
