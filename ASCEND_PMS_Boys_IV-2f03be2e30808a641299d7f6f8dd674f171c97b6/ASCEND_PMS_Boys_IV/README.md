# ASCEND — PMS Boys IV

**Peshawar Model School Boys IV**  
**Compete • Achieve • Grow**  
**Made by Abdul Hanan Sethi**

ASCEND is a production-oriented school challenge, points, rewards and leaderboard platform with separate student, staff-admin and Super Admin experiences.

## What is included

- Admission-number student activation and secure login
- Student profile pictures with safe server-side image processing
- Protected **Super Admin** owner account
- Delegated **Staff Admin** accounts with configurable operational permissions
- Bulk student import from **CSV or Excel (.xlsx)**
- One-time activation codes with expiry and activation-code export
- Point transaction ledger and category leaderboards
- Challenges, submissions, approval and duplicate-award protection
- Achievements, rewards, announcements and notifications
- Admin audit log and no-code branding controls
- Production launch center for demo cleanup, competition setup and backups
- Automatic **full ZIP backups** containing the database plus persistent uploaded branding/profile pictures
- CSRF protection, login/activation rate limiting, security headers, input limits and hardened image uploads
- Professional public landing page, About and Privacy pages
- No-code CSV reports for student progress and challenge participation
- Super Admin system/version/storage status panel
- Railway/Docker deployment support

## Admin hierarchy

The bootstrap admin (`PMS_ADMIN_ID`, normally `ADMIN-0001`) is the **Super Admin**. It has protected access to:

- Admin-team management
- Staff-admin permissions and password resets
- Brand & registration settings
- Launch/cleanup tools
- Backups
- All normal operational areas

Staff admins can be created from **Admin → Admin team**. The Super Admin can grant or remove access to:

- Students & points
- Challenges & submissions
- Achievements
- Rewards
- Announcements
- Activity log

Staff admins can never manage other admins or open protected Super Admin settings.

## Production deployment

The deployed app should use a Railway persistent volume mounted at `/data`.

Required variables:

```text
PMS_ADMIN_ID=ADMIN-0001
PMS_ADMIN_NAME=School Administrator
PMS_ADMIN_PASSWORD=<long unique bootstrap password>
PMS_SECURE_COOKIE=1
PMS_TRUST_PROXY_HEADERS=1
PMS_DATA_DIR=/data
PMS_BACKUP_ENABLED=1
PMS_BACKUP_INTERVAL_HOURS=24
PMS_BACKUP_RETENTION=14
```

`PMS_ADMIN_PASSWORD` is a **bootstrap** password: it creates the Super Admin only if that record does not already exist. After first setup, change the password from **Admin → My admin account**.

## Bulk roster format

```text
Admission Number,Full Name,Class,Section
A-7001,Student Name,10,A
```

A downloadable template is available inside the admin panel.

## Backups

ASCEND creates a full ZIP backup automatically (24 hours by default), retains the latest configured number of backups, and creates safety backups before sensitive cleanup/setup actions. Each new backup contains:

- A consistent SQLite database snapshot
- Uploaded student profile pictures
- Uploaded school branding files

The automatic copies live on the Railway persistent volume. For stronger disaster recovery, periodically download one and keep a copy outside Railway.

## v1.3 presentation release

v1.3 adds a public homepage, About and Privacy pages, protected CSV reports, app/storage status in the Super Admin launch center, versioned health status, accessibility improvements and final presentation polish. It does not change the core database model or onboarding workflow.

## Tests

```bash
pytest -q
```

The v1.3 release was verified with **12 passing regression tests** covering authentication, CSRF/security headers, role protection, duplicate challenge awards, bulk onboarding, activation exports, production preparation, hardened uploads, rate limiting, delegated staff-admin permissions, profile-picture processing, public presentation pages, protected CSV reports, and system/version status.
