import os, sqlite3, hashlib
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
 status TEXT CHECK(status IN ('present','absent') OR status IS NULL), marked_by INTEGER REFERENCES users(id), marked_at TEXT,
 PRIMARY KEY(session_id,student_id)
);
CREATE INDEX IF NOT EXISTS idx_class_attendance_student ON class_attendance(student_id);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  admission_no TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  password_hash TEXT,
  role TEXT NOT NULL CHECK(role IN ('student','admin')),
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

CREATE TABLE IF NOT EXISTS academy_signup_profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  profile_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

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
