SET LOCAL search_path = ascend, pg_catalog;
CREATE TABLE IF NOT EXISTS academy_holidays (
 holiday_date TEXT PRIMARY KEY, title TEXT NOT NULL,
 created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL
);
REVOKE ALL ON academy_holidays FROM PUBLIC, anon, authenticated;
