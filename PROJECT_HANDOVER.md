# PROJECT HANDOVER — Delta Academy (ASCEND PMS Boys IV)

**Project:** Delta Academy — the production ASCEND platform for **Peshawar Model School Boys IV** (tagline: *Compete • Achieve • Grow*).
**Repository:** `https://github.com/hilalzahid125-coder/Ascend.academy.git`
**Current branch:** `arena/24938aa0-ascend-academy` (the earlier parent-portal work landed on `arena/794316a6-ascend-academy`)
**Current tip commit:** `0f6b0d6` — "Give academy staff the same downloadable progress report PDF"
**App version:** `1.4.0` (see `VERSION`)
**Live deployment:** Vercel project `delta_academy`, production alias **`deltaacademy-pi.vercel.app`**, latest deployment `dpl_FuemYy2KWsmWe7noMvupE4kcM1Hc` (READY / PROMOTED), built from commit `0f6b0d6`.
**Database:** Supabase PostgreSQL project `ascend-academy` (ref `ezopvhvxbhdvgaasutfd`, region ap-south-1), private `ascend` schema, migrations 001–017 applied.
**Owner:** Abdul Hanan Sethi. This document is the single source of project knowledge for the incoming AI developer.

> **Read this first.** Everything below was verified against the actual repository, deployment, and database state at commit `0f6b0d6`. No features are invented; anything not confirmed is explicitly labeled. This document is documentation-only — it does not change application code.

---

## 1. Project Overview

**Delta Academy (ASCEND)** is a gamified school platform for Peshawar Model School Boys IV. Students compete through challenges, earn category-based points, unlock achievements, climb leaderboards and claim configured rewards. The platform serves **four roles**: Student, Teacher, Staff Admin, and Parent, with a protected **Super Admin** owner level.

**Vision & purpose:** Make school recognition engaging and measurable — students earn real points from real, approved activity; parents see a clear, honest picture of their child's recorded academy activity; teachers and admins manage classes, progress, fees and gamification from no-code interfaces. Everything is driven by the academy's existing record systems — no duplicate data stores, no invented metrics.

**Ecosystem — how the systems work together:**

- **Points ledger** (`point_transactions`) is the single source of truth for all gamification. Points flow from challenges, achievements, teacher records, and admin adjustments. Leaderboards, achievements, and reward thresholds are all *derived* from this ledger — never client-editable.
- **Challenges & participations** (`challenges`, `challenge_participations`) share one system between the student portal and the parent view. A student joins/submits; the Super Admin approves; approval awards points via the ledger and updates the achievement sync. The parent "Challenges & Rewards" page reads the same records (read-only, scoped to their linked child).
- **Progress records** (`student_progress_records`) hold teacher-entered assessments, participation scores, assignments and feedback, with a review workflow (pending → approved/rejected), versioning, and revision (correction) records that supersede old ones.
- **Attendance** (`class_schedules` → `class_sessions` → `class_attendance`) tracks scheduled classes, live/ended sessions, and per-student marks (present/absent/late/excused/pending), with holidays excluded from totals and streaks computed from recorded class days.
- **Fees** (`fee_assignments`, `fee_payments`, `fee_waivers`) are academy-managed. Students and parents view read-only records; parents can submit payment proof through the existing submission flow; Super Admin approves/rejects proofs and authorizes waivers (with reason + reversal).
- **Notifications** (`notifications`) is one shared system for students, parents, and teachers — unread indicators appear in the sidebar bell and topbar for every role.
- **Achievements & rewards** (`achievements`, `student_achievements`, `rewards`, `reward_claims`) use academy-configured point thresholds; parent achievement pages read the exact same records as the student portal.

**Live test accounts (production DB):** Super Admin `ADMIN-0001` (password held by the owner; the `PMS_ADMIN_PASSWORD` env var was **removed on 2026-11-19**, so the account is never silently recreated); parent `P-923741` linked to student `T-923741`. (Local test DBs also use disposable accounts `P-UI123`/`ParentStrong123`, `A-UI123`/`StudentStrong123` — these are test-only.)

---

## 2. Features and Dashboards

All four dashboards share one app shell: a **sidebar menu** (grouped with section dividers), a **topbar** (context, notification bell with unread badge, identity, sign-out), and a **mobile bottom nav**. Navigation between pages is **SPA (single-page)** — handled client-side in `static/app.js` with zero full-document reloads (see §3).

### 2.1 Student portal
- **Overview** (`/student`): score hero, live Top-3 leaderboard, challenge previews, achievements, rewards, recent points, announcements — each preview links to its full page.
- **My Classes** (`/my-classes`): weekly timetable of assigned classes, session attendance marks, and embedded **live classrooms** (Jitsi Meet) for live sessions.
- **Challenges** (`/challenges`): list of active challenges, join and submit evidence; submission review status is shown.
- **Leaderboards** (`/leaderboards`): category leaderboards (Overall/Academic/Sports/Character/Activity/General) with period filters, podium, and ranked table.
- **Achievements** (`/achievements`): earned badges + in-progress milestones with progress bars.
- **Rewards** (`/rewards`): catalog with point thresholds and stock; students submit claims that remain subject to admin review.
- **Notifications** (`/notifications`), **Fee Management** (`/fees` — read-only view + payment-proof submission), **My profile** (`/profile` — photo upload/removal, identity).

### 2.2 Teacher portal
- **Assigned students** (`/teacher`): roster of students the teacher is assigned to.
- **My Classes** (`/teacher/classes`): start live sessions, mark attendance, end sessions.
- **Student progress** (`/teacher/progress`): create/edit progress records (assessment, assignment, feedback), submit for review, revise rejected/approved records. **Participation scoring is retired** — the record type no longer exists in the form or the validator; legacy rows stay in the database but no screen shows them.
- **Teacher feedback inbox** (`/teacher/feedback`, admin equivalent `/admin/feedback`): one entry per approved feedback record with the family's one-tap answer and any follow-up notes. Teachers see their own students (and lose access when a class assignment is revoked); admins with the `students` permission see every student and can publish feedback directly through `/admin/feedback/new`. **Parents never write free text** — they answer with one of four preset replies (`FEEDBACK_ACKS`: thanks / working / done / contact), which keeps staff screens scannable at class scale.
- **Per-student view** (`/teacher/students/{id}`), **notifications**, **account** (`/teacher/account`).

### 2.3 Admin portal
- **Overview** (`/admin`): quick actions into all admin areas.
- **Student progress** (`/admin/teaching`, `/admin/teaching/classes`, `/admin/teaching/students/{id}`): review and approve/reject teacher progress records, revise, class session management (start/end/attendance).
- **Students & points** (`/admin/students`): roster, bulk CSV/XLSX import, activation-code export, per-student points adjustment, status, reset, photo removal, Super-Admin-only permanent deletion.
- **Student report** (`/admin/students/{id}/report` + `.pdf`): the same consolidated approved-record report guardians download; fee sections appear only for staff whose permissions include fees. Guardians reach the identical PDF at `/parent/children/{id}/report.pdf`.
- **My Classes** (`/admin/my-classes`): admin-managed class schedules and sessions.
- **Challenges / Achievements / Rewards / Announcements** (`/admin/challenges`, `/achievements`, `/rewards`, `/announcements`): create, edit, enable/disable; review submissions and reward claims.
- **Leaderboards** (`/leaderboards` shared), **Activity log** (`/admin/activity`), **Reports** (`/admin/reports` + CSV exports).
- **Fee Management** (`/admin/fees`): assign fees, manage payment methods, review payment proofs (approve/reject with note), authorize waivers with reason and reversal.
- **Admin team** (`/admin/admins`, Super Admin only): create Staff Admins with configurable permissions, edit, disable, reset password.
- **Parent accounts** (`/admin/parents`, Super Admin only): create parents, link/unlink students, update, reset password.
- **Teachers** (`/admin/teachers`), **Academy holidays** (`/admin/holidays`), **Brand & settings** (`/admin/settings` — app name, tagline, school identity, registration, academic session/terms), **Launch & backups** (`/admin/launch` — prepare-production, install-structure, purge-demo, manual/scheduled backups, restore), **My admin account** (`/admin/account`).

### 2.4 Parent portal (fully built, the most recent work)
Every page lives in the **sidebar menu** (not stacked in the overview). The overview is a **summary hub**.
- **Overview** (`/parent`): welcome banner with multi-student switcher, student profile card, an **at-a-glance** stat strip (Overall performance, Attendance, Current learning streak, Total achievements, **Teacher feedback** (unreplied count with a link to the conversation page), Total points, Leaderboard position, Pending assignments, Outstanding fee balance), and links into notifications / upcoming classes / announcements.
- **STUDENT section:** **Classes** (`/parent/children/{id}/classes` — weekly timetable grid), **Attendance** (`/parent/children/{id}/attendance` — stats, monthly calendar with marks, streaks, records), **Progress report** (`/parent/children/{id}/report` + `.pdf` download), **Teacher feedback** (`/parent/children/{id}/feedback` — approved feedback notes: teacher, subject, category, the note itself, any academy follow-up notes, and a one-tap reply bar (changing an earlier answer replaces it); awaiting-reply state per note), **Analytics** (`/parent/children/{id}/analytics` — charts, donuts, heat map, trends).
- **RECOGNITION section:** **Leaderboard** (`/parent/children/{id}/leaderboard` — child highlighted, filters, podium, rankings), **Achievements** (`/parent/children/{id}/achievements`), **Challenges & Rewards** (`/parent/children/{id}/challenges-rewards` — parent-relevant view; internal challenge fields pruned).
- **FINANCE section:** **Fees** (`/parent/children/{id}/fees`), **Fee record** (`/parent/children/{id}/fees/{fee_id}`), **Payment / proof submission** (`/parent/children/{id}/fees/{fee_id}/pay`, `/submit`), voucher PDF, payment-proof download.
- **ACCOUNT section:** **Notifications** (`/parent/notifications`), **My account** (`/parent/account` — profile details, linked students, password change).

### 2.5 Public / shared
Landing page (`/`), About (`/about`), Privacy (`/privacy`), login (`/login`, `/parent/login`), register (`/register`), academy signup (`/register/academy`), health (`/health`), scheduled backup cron (`/internal/scheduled-backup`).

---

## 3. Technical Architecture

### 3.1 Technology stack
- **Backend:** Python 3.11+ / **FastAPI** (server-rendered HTML via Jinja2), **uvicorn**.
- **Frontend:** Jinja2 templates + vanilla CSS + a small vanilla-JS SPA navigation layer (`static/app.js`). No JS framework in the main app. One separate **React 19 + Vite + Tailwind v4** subproject for the academy signup UI (`academy_signup/`), whose build output is served from `static/academy-signup`.
- **Database:** **PostgreSQL** on Supabase (primary, production) via `psycopg[binary]` + `psycopg_pool`; **SQLite** fallback for local/dev/tests. The app uses one SQL dialect with a converter (`pg_adapter.py`) that maps SQLite `?` placeholders and double-quoted literals to PostgreSQL without interpolating values.
- **PDF:** reportlab (progress report PDF, fee voucher PDF).
- **Images:** Pillow (profile pictures cropped to 512×512 WEBP; logo re-encoded safe PNG; SVG disabled for uploads).
- **Spreadsheets:** openpyxl (XLSX roster import).

### 3.2 App assembly (critical, unusual)
The application is **assembled at runtime from fragment files**:

- `app.py` (root of the project dir) concatenates **all `app_parts/part*.pyfrag` files in sorted order** and `exec()`s them into one module, then `exec()`s `app_v14_patch.py` on top.
- `app_parts/part01.pyfrag` … `part12.pyfrag` are the route/logic fragments (part01 = app setup, helpers, static mount; part02 = public/auth/landing; part03 = student challenges/leaderboards/notifications/achievements; part04 = admin/profile; part05 = admin reports/students; part06 = admin challenges/achievements; part07 = admin rewards/announcements; part08 = launch/backups/security/health; part09 = My Classes + class session management; part10 = fees (student + parent); part11 = parent accounts, parent core pages, report, helpers; part12 = parent leaderboard/achievements/challenges-rewards/fees/notifications/analytics).
- `app_v14_patch.py` defines `APP_VERSION = '1.4.0'`, the central `render()` helper (injects request/settings/user/csrf/unread context into every template), and the redesigned `/student` route (it removes the old route and re-registers the new one).
- **Fragments are intentionally NOT standalone-compilable.** Always validate by running the assembled `app.py` (e.g. `python -m py_compile app.py`), never by compiling an individual fragment.

### 3.3 Folder structure (project dir = `ASCEND_PMS_Boys_IV-.../ASCEND_PMS_Boys_IV/`)
```
app.py                 # runtime assembler: concatenates app_parts/*.pyfrag + app_v14_patch.py
app_v14_patch.py       # APP_VERSION, render(), redesigned /student route
app_parts/             # part01..part12.pyfrag route/logic fragments
api/index.py           # Vercel ASGI entry: init_db(), ensure_admin(), super-admin check
db.py                  # SCHEMA (all tables), connect(), init_db(), helpers, PG/SQLite selection
pg_adapter.py          # SQLite→PostgreSQL SQL converter + connection pool
security.py            # PBKDF2 hashing, tokens, activation codes, time helpers
backups.py             # full ZIP backups (DB + uploads), scheduled-backup logic
uploads.py             # upload serving/storage helpers
competition.py         # seed achievement/challenge/reward templates (drafts)
db, academy_signup/    # React/Vite registration UI source (build → static/academy-signup)
templates/             # all Jinja2 templates (base.html + per-page)
static/                # CSS (design-system.css, style.css, v12-14, parent.css, fees.css, ...), app.js, fees.js, live-classes.js, icons.svg, fonts/
supabase/migrations/   # 001–017 idempotent SQL migrations (also run at app init)
scripts/               # create_admin.py, restore_postgres_backup.py
tests/test_core.py     # 99 tests (SQLite; some PG/skip-gated)
requirements.txt / pyproject.toml / Dockerfile / vercel.json / VERSION
PROJECT_DOCUMENTS/     # legacy per-topic docs (superseded by this handover where noted)
```

### 3.4 Routing
All routes are defined across the `app_parts` fragments (see §2 for the full map). Server-side, every protected route calls `require_user(request, role)` / `require_admin(request, permission)`; authorization is enforced server-side on every route and mutation — hidden navigation is never treated as security. Client-side, `static/app.js` intercepts internal link clicks and form GETs within the app shell and fetches the next page's HTML, swapping only `#main-content` (and the sidebar nav + topbar), pushing history state, and dispatching `ascend:page-loaded`. The SPA allowlist (`isPage`) covers student/admin/parent pages plus `/fees/{id}/pay` and all `/parent/children/{id}/...` paths. **When adding a new internal page, add its path to the `pages` set in `static/app.js`** so navigation stays instant.

### 3.5 Backend APIs
The app is server-rendered; there is **no separate JSON API layer**. Interactions are HTML form POSTs (with CSRF tokens) that redirect (303) back to the relevant page, plus a few file endpoints (PDFs, CSV, receipts, vouchers, backups) and `/health` (JSON). A handful of endpoints return JSON or redirects (e.g. live-classroom room creation `POST /my-classes/live/{session_id}/room`).

### 3.6 Database schema (verified in `db.py` SCHEMA)
Core tables: `users` (roles: student/teacher/parent/admin; admin_level, admin_permissions JSON for staff admins), `sessions`, `auth_attempts`, `parent_student_links`, `academy_signup_profiles`, `class_schedules` (self-referencing parent for overrides, recurrence weekly/once), `class_sessions`, `class_attendance`, `academy_holidays`, `class_live_rooms`, `student_progress_records` (kind: assessment/assignment/feedback, score, score_max, status, review fields, version, replaces_id for revisions), `feedback_messages` (answers and follow-up notes on an approved feedback record: author, author_role parent/teacher/admin, body, created_at — parent rows hold one of the `FEEDBACK_ACKS` codes, at most one per note), `academic_terms`, `fee_methods`, `fee_assignments`, `fee_payments`, `fee_waivers`, `point_transactions` (user_id, amount, category, reason — the ledger), `challenges`, `challenge_participations`, `achievements`, `student_achievements`, `rewards` (quantity stock), `reward_claims`, `announcements`, `notifications`, `audit_logs`, `settings`, plus `ascend.app_schema_migrations` ledger used by the cold-start runner. Key constraints: unique participation, award-state duplicate protection, reward stock limits, fee edit/waive history guards. Foreign keys ON, WAL mode for SQLite.

### 3.7 Authentication, roles & permissions
- **Passwords:** PBKDF2-HMAC-SHA256, 310,000 rounds, per-password salt (`security.py`).
- **Sessions:** opaque random tokens; only SHA-256 token hashes stored (`sessions`); `HttpOnly`, `SameSite=Lax`, HTTPS-only in production (`PMS_SECURE_COOKIE=1`).
- **CSRF:** double-submit token (`pms_csrf` cookie + form field) on every state-changing request.
- **Roles:** student, teacher, parent, admin. Admin has two levels: **Super Admin** (protected, `admin_level='super'`) and **Staff Admin** with a JSON permission list (`admin_permissions`) covering operational areas (teaching, students, classes, challenges, achievements, rewards, announcements, leaderboards, activity, reports, fees).
- **Rate limiting:** login/activation throttled by account+IP and by IP (`auth_attempts`).
- **Permission enforcement:** server-side on every route/mutation; Super-Admin-only areas (admin team, brand & settings, launch & backups, parent accounts, holidays, teachers, fee waivers) are guarded and hidden from staff admins.

### 3.8 Integrations, GitHub & deployment
- **GitHub:** repo `hilalzahid125-coder/Ascend.academy`. Work happens on branch `arena/794316a6-ascend-academy` (branched from `main` @ `550ec7c`). Push to this branch, then deploy from it.
- **Vercel:** single project `delta_academy` (`prj_tJG0Ubdg30E6T68KkPrbOvrSwmEM`), team `team_s51P38wvTjBOe7LnO3eSRh1w`, **root directory = the nested project dir** `ASCEND_PMS_Boys_IV-2f03be2e30808a641299d7f6f8dd674f171c97b6/ASCEND_PMS_Boys_IV`. Entry: `api/index.py` (ASGI). `vercel.json` sets the function `includeFiles` glob `{*.py,app_parts/**,templates/**,static/**,supabase/migrations/**,VERSION}`, `maxDuration: 60`, and a daily cron `0 2 * * *` → `/internal/scheduled-backup`. **One project serves the entire app (admin + student + teacher + parent).**
- **Supabase:** project `ascend-academy` (ref `ezopvhvxbhdvgaasutfd`), PostgreSQL, private `ascend` schema, `anon`/`authenticated` direct access revoked. Migrations 001–017 are idempotent and are also applied by the app at cold start.
- **Environment variables (server-side, Vercel):** `PMS_DATABASE_URL` (Supabase PG connection string), `CRON_SECRET` (scheduled backup auth), optional `PMS_BACKUP_RETENTION` (default 14) and `PMS_BACKUP_INTERVAL_HOURS` (default 24). **Never commit or share these.** `PMS_ADMIN_PASSWORD` was **removed on 2026-11-19**: `api/index.py` bootstraps the Super Admin only while that variable exists, and the live account already does, so deleting the account can no longer be undone by a cold start.
- **Deployment procedure:** commit + push to your session's working branch, then create a production deployment from the branch via the Vercel connector (repoId `1450157897`). After verifying, the new deployment is promoted and `deltaacademy-pi.vercel.app` aliases to it.
- **Railway/Docker (alternative, legacy):** `Dockerfile` runs uvicorn on port 8000 with a `/data` volume; SQLite-based. The production deployment is now Vercel + Supabase PG; Railway config remains for reference.

---

## 4. Design and UX

**Visual identity — "Delta Academy green":**
- Primary color **`#087f63`** (deep green), dark `#075c49`, soft `#e8f5f0`, mint `#d1eee5`; ink `#17252b`, muted `#64748b`, line `#e2e8f0`. (Note: legacy docs describe an "orange" palette — the current, active design system in `static/design-system.css` is **green**.)
- **Typography:** Inter (self-hosted woff2 in `static/fonts/`), system fallback. Eyebrow labels (uppercase, letter-spaced), tight heading letter-spacing (`-0.025em`).
- **Layout:** 236px sidebar + main content shell; panels (`border-radius:12px`, subtle shadow), stat cards, home sections, badges, progress bars, tables. `.role-admin .sidebar nav a.active` is dark inverted for admins.
- **Reusable components/classes:** `.panel`, `.home-section`, `.fee-entry`, `.fee-stats`, `.stat-card`, `.progress`, `.btn` (primary/ghost/small/danger), `.badge`, `.notification-row`, `.empty`, `.parent-*` (parent-specific), `.analytics-*` (charts), `.parent-calendar`, `.parent-week-grid` (timetable). Icons are inline SVG referencing `static/icons.svg` sprite (ids: house, book-open, users-round, swords, trophy, gift, megaphone, bell, wallet, award, graduation-cap, sparkles, shield-check, settings, database-backup, user-round, etc.).
- **Parent-specific CSS:** `static/parent.css` (currently `?v=10`) — sidebar hover accents, overview grid, timetable, attendance calendar, analytics, awards, feedback conversations. **When changing `parent.css`, bump the `?v=` in `templates/base.html`.**
- **Cache-busting:** `templates/base.html` loads `app.js?v=academy-12`, `fees.js?v=4`, `live-classes.js?v=1`, and `parent.css?v=9`. **Bump the version query whenever the corresponding file changes** so browsers fetch the new asset.
- **Responsive:** sidebar becomes a slide-in drawer under 820px (overlay, swipe gestures, Escape, body scroll lock); mobile bottom nav shows 4 quick actions per role (parents: Home / Fees / Notifications / Account). Reduced-motion supported.
- **Established decisions that must remain consistent:** green-first palette; Inter; sidebar + topbar shell; SPA navigation with no full reloads; parent overview is a summary hub with sections only in the sidebar; charts/visual indicators preferred over dense numbers on analytics; simple professional wording; parent views must never expose internal/admin-only data (e.g. data-challenge internals were pruned from the parent Challenges page).

---

## 5. Development Status

**Overall: core application complete and deployed. Parent portal fully built. Remaining work is operational/roadmap (§8).**

| Area | Status |
|---|---|
| Student portal (auth, classes, challenges, leaderboards, achievements, rewards, notifications, fees, profile) | **COMPLETE** |
| Teacher portal (classes, live sessions, progress records, review/revise) | **COMPLETE** |
| Admin portal (students, challenges, achievements, rewards, announcements, reports, fees, admin team, parents, teachers, holidays, settings, launch, backups) | **COMPLETE** |
| Parent portal — sidebar restructure + SPA nav + summary overview | **COMPLETE** (deployed, browser-verified) |
| Parent portal — full account page, clean back-links, parent wording | **COMPLETE** (deployed, latest commit `a15bbd1`) |
| PostgreSQL (Supabase) as production DB | **COMPLETE & deployed** (migrations 011–017 made re-run-safe; 500 bug fixed) |
| Vercel single-project deployment | **COMPLETE** (`deltaacademy-pi.vercel.app`, user confirmed admin login works) |
| Regression tests | **COMPLETE** — 99 tests; last run SQLite 91 passed / 9 skipped, PostgreSQL 99 passed |
| Real school roster onboarding | **NOT STARTED** — waiting on school approval / real data |
| Official school crest | **OPTIONAL / WAITING FOR ASSET** (branding uploadable via Super Admin) |
| Official custom domain | **DEFERRED** — waiting on school DNS access |
| `PMS_ADMIN_PASSWORD` removal from Vercel env | **DONE 2026-11-19** — variable deleted and redeployed (`dpl_FuemYy2KWsmWe7noMvupE4kcM1Hc`); `/health` responds without it, boot no longer recreates accounts |
| Participation scoring removed + teacher feedback with one-tap parent replies | **COMPLETE** — migration `018_feedback_conversations.sql`, new routes and pages, tests green |
| `academic_terms` seed data | **DONE 2026-11-19** — academic session `2026-2027` (2026-04-01 → 2027-03-31) plus First Term, Second Term and Final Term in production; editable in Super Admin → Brand & settings |
| Day-1 backup archive confirmation (cron) | **NOT VERIFIED** — confirm a scheduled backup was produced |

**Verified working (last validation, commit `0f6b0d6`):** SQLite suite 91 passed / 9 skipped; 40/40 pages across student, teacher, admin, parent and guest roles returned HTTP 200 at `0261122`; PostgreSQL suite 99 passed at `a15bbd1`; Playwright browser check — all 11 parent sidebar pages navigate via SPA with zero document reloads; admin login confirmed working on the live `deltaacademy-pi.vercel.app` by the owner.

**Not verified / cannot confirm from the sandbox:** live HTTP responses from the sandbox to Vercel return HTTP `000` (sandbox limitation — verify via browser/connectors, not curl). The 9 skipped tests are PG-only/restore/environment-gated tests.

---

## 6. Development History

**Key decisions:**
- One shared database (PostgreSQL on Supabase in production; SQLite for local/tests) with a SQL converter (`pg_adapter.py`) rather than two code paths.
- App assembled from `app_parts/*.pyfrag` fragments + `app_v14_patch.py` (keeps the loader compact; fragments are not individually compilable).
- SPA navigation in vanilla JS (`static/app.js`) — no full-page reloads; the allowlist must be extended for every new internal route.
- Gamification is ledger-derived: points, leaderboards, achievements and reward thresholds all read `point_transactions`; nothing is client-editable.
- Parent views are read-only over shared records (no separate fee/challenge/achievement databases), reusing the existing student challenge/reward/fee systems.
- Parent portal restructured (latest): all parent pages in the sidebar, overview as a summary hub, instant SPA navigation, green hover accents, parent-unnecessary internals pruned.

**Resolved problems:**
- **500 FUNCTION_INVOCATION_FAILED (cold start):** the cold-start `init_db()` re-ran Supabase-applied migrations; 011/012/014 (bare `ADD CONSTRAINT`) and 017 (bare `ADD COLUMN`) raised duplicate_object/duplicate_column. Fixed by making migrations 011–017 re-run-safe (commit `4712e28`), redeployed, admin login confirmed working.
- **12 failing SQLite tests after the parent restructure:** tests asserted the old stacked-overview markup for functionality moved to dedicated section pages. Fixed by repointing assertions to the new routes/markup while preserving test intent (attendance section ported to its own route/page; fee/challenge/participation/admin-teaching/overview assertions updated). Final: 90 passed / 9 skipped.
- **`enumerate` undefined in Jinja:** `parent_classes.html` used `enumerate(weekdays)`; replaced with `loop.index0` + `{% for label in weekdays %}`.
- **`/parent/notifications` triggered a full reload:** missing from the SPA allowlist; added to the `pages` set in `app.js`, cache-bust bumped to `academy-12`.
- **Broken back-links:** section pages linked to old dashboard anchors (`#parent-recognition`, `#parent-fees`) that no longer exist after the overview redesign; updated to plain `/parent?child={id}`.
- **Parent wording on shared payment page:** "Back to Fee Management" shown to parents; made context-aware ("Back to fees").

**Rejected/dead-end approaches (do not retry):**
- Do not compile individual `app_parts/*.pyfrag` fragments — they rely on the assembled context.
- Do not run `pkill -f chrome` (self-kills) — use `[c]hrome` pattern; Playwright needs `LD_LIBRARY_PATH=/tmp/al2023/lib`.
- Do not rely on curl from the sandbox to verify Vercel (HTTP `000`) — use connectors/browser.
- Do not split the app into multiple Vercel deployments — one project serves everything.

**User standing instructions (must keep honoring):** keep the parent portal in the sidebar (not stacked); instant SPA navigation; best professional design with green hover accents; simple wording; remove parent-irrelevant internal content; parent financial access read-only over existing records; parent achievements/challenges/rewards tied to the real student systems (no invented badges or separate mechanisms); Step-10 redemption follows existing approval/validation rules; notification unread indicators for all roles via the one existing system; analytics must be beautiful and chart-driven from real records; deploy the whole app to the one existing Vercel project.

---

## 7. Exact Stopping Point

Development stopped **at the completion of the Parent Portal scope**, on branch `arena/794316a6-ascend-academy` at commit **`a15bbd1`** ("Complete parent portal scope: full account page, clean back links, parent wording"), deployed as **`dpl_E4eKARzeeeTc7A6ziD8FrroU2Vk8`** (READY/PROMOTED, alias `deltaacademy-pi.vercel.app`).

**Latest relevant files (all current as of the stop):**
- `templates/parent_dashboard.html` — summary-hub overview (welcome banner, profile card, at-a-glance strip, notices/classes/announcements linking out).
- `templates/parent_account.html` — full account page (profile details, linked students, password change).
- `templates/parent_classes.html`, `parent_attendance.html`, `parent_feedback.html` — section pages (`parent_participation.html` was deleted with the feature).
- `templates/parent_leaderboard.html`, `parent_achievements.html`, `parent_challenges_rewards.html`, `parent_fees.html`, `parent_fee_detail.html`, `parent_report.html`, `parent_notifications.html`, `parent_analytics.html` — section pages (back-links cleaned).
- `templates/base.html` — parent sidebar full menu + mobile bottom nav; `app.js?v=academy-12`.
- `static/app.js` — SPA navigation; `pages` set includes `/parent/notifications`.
- `static/parent.css` (v9) — parent styles, including the ≤680 px phone rules for the child switcher and page headers.
- `app_parts/part11.pyfrag` / `part12.pyfrag` / `part10.pyfrag` — parent routes (all child-scoped render contexts pass `parent_child_id`).
- `tests/test_core.py` — all parent tests updated to the new routes.

**Immediate next steps (not yet done, deliberately deferred):**
1. ~~Remove `PMS_ADMIN_PASSWORD` from Vercel env and redeploy~~ — **DONE 2026-11-19**.
2. ~~Configure real `academic_terms`~~ — **DONE 2026-11-19** (session `2026-2027`, three terms).
3. Confirm the day-1 scheduled backup (cron `0 2 * * *`) produced an archive — still open; archives currently land roughly every two days.
4. Onboard the real student roster / parents / teachers when the school approves.
5. No code changes are pending — the app is feature-complete per the current scope.

---

## 8. Future Roadmap (priority order)

**P0 — Operational safety (do first, no code risk):**
1. ~~Verify admin login + core flows on the live deployment; then remove `PMS_ADMIN_PASSWORD` from Vercel and redeploy.~~ — **DONE 2026-11-19.**
2. Confirm scheduled backups are actually produced; download a full archive and keep an off-site copy; verify restore in an isolated DB with `scripts/restore_postgres_backup.py`.
3. ~~Configure real `academic_terms`~~ — **DONE 2026-11-19**. Remaining: real fee methods, challenges, achievements and rewards configured in the Super Admin panel.

**P1 — Real-data onboarding (school-dependent):**
4. Bulk-import the real student roster (CSV/XLSX), distribute activation codes privately, enable registration only during onboarding.
5. Create Staff Admins with least privilege; create teacher and parent accounts; link parents to students.

**P2 — Polish & production readiness:**
6. Accessibility/UX review across all four portals; verify SPA navigation on every new page added (keep the `pages` allowlist updated).
7. Performance: reduce duplicate DB lookups in shared page renders (already partially done); review cold-start time.
8. Consider dedicated object storage + managed off-site backups as data grows (current PG-stored backups share DB quota).
9. Optional: official school crest upload via Super Admin branding; official custom domain once DNS is available.

**Dependencies & sequence:** P0 is independent and safe. P1 depends on school approval and the roster. P2 items depend on real usage feedback. **Testing requirements for any change:** run `tests/test_core.py` on SQLite (expect ≥90 passed / 9 skipped) and the PostgreSQL suite (expect 99 passed); for UI changes run the Playwright browser checks (seed with `/tmp/ascend-step7-browser-setup.py`, server on port 8006, `LD_LIBRARY_PATH=/tmp/al2023/lib`); always `python -m py_compile app.py db.py api/index.py` before deploying; bump the `?v=` cache-bust for any changed CSS/JS in `base.html`.

---

## 9. Incoming AI Instructions

You are continuing an existing, deployed, working application. **Do not restart, re-architect, or redesign what is already built.** The owner (Abdul Hanan Sethi) wants the best possible professional experience with no mistakes and no data loss.

**Preserve:**
- The assembled-fragment architecture (`app.py` + `app_parts/*.pyfrag` + `app_v14_patch.py`). Add new routes as new fragments or additions to existing ones; never restructure into a build step unless asked.
- The green design system (`static/design-system.css`, `static/parent.css`), the sidebar+topbar shell, and SPA navigation (`static/app.js`). Keep the green hover accents and clean, simple, professional wording.
- The shared-record principle: parent/student/teacher/admin views read the **same** database records; do not create parallel data stores for fees, challenges, achievements, or notifications.
- The auth/permission model (Super Admin vs Staff Admin, role guards on every route). Never weaken server-side authorization.
- The single-Vercel-project deployment and the Supabase PG database. Never split deployments or lose the DB connection.

**How to work safely:**
1. Always work on branch `arena/794316a6-ascend-academy`; push only to it.
2. Validate with `python -m py_compile app.py db.py api/index.py`, then `pytest tests/test_core.py` (SQLite) and the PG suite before any deploy.
3. For every new internal page, add its path to the `pages` set in `static/app.js`; bump the `?v=` cache-bust in `templates/base.html` for changed CSS/JS.
4. For every new parent child-scoped route, pass `parent_child_id` in the render context (the sidebar/mobile-nav guard depends on it).
5. Deploy by pushing the branch and creating a production Vercel deployment from it; verify READY/PROMOTED and the `deltaacademy-pi.vercel.app` alias.
6. Never expose secrets/API keys/passwords in code, docs, or chat. Verify live behavior via the browser or the Vercel/Supabase connectors (sandbox curl to Vercel returns HTTP `000`).
7. When in doubt, read the actual code and templates first — this document is a map, not the territory. Confirm anything marked "cannot verify" before acting on it.

**Improve consistently:** small, focused, well-tested increments that respect the existing design and data model. If you must change an established design decision, note it and keep it consistent across all four portals.

---

## FIRST ACTION FOR THE NEXT AI

**Step 1 — Orient.** Clone/inspect the repo at `hilalzahid125-coder/Ascend.academy`, branch `arena/24938aa0-ascend-academy` (tip `0f6b0d6`; earlier parent-portal work is on `arena/794316a6-ascend-academy` at `a15bbd1`). Read this document, then `README.md`, `app.py`, `db.py`, `app_v14_patch.py`, and skim `app_parts/part*.pyfrag` to see how routes are assembled.

**Step 2 — Verify the live baseline (do not change anything yet).** Confirm the production deployment `dpl_FuemYy2KWsmWe7noMvupE4kcM1Hc` on `deltaacademy-pi.vercel.app` is READY/PROMOTED and that admin login works (Super Admin `ADMIN-0001`; the password is held by the owner — the `PMS_ADMIN_PASSWORD` env var no longer exists). Confirm the Supabase `ascend` schema has migrations 001–017 applied.

**Step 3 — Run the safety checks.** From the project dir (`ASCEND_PMS_Boys_IV-2f03be2e30808a641299d7f6f8dd674f171c97b6/ASCEND_PMS_Boys_IV`): `python -m py_compile app.py db.py api/index.py`, then the SQLite suite (`pytest tests/test_core.py` → expect 91 passed / 9 skipped) and the PostgreSQL suite (expect 99 passed). Fix only if these fail.

**Step 4 — Execute the deferred operational items (P0), in order:**
1. ~~Remove `PMS_ADMIN_PASSWORD` from Vercel env and redeploy~~ — **DONE 2026-11-19**.
2. **Confirm the scheduled backup** (cron `0 2 * * *` → `/internal/scheduled-backup`) has produced an archive; if not, investigate `backups.py` and `CRON_SECRET`, then download a full backup off-site.
3. ~~**Configure real `academic_terms`** in Super Admin → Brand & settings~~ — **DONE 2026-11-19**.

**Step 5 — Then continue the roadmap (§8)** in priority order, using the testing requirements there for every change, and keeping all the preservation rules in §9.

**If you only do one thing:** get the project running locally, confirm the tests pass, and verify the live deployment — then proceed with the P0 operational items above. The application itself is feature-complete; your job is to safeguard it, onboard real data when the school approves, and improve it consistently without breaking what already works.
