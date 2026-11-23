-- Richer application records for the self-service signup flow.
--
-- A new applicant used to be shown only a temporary ID and a generic waiting
-- message. The status page now shows exactly what was submitted, when, which
-- subjects were chosen, and where the application sits in the review pipeline.
--
-- Both columns are additive and nullable, so existing rows stay valid.
ALTER TABLE ascend.student_admissions
  ADD COLUMN IF NOT EXISTS subjects TEXT NOT NULL DEFAULT '[]';

ALTER TABLE ascend.student_admissions
  ADD COLUMN IF NOT EXISTS full_name TEXT NOT NULL DEFAULT '';

COMMENT ON COLUMN ascend.student_admissions.subjects IS
  'JSON array of every subject the applicant selected in the signup wizard.';
COMMENT ON COLUMN ascend.student_admissions.full_name IS
  'Name exactly as typed at signup, kept separate from the users row.';
