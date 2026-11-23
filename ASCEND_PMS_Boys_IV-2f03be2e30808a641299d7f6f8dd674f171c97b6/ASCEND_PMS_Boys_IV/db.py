import os, sqlite3, hashlib, re, json, threading, itertools
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from security import hash_password, iso_now

# Fail closed on Vercel: SQLite and temporary files are not persistent.
DATABASE_URL = os.getenv('PMS_DATABASE_URL', '')
if os.getenv('VERCEL') == '1' and not DATABASE_URL:
    raise RuntimeError('ASCEND on Vercel requires PMS_DATABASE_URL; SQLite is not persistent.')
if os.getenv('VERCEL') == '1':
    os.environ.setdefault('PMS_SECURE_COOKIE', '1')
    if os.getenv('PMS_SECURE_COOKIE') != '1':
        raise RuntimeError('ASCEND on Vercel requires secure cookies.')

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('PMS_DATA_DIR', '/tmp/ascend' if os.getenv('VERCEL') == '1' else BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv('PMS_DB_PATH', DATA_DIR / 'pms_rise.db'))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if DATABASE_URL:
    from pg_adapter import PostgresConnection, open_postgres, postgres_pool
    import psycopg
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)

SCHEMA = r'''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS class_schedules (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 parent_id INTEGER REFERENCES class_schedules(id),
 student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
 grade TEXT NOT NULL, subject TEXT NOT NULL, teacher_id INTEGER NOT NULL REFERENCES users(id),
 recurrence TEXT NOT NULL CHECK(recurrence IN ('weekly','once')),
 weekday INTEGER, class_date TEXT, start_time TEXT NOT NULL, duration_minutes INTEGER NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
 UNIQUE(parent_id, student_id)
);
CREATE TABLE IF NOT EXISTS class_sessions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 schedule_id INTEGER NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE, session_date TEXT NOT NULL,
 subject TEXT NOT NULL, grade TEXT NOT NULL, start_time TEXT NOT NULL, duration_minutes INTEGER NOT NULL,
 teacher_id INTEGER NOT NULL REFERENCES users(id), started_by INTEGER NOT NULL REFERENCES users(id),
 status TEXT NOT NULL CHECK(status IN ('live','ended')), started_at TEXT NOT NULL, ended_at TEXT,
 UNIQUE(schedule_id,session_date)
);
CREATE TABLE IF NOT EXISTS class_attendance (
 session_id INTEGER NOT NULL REFERENCES class_sessions(id) ON DELETE CASCADE, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 status TEXT CHECK(status IN ('present','absent','late','excused') OR status IS NULL), marked_by INTEGER REFERENCES users(id), marked_at TEXT,
 PRIMARY KEY(session_id,student_id)
);
CREATE INDEX IF NOT EXISTS idx_class_attendance_student ON class_attendance(student_id);
CREATE TABLE IF NOT EXISTS academy_holidays (
 holiday_date TEXT PRIMARY KEY, title TEXT NOT NULL,
 created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS academy_subjects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS class_live_rooms (
  session_id INTEGER PRIMARY KEY REFERENCES class_sessions(id) ON DELETE CASCADE,
  room_name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admission_no TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  password_hash TEXT,
  role TEXT NOT NULL CHECK(role IN ('student','admin','parent','teacher')),
  status TEXT NOT NULL DEFAULT 'unclaimed' CHECK(status IN ('unclaimed','active','disabled','pending')),
  class_name TEXT,
  section_name TEXT,
  activation_code TEXT,
  activation_code_expires_at TEXT,
  claimed INTEGER NOT NULL DEFAULT 0,
  profile_picture_path TEXT,
  admin_level TEXT CHECK(admin_level IN ('super','staff') OR admin_level IS NULL),
  admin_permissions TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parent_student_links (
 parent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL,
 PRIMARY KEY(parent_id,student_id)
);
CREATE INDEX IF NOT EXISTS idx_parent_student ON parent_student_links(student_id);
CREATE TABLE IF NOT EXISTS student_progress_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 teacher_id INTEGER NOT NULL REFERENCES users(id), subject TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('assessment','assignment','participation','feedback')),
 title TEXT NOT NULL, details TEXT NOT NULL, record_date TEXT NOT NULL,
 score INTEGER, score_max INTEGER, outcome TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL, reviewed_by INTEGER REFERENCES users(id), reviewed_at TEXT,
 review_note TEXT NOT NULL DEFAULT '', replaces_id INTEGER REFERENCES student_progress_records(id), version INTEGER NOT NULL DEFAULT 1,
 assessment_type TEXT NOT NULL DEFAULT 'general' CHECK(assessment_type IN ('general','quiz','test')),
 feedback_type TEXT NOT NULL DEFAULT 'general' CHECK(feedback_type IN ('general','academic','improvement','behavior','parent_feedback')),
 participation_type TEXT NOT NULL DEFAULT 'general' CHECK(participation_type IN ('general','classroom','answers','discussions','group','homework','activities','competitions','events','extracurricular')),
 period_start TEXT, period_end TEXT
);
CREATE TABLE IF NOT EXISTS academic_terms (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS academic_terms_dates ON academic_terms(start_date,end_date);
CREATE INDEX IF NOT EXISTS idx_progress_student ON student_progress_records(student_id,status,record_date);

-- Replies attached to an approved teacher-feedback record. The feedback record
-- stays the single source of the observation; this table only carries the
-- conversation between the student's teachers and their linked parents.
CREATE TABLE IF NOT EXISTS feedback_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 record_id INTEGER NOT NULL REFERENCES student_progress_records(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES users(id),
 author_role TEXT NOT NULL CHECK(author_role IN ('parent','teacher','admin')),
 body TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_messages_record ON feedback_messages(record_id,id);

CREATE TABLE IF NOT EXISTS fee_methods (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, currency TEXT NOT NULL,
 details TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fee_assignments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, period TEXT NOT NULL, description TEXT NOT NULL, installment TEXT NOT NULL,
 amount INTEGER NOT NULL CHECK(amount>0), currency TEXT NOT NULL, due_date TEXT,
 batch_key TEXT NOT NULL, created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL,
 UNIQUE(batch_key,student_id)
);
CREATE TABLE IF NOT EXISTS fee_payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, fee_id INTEGER NOT NULL REFERENCES fee_assignments(id),
 student_id INTEGER NOT NULL REFERENCES users(id), method_id INTEGER NOT NULL REFERENCES fee_methods(id),
 method_name TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), currency TEXT NOT NULL,
 payment_date TEXT NOT NULL, reference TEXT NOT NULL, notes TEXT NOT NULL,
 receipt BLOB NOT NULL, status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected')),
 submitted_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by INTEGER REFERENCES users(id), review_note TEXT NOT NULL DEFAULT '',
 submission_key TEXT NOT NULL UNIQUE, submitted_by INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS fee_waivers (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fee_id INTEGER NOT NULL REFERENCES fee_assignments(id),
 amount INTEGER NOT NULL CHECK(amount>0), reason TEXT NOT NULL,
 waived_by INTEGER NOT NULL REFERENCES users(id), waived_at TEXT NOT NULL,
 revoked_by INTEGER REFERENCES users(id), revoked_at TEXT, revocation_reason TEXT,
 CHECK((revoked_at IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL) OR
       (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS fee_one_active_waiver ON fee_waivers(fee_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS fee_waiver_history_idx ON fee_waivers(fee_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS fee_one_pending ON fee_payments(fee_id) WHERE status='submitted';
CREATE INDEX IF NOT EXISTS fee_student_idx ON fee_assignments(student_id);
CREATE INDEX IF NOT EXISTS fee_payment_idx ON fee_payments(fee_id,status);

CREATE TABLE IF NOT EXISTS academy_signup_profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  profile_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_admissions (
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 temporary_id TEXT NOT NULL UNIQUE,
 email TEXT NOT NULL, phone TEXT NOT NULL, guardian_name TEXT NOT NULL, guardian_phone TEXT NOT NULL,
 subject TEXT NOT NULL, subjects TEXT NOT NULL DEFAULT '[]', full_name TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL, reviewed_at TEXT, reviewed_by INTEGER REFERENCES users(id), review_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS student_admissions_status_idx ON student_admissions(status,created_at);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_key TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS challenges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  subject TEXT,
  points INTEGER NOT NULL DEFAULT 0,
  start_date TEXT,
  end_date TEXT,
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','scheduled','active','completed','expired','archived')),
  eligibility_class TEXT,
  eligibility_section TEXT,
  requires_submission INTEGER NOT NULL DEFAULT 1,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS challenge_participations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  challenge_id INTEGER NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'joined' CHECK(status IN ('joined','pending','approved','rejected','completed')),
  submission_text TEXT,
  review_note TEXT,
  awarded INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(challenge_id, user_id)
);

CREATE TABLE IF NOT EXISTS point_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  subject TEXT,
  reason TEXT NOT NULL,
  challenge_id INTEGER REFERENCES challenges(id),
  admin_id INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS achievements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'overall',
  points_required INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_achievements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  achievement_id INTEGER NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  unlocked_at TEXT NOT NULL,
  UNIQUE(achievement_id, user_id)
);

CREATE TABLE IF NOT EXISTS rewards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  points_required INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
  quantity INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reward_claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reward_id INTEGER NOT NULL REFERENCES rewards(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','fulfilled')),
  created_at TEXT NOT NULL,
  UNIQUE(reward_id, user_id)
);

CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  audience TEXT NOT NULL DEFAULT 'all',
  audience_role TEXT NOT NULL DEFAULT 'all' CHECK(audience_role IN ('all','students','parents','teachers')),
  class_name TEXT,
  section_name TEXT,
  status TEXT NOT NULL DEFAULT 'published' CHECK(status IN ('draft','published','archived')),
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  is_read INTEGER NOT NULL DEFAULT 0,
  kind TEXT NOT NULL DEFAULT 'update',
  student_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  link_path TEXT,
  read_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admin_id INTEGER REFERENCES users(id),
  action TEXT NOT NULL,
  details TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_points_user ON point_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_points_created ON point_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_points_category ON point_transactions(category);
CREATE INDEX IF NOT EXISTS idx_participation_user ON challenge_participations(user_id);
CREATE INDEX IF NOT EXISTS idx_challenges_status ON challenges(status);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_attempts_key_time ON auth_attempts(attempt_key,created_at);
'''

DEFAULT_SETTINGS = {
    'school_name': 'ASCEND Academy',
    'app_name': 'ASCEND',
    'tagline': 'Compete • Achieve • Grow',
    'creator_credit': 'Made by Hilal Zahid',
    'primary_color': '#c20a0a',
    'registration_enabled': '0',
    'school_logo_path': '/static/school-mark.svg',
    'competition_structure_version': '0',
    'academic_session': '',
}


def _configure(conn):
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    # WAL greatly reduces reader/writer contention for this single-service SQLite deployment.
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
    except sqlite3.DatabaseError:
        pass
    return conn


@contextmanager
def connect():
    if DATABASE_URL:
        # SET LOCAL is scoped to each transaction, including PgBouncer transaction
        # pools, so another request cannot inherit the wrong search path.
        with postgres_pool(DATABASE_URL).connection() as raw:
            raw.execute('SET LOCAL search_path TO ascend, pg_catalog')
            yield PostgresConnection(raw)
        return
    conn = _configure(sqlite3.connect(DB_PATH, timeout=5))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn):
    """Small idempotent migrations for databases created by earlier ASCEND builds."""
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'activation_code_expires_at' not in cols:
        conn.execute('ALTER TABLE users ADD COLUMN activation_code_expires_at TEXT')
    if 'profile_picture_path' not in cols:
        conn.execute('ALTER TABLE users ADD COLUMN profile_picture_path TEXT')
    if 'admin_level' not in cols:
        conn.execute('ALTER TABLE users ADD COLUMN admin_level TEXT')
    if 'admin_permissions' not in cols:
        conn.execute('ALTER TABLE users ADD COLUMN admin_permissions TEXT')
    # Existing installations originally had only one admin. Keep the bootstrap admin as
    # the Super Admin and make any additional legacy admins staff accounts.
    conn.execute("UPDATE users SET admin_level='staff' WHERE role='admin' AND (admin_level IS NULL OR admin_level='')")
    bootstrap_id=os.getenv('PMS_ADMIN_ID','ADMIN-0001').upper()
    conn.execute("UPDATE users SET admin_level='super' WHERE role='admin' AND admission_no=?",(bootstrap_id,))
    if not conn.execute("SELECT 1 FROM users WHERE role='admin' AND admin_level='super' LIMIT 1").fetchone():
        conn.execute("UPDATE users SET admin_level='super' WHERE id=(SELECT MIN(id) FROM users WHERE role='admin')")
    conn.execute('CREATE TABLE IF NOT EXISTS auth_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_key TEXT NOT NULL, created_at TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_auth_attempts_key_time ON auth_attempts(attempt_key,created_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at)')



def _migrate_sqlite_parent_role(conn):
    """Expand the users role constraint without renaming referenced tables.

    Preserve all columns, indexes and triggers of legacy installations. The
    rebuild is atomic and validates foreign keys before committing.
    """
    row=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if not row or ("'parent'" in row['sql'] and "'teacher'" in row['sql']):
        return
    original=row['sql']
    pattern=r"CHECK\s*\(\s*role\s+IN\s*\(\s*'student'\s*,\s*'admin'(?:\s*,\s*'parent')?\s*\)\s*\)"
    expanded,count=re.subn(pattern,"CHECK(role IN ('student','admin','parent','teacher'))",original,flags=re.I)
    if count!=1:
        raise RuntimeError('Unexpected users role constraint; cannot safely enable parent accounts.')
    expanded=re.sub(r'^(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?:"users"|users)',r'\1users_parent_migration',expanded,count=1,flags=re.I)
    objects=[r['sql'] for r in conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name='users' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()]
    cols=[r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()]
    quoted=','.join('"'+c.replace('"','""')+'"' for c in cols)
    conn.commit()
    conn.execute('PRAGMA foreign_keys=OFF')
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(expanded)
        conn.execute(f'INSERT INTO users_parent_migration ({quoted}) SELECT {quoted} FROM users')
        conn.execute('DROP TABLE users')
        conn.execute('ALTER TABLE users_parent_migration RENAME TO users')
        for sql in objects: conn.execute(sql)
        if conn.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('Parent migration failed foreign-key validation.')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')


def _migrate_sqlite_attendance_status(conn):
    row=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='class_attendance'").fetchone()
    if not row or ("'late'" in row['sql'] and "'excused'" in row['sql']): return
    original=row['sql']
    expanded,count=re.subn(r"status\s+IN\s*\(\s*'present'\s*,\s*'absent'\s*\)", "status IN ('present','absent','late','excused')", original,flags=re.I)
    if count!=1: raise RuntimeError('Unexpected attendance constraint; cannot safely expand statuses.')
    expanded=re.sub(r'^(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?:"class_attendance"|class_attendance)',r'\1attendance_status_migration',expanded,count=1,flags=re.I)
    objects=[r['sql'] for r in conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name='class_attendance' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()]
    cols=[r['name'] for r in conn.execute('PRAGMA table_info(class_attendance)').fetchall()]
    quoted=','.join('"'+c.replace('"','""')+'"' for c in cols)
    conn.commit(); conn.execute('PRAGMA foreign_keys=OFF')
    try:
        conn.execute('BEGIN IMMEDIATE'); conn.execute(expanded)
        conn.execute(f'INSERT INTO attendance_status_migration ({quoted}) SELECT {quoted} FROM class_attendance')
        conn.execute('DROP TABLE class_attendance'); conn.execute('ALTER TABLE attendance_status_migration RENAME TO class_attendance')
        for sql in objects: conn.execute(sql)
        if conn.execute('PRAGMA foreign_key_check').fetchone(): raise RuntimeError('Attendance migration failed foreign-key validation.')
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')

def _migrate_sqlite_progress_revisions(conn):
    columns={r['name'] for r in conn.execute('PRAGMA table_info(student_progress_records)').fetchall()}
    if 'replaces_id' not in columns:
        conn.execute('ALTER TABLE student_progress_records ADD COLUMN replaces_id INTEGER REFERENCES student_progress_records(id)')
    if 'version' not in columns:
        conn.execute('ALTER TABLE student_progress_records ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS progress_one_active_revision ON student_progress_records(replaces_id) WHERE replaces_id IS NOT NULL AND status IN ('pending','approved')")


def _migrate_sqlite_assessment_type(conn):
    columns={r['name'] for r in conn.execute('PRAGMA table_info(student_progress_records)').fetchall()}
    if 'assessment_type' not in columns:
        conn.execute("ALTER TABLE student_progress_records ADD COLUMN assessment_type TEXT NOT NULL DEFAULT 'general' CHECK(assessment_type IN ('general','quiz','test'))")


def _migrate_sqlite_feedback_details(conn):
    columns={r['name'] for r in conn.execute('PRAGMA table_info(student_progress_records)').fetchall()}
    if 'feedback_type' not in columns:
        conn.execute("ALTER TABLE student_progress_records ADD COLUMN feedback_type TEXT NOT NULL DEFAULT 'general' CHECK(feedback_type IN ('general','academic','improvement','behavior','parent_feedback'))")
    if 'period_start' not in columns: conn.execute('ALTER TABLE student_progress_records ADD COLUMN period_start TEXT')
    if 'period_end' not in columns: conn.execute('ALTER TABLE student_progress_records ADD COLUMN period_end TEXT')


def _migrate_sqlite_admission_details(conn):
    """Backfill the two application-detail columns for pre-existing databases."""
    columns={r['name'] for r in conn.execute('PRAGMA table_info(student_admissions)').fetchall()}
    if 'subjects' not in columns:
        conn.execute("ALTER TABLE student_admissions ADD COLUMN subjects TEXT NOT NULL DEFAULT '[]'")
    if 'full_name' not in columns:
        conn.execute("ALTER TABLE student_admissions ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
    # Older rows stored a single subject; promote it into the JSON list and
    # copy the name across so the status page always has something to show.
    for row in conn.execute("SELECT user_id,subject,full_name FROM student_admissions WHERE subjects='[]' OR full_name=''").fetchall():
        user=conn.execute('SELECT full_name FROM users WHERE id=?',(row['user_id'],)).fetchone()
        name=row['full_name'] or (user['full_name'] if user else '')
        try:
            stored=json.loads(row['subject'])
            subjects=stored if isinstance(stored,list) and stored else [row['subject']]
        except (TypeError, ValueError):
            subjects=[row['subject']] if row['subject'] else []
        conn.execute('UPDATE student_admissions SET subjects=?,full_name=? WHERE user_id=?',
                     (json.dumps(subjects), name, row['user_id']))


def _migrate_sqlite_announcement_audience(conn):
    columns={r['name'] for r in conn.execute('PRAGMA table_info(announcements)').fetchall()}
    if 'audience_role' not in columns:
        conn.execute("ALTER TABLE announcements ADD COLUMN audience_role TEXT NOT NULL DEFAULT 'all' CHECK(audience_role IN ('all','students','parents','teachers'))")


def _migrate_sqlite_participation_type(conn):
    columns={r['name'] for r in conn.execute('PRAGMA table_info(student_progress_records)').fetchall()}
    if 'participation_type' not in columns:
        conn.execute("ALTER TABLE student_progress_records ADD COLUMN participation_type TEXT NOT NULL DEFAULT 'general' CHECK(participation_type IN ('general','classroom','answers','discussions','group','homework','activities','competitions','events','extracurricular'))")


def _migrate_sqlite_subject_point_metadata(conn):
    for table in ('challenges','point_transactions'):
        columns={r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        if 'subject' not in columns: conn.execute(f'ALTER TABLE {table} ADD COLUMN subject TEXT')


def _migrate_sqlite_fee_submitter(conn):
    columns={r['name'] for r in conn.execute('PRAGMA table_info(fee_payments)').fetchall()}
    if 'submitted_by' not in columns:
        conn.execute('ALTER TABLE fee_payments ADD COLUMN submitted_by INTEGER REFERENCES users(id)')


def _migrate_sqlite_notification_categories(conn):
    cols={r['name'] for r in conn.execute('PRAGMA table_info(notifications)').fetchall()}
    if 'kind' not in cols:
        conn.execute("ALTER TABLE notifications ADD COLUMN kind TEXT NOT NULL DEFAULT 'update'")
    if 'student_id' not in cols:
        conn.execute('ALTER TABLE notifications ADD COLUMN student_id INTEGER REFERENCES users(id) ON DELETE SET NULL')
    if 'link_path' not in cols:
        conn.execute('ALTER TABLE notifications ADD COLUMN link_path TEXT')
    if 'read_at' not in cols:
        conn.execute('ALTER TABLE notifications ADD COLUMN read_at TEXT')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id,is_read)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_notifications_kind ON notifications(kind)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_notifications_student ON notifications(student_id)')


def _migrate_sqlite_staff_permissions(conn):
    # Preserve historical implicit staff capabilities once; do not re-grant
    # revoked permissions on subsequent starts.
    if not conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES ('staff_permissions_explicit_v1','1')").rowcount:
        return
    default=['students','challenges','achievements','rewards','announcements','activity']
    rows=conn.execute("SELECT id,admin_permissions FROM users WHERE role='admin' AND admin_level='staff'").fetchall()
    for row in rows:
        try:
            permissions=json.loads(row['admin_permissions']) if row['admin_permissions'] else default[:]
            if not isinstance(permissions,list): permissions=default[:]
        except (ValueError,TypeError):
            permissions=default[:]
        for permission in ('classes','leaderboards'):
            if permission not in permissions: permissions.append(permission)
        conn.execute('UPDATE users SET admin_permissions=? WHERE id=?',(json.dumps(permissions),row['id']))


def _migrate_sqlite_staff_feedback_permission(conn):
    # Teacher feedback used to sit behind the "Students & points" grant. Give
    # existing staff admins who had that access the new explicit grant once, so
    # nobody loses a screen they could already open; later edits are respected.
    if not conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES ('staff_permissions_feedback_v1','1')").rowcount:
        return
    rows=conn.execute("SELECT id,admin_permissions FROM users WHERE role='admin' AND admin_level='staff'").fetchall()
    for row in rows:
        try:
            permissions=json.loads(row['admin_permissions']) if row['admin_permissions'] else []
            if not isinstance(permissions,list): permissions=[]
        except (ValueError,TypeError):
            permissions=[]
        if 'students' in permissions and 'feedback' not in permissions:
            permissions.append('feedback')
            conn.execute('UPDATE users SET admin_permissions=? WHERE id=?',(json.dumps(permissions),row['id']))


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DATABASE_URL:
        with open_postgres(DATABASE_URL) as raw:
            raw.execute('SELECT pg_advisory_xact_lock(638418625)')
            # Infrastructure-only ledger: migrations remain atomic, and cold
            # starts don't repeatedly execute every historical DDL statement.
            raw.execute('CREATE SCHEMA IF NOT EXISTS ascend')
            raw.execute('REVOKE ALL ON SCHEMA ascend FROM PUBLIC, anon, authenticated')
            raw.execute('CREATE TABLE IF NOT EXISTS ascend.app_schema_migrations (name TEXT PRIMARY KEY, checksum TEXT NOT NULL)')
            raw.execute('REVOKE ALL ON ascend.app_schema_migrations FROM PUBLIC, anon, authenticated')
            applied={r['name']:r['checksum'] for r in raw.execute('SELECT name,checksum FROM ascend.app_schema_migrations').fetchall()}
            for migration in sorted((BASE_DIR / 'supabase/migrations').glob('*.sql')):
                contents=migration.read_text(encoding='utf-8')
                digest=hashlib.sha256(contents.encode('utf-8')).hexdigest()
                if migration.name in applied:
                    if applied[migration.name]!=digest:
                        raise RuntimeError(f'Applied migration {migration.name} has changed; add a new migration instead.')
                    continue
                raw.execute(contents)
                raw.execute('INSERT INTO ascend.app_schema_migrations(name,checksum) VALUES (%s,%s)',(migration.name,digest))
    with connect() as conn:
        if not DATABASE_URL:
            conn.executescript(SCHEMA)
            _migrate(conn)
            _migrate_sqlite_parent_role(conn)
            _migrate_sqlite_attendance_status(conn)
            _migrate_sqlite_progress_revisions(conn)
            _migrate_sqlite_fee_submitter(conn)
            _migrate_sqlite_assessment_type(conn)
            _migrate_sqlite_feedback_details(conn)
            _migrate_sqlite_participation_type(conn)
            _migrate_sqlite_subject_point_metadata(conn)
            _migrate_sqlite_notification_categories(conn)
            _migrate_sqlite_staff_permissions(conn)
            _migrate_sqlite_announcement_audience(conn)
            _migrate_sqlite_admission_details(conn)
            _migrate_sqlite_staff_feedback_permission(conn)
        seed_default_subjects(conn)
        default_values=list(DEFAULT_SETTINGS.items())
        conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES '+','.join('(?,?)' for _ in default_values),
                     [value for pair in default_values for value in pair])
        migrated=conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)', ('academy_identity_migrated','1'))
        if migrated.rowcount:
            conn.execute("UPDATE settings SET value=? WHERE key='school_name' AND value=?", ('ASCEND Academy', 'Peshawar Model School Boys IV'))
        conn.execute("UPDATE settings SET value=? WHERE key='creator_credit' AND value=?", ('Made by Hilal Zahid', 'Made by Abdul Hanan Sethi'))
        conn.execute("UPDATE settings SET value=? WHERE key='primary_color' AND lower(value)=?", ('#c20a0a', '#f97316'))
        now=datetime.now(timezone.utc).isoformat()
        old=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        conn.execute('DELETE FROM sessions WHERE expires_at < ?',(now,))
        conn.execute('DELETE FROM auth_attempts WHERE created_at < ?',(old,))


def get_settings(conn=None):
    own = conn is None
    if own:
        with connect() as own_conn:
            return get_settings(own_conn)
    rows = conn.execute('SELECT key,value FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows}


# ---------- Academy subjects ----------
# Subjects are administrator-managed data now, not a Python constant. These
# helpers are the single source of truth for every screen that lists subjects.
DEFAULT_SUBJECTS = ('Maths', 'Computer Science')


def seed_default_subjects(conn):
    """Make sure a database always has at least the two original subjects."""
    if conn.execute('SELECT COUNT(*) c FROM academy_subjects').fetchone()['c']:
        return
    for index, name in enumerate(DEFAULT_SUBJECTS):
        try:
            conn.execute('INSERT INTO academy_subjects(name,sort_order,is_active,created_at) VALUES (?,?,1,?)',
                         (name, index, iso_now()))
        except INTEGRITY_ERRORS:
            pass


# Subjects are read on nearly every academy screen. Reading them inside a
# request that already holds an open SQLite connection (or a transaction) would
# nest a second connection and stall on the write lock, so memoise per request.
# The counter lets a write invalidate the cache in every thread of this process,
# not just the one that handled the request.
_SUBJECTS_CACHE = threading.local()
_SUBJECTS_EPOCH = itertools.count()
_SUBJECTS_GENERATION = [0]


def clear_subjects_cache():
    """Drop the subject cache everywhere on the next read.

    Each thread keeps its own entry, so a write handled on one worker thread
    must not leave another thread serving the old list.
    """
    _SUBJECTS_GENERATION[0] = next(_SUBJECTS_EPOCH)
    for attr in ('active', 'all', 'generation'):
        if hasattr(_SUBJECTS_CACHE, attr):
            delattr(_SUBJECTS_CACHE, attr)


def _read_subjects(conn, include_retired):
    query = 'SELECT name FROM academy_subjects'
    if not include_retired:
        query += ' WHERE is_active=1'
    query += ' ORDER BY sort_order, name'
    try:
        rows = conn.execute(query).fetchall()
    except Exception:
        return list(DEFAULT_SUBJECTS)
    names = [r['name'] for r in rows]
    return names or list(DEFAULT_SUBJECTS)


def get_subjects(conn=None, include_retired=False, fresh=False):
    """Return the ordered subject list.

    Falls back to DEFAULT_SUBJECTS if the table is missing (unit tests build
    the schema on the fly) so callers never have to guard against it.

    Results are cached per request in thread-local storage, so calling this
    from inside a block that already holds a connection never opens a nested
    one. Pass ``conn`` to read through a connection the caller owns (always
    fresh), or ``fresh=True`` to bypass the cache after a write.
    """
    if conn is not None:
        return _read_subjects(conn, include_retired)
    attr = 'all' if include_retired else 'active'
    generation = _SUBJECTS_GENERATION[0]
    cached = getattr(_SUBJECTS_CACHE, attr, None)
    if not fresh and cached is not None and getattr(_SUBJECTS_CACHE, 'generation', None) == generation:
        return cached
    with connect() as own_conn:
        names = _read_subjects(own_conn, include_retired)
    _SUBJECTS_CACHE.generation = generation
    setattr(_SUBJECTS_CACHE, attr, names)
    return names


def database_size():
    if not DATABASE_URL:
        return DB_PATH.stat().st_size if DB_PATH.exists() else 0
    with connect() as conn:
        row = conn.execute("""SELECT COALESCE(SUM(pg_total_relation_size(c.oid)),0) AS size
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='ascend' AND c.relkind IN ('r','m')""").fetchone()
        return row['size']


def ensure_admin(admission_no: str, full_name: str, password: str):
    """Create the initial admin only if it does not already exist.

    PMS_ADMIN_PASSWORD is intentionally a bootstrap secret, not a perpetual password override.
    Existing admin passwords are changed from the admin UI instead.
    """
    with connect() as conn:
        row = conn.execute('SELECT id,role,admin_level FROM users WHERE admission_no=?', (admission_no.upper(),)).fetchone()
        if row:
            # Bootstrap never changes an existing user's role or password.
            return row['id']
        cur = conn.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,created_at)
                            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(admission_no) DO NOTHING RETURNING id''',
                           (admission_no.upper(), full_name, hash_password(password), 'admin', 'active', 1, 'super', iso_now()))
        inserted = cur.fetchone()
        if inserted:
            return inserted['id']
        return conn.execute('SELECT id FROM users WHERE admission_no=? AND role=?', (admission_no.upper(), 'admin')).fetchone()['id']
