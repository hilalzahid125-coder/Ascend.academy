# Changelog

## v1.4 — Final QA, mobile navigation & student-home redesign

- Redesigned the student home page around the user score, live Top 3 leaderboard, challenge previews, achievements, rewards, recent points and announcements.
- Added direct working calls-to-action from each home preview to its full page.
- Made student profile pictures circular across the top bar, profile page, leaderboards, podiums and admin student directory.
- Added a mobile navigation backdrop: tapping outside the drawer now closes it.
- Added swipe-left-to-close and edge-swipe-right-to-open gestures, Escape support, body scroll locking and a visible mobile close button.
- Fixed student rank calculations so disabled accounts no longer affect active leaderboard rank.
- Added Super Admin-only permanent student deletion with linked student data removed by database cascades and the stored profile image cleaned up.
- Reduced duplicate database lookups while rendering shared pages.
- Added cache-busting for v1.4 CSS/JS assets.
- Expanded the regression suite to **16/16 passing** tests, including dashboard previews, drawer behavior, circular avatars and protected student deletion.
- Verified SQLite integrity and foreign-key integrity with no errors.

## v1.3 — Final presentation polish & reporting

- Added a professional public landing page at `/` while preserving role-aware redirects for signed-in users.
- Added public About and Privacy pages suitable for school presentation and pilot use.
- Added a protected Admin Reports center.
- Added downloadable student progress CSV report with overall and category totals.
- Added downloadable challenge participation CSV report with award/review status.
- Enforced report access using existing Staff Admin permissions on the server.
- Added app version, database size, upload count and latest-backup status to the Super Admin launch center without exposing sensitive paths.
- Added ASCEND version to the health endpoint.
- Added public/auth footer navigation and clearer product/version identity.
- Added skip-to-content accessibility support and small mobile navigation polish.
- Expanded regression suite to **12/12 passing** tests.

## v1.2 — Profiles, admin delegation & full backups

- Added student profile pictures with safe raster-only upload, dimension limits, square cropping and WEBP re-encoding.
- Added profile photos to student identity areas and leaderboards.
- Added protected **Super Admin** and delegated **Staff Admin** levels.
- Added Super Admin-only Admin Team control center.
- Added configurable Staff Admin permissions for Students & Points, Challenges, Achievements, Rewards, Announcements and Activity Log.
- Added server-side permission enforcement; hidden navigation alone is never treated as security.
- Added staff-admin enable/disable, permission editing and password reset with session invalidation.
- Added My Admin Account page and password-change flow for both Super Admin and Staff Admin.
- Protected Brand & settings, Launch & backups and admin management from Staff Admins.
- Upgraded backups from DB-only files to full ZIP archives containing a consistent database snapshot plus uploaded branding/profile images.
- Polished admin navigation, user identity/avatar presentation and role-aware dashboard actions.
- Expanded regression suite to **9/9 passing** tests, including delegated permissions and profile-image processing.

## v1.1 — Launch hardening

- Added bulk CSV/XLSX student import (up to 2,500 rows at a time).
- Added downloadable import template and activation-code export.
- Added stronger 8-character one-time activation codes and 30-day expiry.
- Added production-safe registration default (closed until roster is ready).
- Added automatic database migrations for existing Railway databases.
- Added CSRF protection to state-changing requests.
- Added account/IP authentication rate limiting.
- Added security headers, request limits and stricter server-side input validation.
- Hardened school-logo upload: SVG disabled, real image validation, dimension limit, safe PNG re-encoding.
- Reset/disable now invalidates student sessions.
- Removed activation codes from audit-log details.
- Added automatic rolling database backups, manual backup/download and pre-cleanup safety backups.
- Added Admin → Launch & backups control center.
- Added known-demo cleanup with typed confirmation and automatic backup.
- Added real competition starter structure: category achievements, draft challenge templates and inactive configurable reward milestones.
- Added administrator password-change screen with other-session invalidation.
- Switched SQLite to WAL/busy-timeout configuration for better reliability.
- Removed production demo seed/run files.
- Expanded regression suite from 2 to 5 tests.

## v1.0 — Deployment candidate

Initial student/admin auth, points ledger, challenges, leaderboards, achievements, rewards, announcements, notifications, audit log, branding controls and Railway deployment support.
