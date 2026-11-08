"""Restore a downloaded ASCEND backup into PostgreSQL (destructive).

Run with PMS_DATABASE_URL set, after downloading and verifying a backup:
    python scripts/restore_postgres_backup.py /path/to/ascend_backup.zip
The script requires an explicit confirmation and restores in one transaction.
"""
import io, os, re, sqlite3, sys, tempfile, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import DATABASE_URL, connect, init_db
from security import iso_now


def restore_backup(archive):
    if not DATABASE_URL:
        raise RuntimeError('PMS_DATABASE_URL must point to the intended PostgreSQL database.')
    # Load and validate the backup completely before modifying the target.
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if names.count('ascend.db') != 1:
            raise ValueError('Backup must contain exactly one database snapshot.')
        assets=[]
        for name in names:
            if name == 'ascend.db':
                continue
            if not re.fullmatch(r'uploads/(?:profile_\d+\.webp|school_logo\.png)', name):
                raise ValueError(f'Unexpected archive item: {name}')
            asset_name=name.split('/')[-1]
            assets.append((asset_name, 'image/png' if asset_name.endswith('.png') else 'image/webp', z.read(name), iso_now()))
        db_bytes=z.read('ascend.db')
    fd, tmp=tempfile.mkstemp(suffix='.db')
    try:
        with os.fdopen(fd,'wb') as f: f.write(db_bytes)
        sqlite=sqlite3.connect(f'file:{tmp}?mode=ro',uri=True)
        sqlite.row_factory=sqlite3.Row
        try:
            if sqlite.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup database failed integrity check.')
            expected=['settings','users','academy_signup_profiles','sessions','auth_attempts','challenges',
                      'challenge_participations','point_transactions','achievements','student_achievements',
                      'rewards','reward_claims','announcements','notifications','audit_logs']
            tables={r['name'] for r in sqlite.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not set(expected).issubset(tables):
                raise ValueError('Backup is missing required tables.')
            class_tables=['class_schedules','class_sessions','class_attendance']
            present=set(class_tables) & tables
            if present and present != set(class_tables):
                raise ValueError('Backup has an incomplete class data set.')
            snapshot=[]
            for table in expected + (class_tables if present else []):
                columns=[r['name'] for r in sqlite.execute(f'PRAGMA table_info({table})')]
                rows=[tuple(r[c] for c in columns) for r in sqlite.execute(f'SELECT * FROM {table}')]
                snapshot.append((table,columns,rows))
        finally:
            sqlite.close()
        init_db()
        with connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            # Older backups predate My Classes; clearing the newer tables prevents
            # stale data and foreign keys from surviving a full restore.
            if not present:
                for table in reversed(class_tables): conn.execute(f'DELETE FROM {table}')
            for table, _, _ in reversed(snapshot): conn.execute(f'DELETE FROM {table}')
            conn.execute('DELETE FROM file_assets')
            for table, columns, rows in snapshot:
                placeholders=','.join('?' for _ in columns)
                for row in rows:
                    conn.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({placeholders})', row)
                if 'id' in columns:
                    conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), GREATEST(COALESCE(MAX(id),0),1), COALESCE(MAX(id),0)>0) FROM {table}")
            for asset in assets:
                conn.execute('INSERT INTO file_assets(name,content_type,data,created_at) VALUES (?,?,?,?)',asset)
    finally:
        Path(tmp).unlink(missing_ok=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: restore_postgres_backup.py path-to-backup.zip')
    print('WARNING: This replaces all ASCEND users, data and uploaded images in the configured database.')
    if input('Type RESTORE ASCEND to continue: ').strip() != 'RESTORE ASCEND':
        raise SystemExit('Cancelled; no data was changed.')
    restore_backup(sys.argv[1])
    print('Restore completed. Verify login, data and uploads before using the app.')
