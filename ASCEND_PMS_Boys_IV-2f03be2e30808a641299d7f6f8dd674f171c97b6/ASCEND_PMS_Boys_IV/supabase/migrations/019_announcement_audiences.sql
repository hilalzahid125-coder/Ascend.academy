-- Step 20: role-targeted announcements.
-- `audience` keeps its existing meaning (all / class / section scope). This adds
-- the orthogonal question of who should receive the notice, so an announcement
-- can be for everyone, students only, parents only or teachers only without a
-- second table. Existing rows default to 'all', which is what they already did.
ALTER TABLE ascend.announcements
  ADD COLUMN IF NOT EXISTS audience_role TEXT NOT NULL DEFAULT 'all'
  CHECK (audience_role IN ('all','students','parents','teachers'));
CREATE INDEX IF NOT EXISTS idx_announcements_role ON ascend.announcements(audience_role,status);
