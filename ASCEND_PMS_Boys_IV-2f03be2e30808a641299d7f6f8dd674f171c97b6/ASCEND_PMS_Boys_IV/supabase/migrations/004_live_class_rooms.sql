SET LOCAL search_path = ascend, pg_catalog;
-- Rooms are private application data; each live session receives a new secret.
CREATE TABLE IF NOT EXISTS class_live_rooms (
  session_id INTEGER PRIMARY KEY REFERENCES class_sessions(id) ON DELETE CASCADE,
  room_name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
REVOKE ALL ON class_live_rooms FROM PUBLIC, anon, authenticated;
