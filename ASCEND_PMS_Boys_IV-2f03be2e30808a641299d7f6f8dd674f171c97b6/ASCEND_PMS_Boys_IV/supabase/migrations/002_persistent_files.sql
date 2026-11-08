-- Uploaded files and backups stay private to the application database role.
SET LOCAL search_path = ascend, pg_catalog;
CREATE TABLE IF NOT EXISTS file_assets (
    name TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,
    data BYTEA NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backup_archives (
    name TEXT PRIMARY KEY,
    data BYTEA NOT NULL,
    created_at TEXT NOT NULL
);
REVOKE ALL ON file_assets, backup_archives FROM PUBLIC, anon, authenticated;
