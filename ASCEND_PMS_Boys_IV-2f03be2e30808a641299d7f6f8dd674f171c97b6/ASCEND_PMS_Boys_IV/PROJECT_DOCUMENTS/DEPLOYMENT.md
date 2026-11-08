# Deployment

## Current production target: Railway

ASCEND uses FastAPI + SQLite and requires persistent writable storage. The included Dockerfile is configured for one Railway service.

### Persistent storage
Mount a Railway volume at:

```text
/data
```

Runtime paths:

- Database: `/data/pms_rise.db`
- Uploaded school branding: `/data/uploads/`
- Rolling backups: `/data/backups/`

### Core production variables

```text
PMS_SECURE_COOKIE=1
PMS_TRUST_PROXY_HEADERS=1
PMS_DATA_DIR=/data
PMS_BACKUP_ENABLED=1
PMS_BACKUP_INTERVAL_HOURS=24
PMS_BACKUP_RETENTION=14
```

Use `PMS_ADMIN_PASSWORD` only as the initial admin bootstrap secret and keep it out of GitHub.

### Health endpoint

`/health`

### Domain

Use the generated Railway `*.up.railway.app` domain during the private/pre-school phase. An official school subdomain can be connected later when administration provides DNS access.

### Existing v1.0 database

No database deletion is needed when upgrading to v1.2. Schema changes are migrated automatically at startup. Use the Admin **Launch & backups** page to create a safety backup, remove the known test/demo records, install the real starter competition structure and then import the real student roster.
