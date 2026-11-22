-- Step 19: Teacher feedback conversations.
-- Student participation scoring is retired from the product. Teacher feedback
-- stays on student_progress_records (kind='feedback'), which already carries the
-- approval workflow, and this table adds the parent/teacher conversation on top
-- of an approved record. No existing table or column is removed, so historical
-- records remain intact and restorable.
CREATE TABLE IF NOT EXISTS ascend.feedback_messages (
 id SERIAL PRIMARY KEY,
 record_id INTEGER NOT NULL REFERENCES ascend.student_progress_records(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES ascend.users(id),
 author_role TEXT NOT NULL CHECK(author_role IN ('parent','teacher','admin')),
 body TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_messages_record ON ascend.feedback_messages(record_id,id);
