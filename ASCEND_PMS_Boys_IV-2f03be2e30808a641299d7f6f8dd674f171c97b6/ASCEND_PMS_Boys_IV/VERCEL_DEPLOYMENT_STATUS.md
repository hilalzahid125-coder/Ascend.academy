# Vercel deployment: verification required

The app supports PostgreSQL through `PMS_DATABASE_URL`. Uploaded images and backup archives are stored in the private `ascend` schema. PostgreSQL compatibility, backup creation, and restore have been tested on an isolated local PostgreSQL database, **not yet against this Supabase project or on Vercel**. Do not enter real student data until a deployed instance has passed end-to-end testing.

## First deployment

The connected Vercel deployment tool cannot supply the controls required for the first deployment of a new project. Create/import a new project through the Vercel dashboard using this repository and the branch `arena/794316a6-ascend-academy`. Set the project root directory to:

`ASCEND_PMS_Boys_IV-2f03be2e30808a641299d7f6f8dd674f171c97b6/ASCEND_PMS_Boys_IV`

Set these **server-side environment variables** before deployment:

- `PMS_DATABASE_URL`: the Supabase dashboard's PostgreSQL connection string for this project. Use an IPv4-compatible transaction pooler when the direct connection is unreachable; URL-encode special characters in the password. Database credentials belong in Vercel's encrypted environment settings, not Git or chat. TLS is required on Vercel. The server needs sufficient privileges to access the private `ascend` schema and run the supplied idempotent migrations.
- `PMS_ADMIN_ID`: initial Super Admin admission number (default `ADMIN-0001`).
- `PMS_ADMIN_PASSWORD`: a strong, unique password of at least 12 characters, chosen privately. This creates an initial admin if that ID does not exist; it does not update existing passwords or promote existing staff. After verifying the account, remove the bootstrap password from Vercel and redeploy so a deleted account cannot be silently recreated.
- `CRON_SECRET`: a long random secret used by Vercel to authorize scheduled backup requests; never share it or commit it.
- Optional: `PMS_BACKUP_RETENTION` (default 14), `PMS_BACKUP_INTERVAL_HOURS` (default 24).

If the database password from project creation is unavailable, reset it in the Supabase dashboard and use the new password in the connection string. Never submit it in chat. `VERCEL=1` without `PMS_DATABASE_URL` or with insecure cookies is rejected. Persistent data is never kept solely in Vercel's temporary filesystem.

The Vercel cron configuration requests a daily backup at 02:00 UTC, but scheduling, authentication, time limits, and actual creation must be checked after deployment. Backups stored in PostgreSQL share the same database and its quota and are not disaster recovery. Regularly download archives off-site, monitor storage/quota, and verify restores in an isolated database with `scripts/restore_postgres_backup.py`. Large datasets or archives can exceed function memory, execution time, or database limits. Consider dedicated object storage and managed off-site backups as the installation grows.

## Before real use

Test database connectivity, migrations, Super Admin and staff permissions, student activation/login, dashboards, image upload, challenge/reward flows, concurrent updates, manual and scheduled backups, download and an isolated restore. Confirm the browser cookie and preview behavior reported earlier. Only then import real users. Do not rely on the local preview credentials.
