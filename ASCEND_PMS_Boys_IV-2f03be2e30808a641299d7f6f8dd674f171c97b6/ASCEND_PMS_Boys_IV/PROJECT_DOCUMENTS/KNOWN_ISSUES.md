# Known Limits

- The exact official school crest is not embedded in this build; the current branding remains usable and the real crest can be uploaded from the Super Admin panel when available.
- SQLite is appropriate for one Railway service / school-scale usage. If ASCEND later needs multiple application replicas or substantially higher concurrency, migrate to PostgreSQL.
- Automatic full backups are stored on the persistent Railway volume. Super Admin can download them; keeping a periodic downloaded copy outside Railway is recommended for full disaster recovery.
- ASCEND currently uses the Railway-generated domain because official school-domain access is not yet available.
- Student profile pictures should only be used in accordance with the school’s privacy/photo policy.
