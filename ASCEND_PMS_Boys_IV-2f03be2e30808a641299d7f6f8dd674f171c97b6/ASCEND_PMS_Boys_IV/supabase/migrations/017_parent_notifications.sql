-- Step 12: Parent Notifications & Announcements.
-- Extends the existing notifications table with a category, the linked
-- student, an optional deep link and a read timestamp. Announcements keep
-- using the existing announcements table; no separate notification system.
ALTER TABLE ascend.notifications ADD COLUMN kind TEXT NOT NULL DEFAULT 'update';
ALTER TABLE ascend.notifications ADD COLUMN student_id INTEGER REFERENCES ascend.users(id) ON DELETE SET NULL;
ALTER TABLE ascend.notifications ADD COLUMN link_path TEXT;
ALTER TABLE ascend.notifications ADD COLUMN read_at TEXT;

CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON ascend.notifications(user_id,is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_kind ON ascend.notifications(kind);
CREATE INDEX IF NOT EXISTS idx_notifications_student ON ascend.notifications(student_id);
