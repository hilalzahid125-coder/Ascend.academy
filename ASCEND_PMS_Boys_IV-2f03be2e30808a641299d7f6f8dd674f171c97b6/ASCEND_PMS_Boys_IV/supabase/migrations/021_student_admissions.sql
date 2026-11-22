-- New self-registered applicants remain isolated until an admin approves them.
CREATE TABLE IF NOT EXISTS ascend.student_admissions (
 user_id INTEGER PRIMARY KEY REFERENCES ascend.users(id) ON DELETE CASCADE,
 temporary_id TEXT NOT NULL UNIQUE,
 email TEXT NOT NULL, phone TEXT NOT NULL, guardian_name TEXT NOT NULL, guardian_phone TEXT NOT NULL,
 subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by INTEGER REFERENCES ascend.users(id), review_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS student_admissions_status_idx ON ascend.student_admissions(status,created_at);
