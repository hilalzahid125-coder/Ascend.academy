SET LOCAL search_path = ascend, pg_catalog;
ALTER TABLE class_attendance DROP CONSTRAINT IF EXISTS class_attendance_status_check;
ALTER TABLE class_attendance ADD CONSTRAINT class_attendance_status_check CHECK (status IN ('present','absent','late','excused') OR status IS NULL);
