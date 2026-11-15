SET LOCAL search_path = ascend, pg_catalog;
ALTER TABLE student_progress_records ADD COLUMN IF NOT EXISTS feedback_type TEXT NOT NULL DEFAULT 'general';
ALTER TABLE student_progress_records ADD COLUMN IF NOT EXISTS period_start TEXT;
ALTER TABLE student_progress_records ADD COLUMN IF NOT EXISTS period_end TEXT;
ALTER TABLE student_progress_records ADD CONSTRAINT progress_feedback_type_check CHECK (feedback_type IN ('general','academic','improvement','behavior','parent_feedback'));
