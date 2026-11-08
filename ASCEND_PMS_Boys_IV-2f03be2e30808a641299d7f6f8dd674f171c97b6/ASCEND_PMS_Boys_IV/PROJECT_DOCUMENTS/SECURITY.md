# ASCEND Security Model — v1.2 Production Build

## Implemented protections

- PBKDF2-SHA256 password hashing with per-password salts and a high work factor.
- Random opaque session tokens; only token hashes are stored in SQLite.
- `HttpOnly`, `SameSite=Lax`, HTTPS-only production session cookies.
- CSRF token validation on every state-changing request.
- Server-side role and permission checks on all protected routes and mutations.
- Protected **Super Admin** owner level for admin-team management, branding, launch tools and backups.
- Delegated **Staff Admin** permissions for operational areas only.
- Staff admins cannot create/edit/disable/reset other admins or access protected Super Admin pages.
- Login and activation rate limiting by account+IP and by IP.
- Admission records must exist before a student can activate an account.
- One-time activation codes expire and are removed after successful activation.
- Disabling/resetting a student or staff admin invalidates active sessions.
- Point totals are not client-editable; all points are server-side ledger transactions.
- Duplicate challenge awards are blocked by participation award state and unique participation records.
- SQL uses parameterized queries.
- Jinja auto-escaping is used for user-controlled text.
- Security headers include CSP, frame denial, MIME sniffing protection, same-origin referrer policy and HSTS in secure mode.
- Request/body size limits and text length validation reduce abuse.
- Uploaded school logos and student profile pictures accept raster formats only, are image-validated with Pillow, dimension-limited and safely re-encoded before serving.
- Profile pictures are cropped to a controlled 512×512 WEBP asset.
- Audit logs record important administrator actions without recording passwords or student activation codes.
- Backup downloads and production tools require Super Admin authorization.
- Persistent SQLite uses foreign keys, WAL mode and busy timeouts.
- Full backup archives include a consistent DB snapshot plus persistent uploaded profile/branding files.

## Operational security

- Keep `PMS_SECURE_COOKIE=1` in Railway.
- Use a unique 12+ character Super Admin password; longer is better.
- Enable 2FA on Railway and GitHub.
- Grant Staff Admin permissions using least privilege: only enable areas each staff member genuinely needs.
- Remove/disable staff access immediately when it is no longer required.
- Do not share activation-code exports publicly.
- Disable student registration when not actively onboarding students.
- Never commit production environment secrets.
- Download periodic full ZIP backups and keep at least one copy outside Railway.
- Treat student profile images as school data and follow the school’s privacy/photo policy before large-scale use.

## Scope limits

Application hardening reduces common web attacks but cannot guarantee resistance to every attack or large distributed denial-of-service event. Railway/network account security, dependency updates and school operational practices remain part of production security.
