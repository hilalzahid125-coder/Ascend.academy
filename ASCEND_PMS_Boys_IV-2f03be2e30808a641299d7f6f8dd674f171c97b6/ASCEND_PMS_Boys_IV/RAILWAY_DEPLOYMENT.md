# Railway Deployment — ASCEND v1.2

## Service
Deploy from the GitHub repository using the included Dockerfile.

## Persistent volume
Attach one Railway volume to the ASCEND service and mount it at:

```text
/data
```

ASCEND stores the SQLite database, uploaded school logo, student profile pictures and rolling full backup archives below that directory.

## Variables

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

Do not commit the real password to GitHub.

## Health check

```text
/health
```

Expected JSON includes `"ok": true`.

## After v1.2 deploys

1. Sign in with the existing main admin. The database migrates automatically and that bootstrap admin becomes the protected **Super Admin**.
2. Verify **Admin team** appears in the Super Admin navigation.
3. Existing students/data remain intact unless you deliberately use the cleanup tool.
4. If production preparation has not yet been run, open **Launch & backups** and use `PREPARE ASCEND`.
5. Bulk-import real students from CSV/XLSX when available.
6. Export activation codes and enable registration only during onboarding.
7. Create Staff Admin accounts only for trusted helpers and grant the minimum permissions needed.
8. Create/download a full ZIP backup after major roster or configuration changes.

The Railway-generated `*.up.railway.app` address is suitable while the school domain is unavailable.
