SET LOCAL search_path = ascend, pg_catalog;
ALTER TABLE student_progress_records ADD COLUMN IF NOT EXISTS replaces_id INTEGER REFERENCES student_progress_records(id);
ALTER TABLE student_progress_records ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
CREATE UNIQUE INDEX IF NOT EXISTS progress_one_active_revision ON student_progress_records(replaces_id) WHERE replaces_id IS NOT NULL AND status IN ('pending','approved');
