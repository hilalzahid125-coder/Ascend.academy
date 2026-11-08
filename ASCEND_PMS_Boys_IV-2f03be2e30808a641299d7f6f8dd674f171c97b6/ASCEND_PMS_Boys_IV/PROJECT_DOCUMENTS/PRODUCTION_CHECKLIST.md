# Production Checklist

## Application
- [x] Student activation + login
- [x] Super Admin login + protected owner controls
- [x] Staff Admin creation and delegated permissions
- [x] Student profile pictures
- [x] Bulk student CSV/XLSX import
- [x] Activation-code export + expiry
- [x] Point ledger
- [x] Challenges/submission approval
- [x] Duplicate challenge award protection
- [x] Overall/category/period/class/section/challenge leaderboards
- [x] Achievements
- [x] Rewards
- [x] Announcements
- [x] Notifications
- [x] Audit log
- [x] Branding controls
- [x] Competition starter structure
- [x] Automatic/manual full backups (database + uploads)
- [x] Public landing page
- [x] About and Privacy pages
- [x] Student progress CSV report
- [x] Challenge participation CSV report
- [x] Version/storage status in Super Admin launch center

## Security
- [x] Password hashing
- [x] Secure production cookies
- [x] CSRF protection
- [x] Authentication rate limiting
- [x] Server-side role + granular permission enforcement
- [x] Protected Super Admin-only routes
- [x] Security headers
- [x] Server-side input limits
- [x] Hardened logo/profile uploads
- [x] Session invalidation on reset/disable
- [x] Sensitive activation codes excluded from audit details

## Hosting
- [x] Railway Docker deployment
- [x] Persistent `/data` volume support
- [x] Health endpoint
- [x] Automatic old-database migration

## Verified setup work
- [x] Main admin verified as Super Admin
- [x] Production-preparation cleanup already completed
- [x] Bulk import tested with a dummy roster
- [x] Student activation/login flow pilot-tested
- [x] Admin and student core flows tested successfully

## Before real school-wide launch
- [ ] Obtain school approval for real student data and profile-photo use
- [ ] Import real student roster
- [ ] Keep activation closed until codes are ready for controlled distribution
- [ ] Create only necessary Staff Admin accounts and grant least privilege
- [ ] Upload exact official school crest when/if available
- [ ] Download a full ZIP backup after real data is added and keep a copy outside Railway
- [ ] Run a small school-approved real-user pilot
- [ ] Connect an official domain only when school DNS access is available
