import os, sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from security import hash_password, iso_now

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('PMS_DATA_DIR', BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv('PMS_DB_PATH', DATA_DIR / 'pms_rise.db'))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = r'''
PRAGMA foreign_keys = ON;

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
    'school_name': 'Peshawar Model School Boys IV',
    'app_name': 'ASCEND',
    'tagline': 'Compete • Achieve • Grow',
    'creator_credit': 'Made by Abdul Hanan Sethi',
    'primary_color': '#f97316',
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
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)', (k,v))
        # Expired sessions and stale rate-limit records should not grow forever.
        now=datetime.now(timezone.utc).isoformat()
        old=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        conn.execute('DELETE FROM sessions WHERE expires_at < ?',(now,))
        conn.execute('DELETE FROM auth_attempts WHERE created_at < ?',(old,))


def get_settings(conn=None):
    own = conn is None
    if own:
        conn = _configure(sqlite3.connect(DB_PATH, timeout=5))
    rows = conn.execute('SELECT key,value FROM settings').fetchall()
    data = {r['key']: r['value'] for r in rows}
    if own:
        conn.close()
    return data


def ensure_admin(admission_no: str, full_name: str, password: str):
    """Create the initial admin only if it does not already exist.

    PMS_ADMIN_PASSWORD is intentionally a bootstrap secret, not a perpetual password override.
    Existing admin passwords are changed from the admin UI instead.
    """
    with connect() as conn:
        row = conn.execute('SELECT id,role,admin_level FROM users WHERE admission_no=?', (admission_no.upper(),)).fetchone()
        if row:
            if row['role']=='admin' and row['admin_level']!='super':
                conn.execute("UPDATE users SET admin_level='super' WHERE id=?",(row['id'],))
            return row['id']
        cur = conn.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,created_at)
                            VALUES (?,?,?,?,?,?,?,?)''',
                           (admission_no.upper(), full_name, hash_password(password), 'admin', 'active', 1, 'super', iso_now()))
        return cur.lastrowid
