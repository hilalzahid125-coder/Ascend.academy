# Supabase integration

The migrations create the private `ascend` schema, core application tables, uploaded image assets and backup archives. Direct `anon` and `authenticated` access is revoked. The FastAPI server connects using `PMS_DATABASE_URL` over PostgreSQL; API keys alone are not a database connection string. Migrations are idempotent and are also run during application initialization. Protect the database credential and keep it server-side.

The app and a portable backup/restore round trip have been tested against an isolated local PostgreSQL server. **The actual Supabase connection and Vercel deployment are not yet verified.** See `VERCEL_DEPLOYMENT_STATUS.md` for setup, security, backup limitations, and the remaining launch checks.
