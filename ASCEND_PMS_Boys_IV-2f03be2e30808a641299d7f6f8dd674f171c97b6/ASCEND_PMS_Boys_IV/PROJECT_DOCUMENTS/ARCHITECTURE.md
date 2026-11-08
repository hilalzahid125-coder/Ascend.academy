# Architecture

- FastAPI server-rendered application
- Jinja responsive interface with ASCEND orange/white/black design system
- SQLite relational database on Railway persistent storage (`/data/pms_rise.db`)
- Foreign keys, indexes, WAL journal mode and busy timeout
- Idempotent schema migration for earlier ASCEND databases
- PBKDF2-HMAC-SHA256 password hashing
- Opaque random server-side sessions stored only as SHA-256 token hashes
- CSRF double-submit token protection on state-changing forms
- Account/IP authentication rate limiting persisted in SQLite
- Three access levels: Student, Staff Admin and protected Super Admin
- Configurable staff-admin operational permissions stored server-side
- Server-side authorization on every protected route/action
- Point totals derived from an auditable transaction ledger
- Unique student/challenge participation + awarded state for duplicate reward protection
- CSV/XLSX roster parsing with server-side validation and generated activation codes
- Student activation-code expiration
- Student profile pictures safely decoded, cropped and re-encoded to WEBP
- Runtime uploads stored under persistent `/data/uploads`
- Rolling full ZIP backups stored under `/data/backups`, containing DB snapshot + persistent uploads
- Production setup/cleanup operations available from a no-code Super Admin launch center

The architecture deliberately favors one simple, maintainable school deployment. PostgreSQL is the natural later migration if usage grows beyond a single application service.
