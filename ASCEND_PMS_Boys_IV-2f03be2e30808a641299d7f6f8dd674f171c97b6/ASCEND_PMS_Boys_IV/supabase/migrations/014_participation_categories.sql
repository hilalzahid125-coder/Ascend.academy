SET LOCAL search_path = ascend, pg_catalog;
-- Existing participation records were not classified; preserve them as general.
ALTER TABLE student_progress_records ADD COLUMN IF NOT EXISTS participation_type TEXT NOT NULL DEFAULT 'general';
DO $$
BEGIN
  ALTER TABLE student_progress_records ADD CONSTRAINT progress_participation_type_check CHECK (participation_type IN ('general','classroom','answers','discussions','group','homework','activities','competitions','events','extracurricular'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
