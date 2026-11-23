-- Admin-managed academy subjects.
--
-- Subjects used to be a hardcoded Python tuple ('Maths', 'Computer Science').
-- They now live in the database so the Super Admin can add, rename, reorder
-- and retire subjects without a code change. Every existing code path that
-- needed the list reads it through get_subjects(), which falls back to the
-- original two subjects on a fresh install.
CREATE TABLE IF NOT EXISTS ascend.academy_subjects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

-- Seed the two subjects that predate this table. ON CONFLICT keeps any
-- rename an administrator has already made.
INSERT INTO ascend.academy_subjects(name, sort_order, is_active, created_at)
VALUES ('Maths', 0, 1, '2026-01-01T00:00:00+00:00')
ON CONFLICT (name) DO NOTHING;

INSERT INTO ascend.academy_subjects(name, sort_order, is_active, created_at)
VALUES ('Computer Science', 1, 1, '2026-01-01T00:00:00+00:00')
ON CONFLICT (name) DO NOTHING;

REVOKE ALL ON ascend.academy_subjects FROM PUBLIC, anon, authenticated;
