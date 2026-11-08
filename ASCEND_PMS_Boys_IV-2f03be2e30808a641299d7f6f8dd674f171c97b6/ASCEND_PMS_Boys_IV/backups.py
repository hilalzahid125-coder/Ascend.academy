import io, os, secrets, sqlite3, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
from db import DB_PATH, DATA_DIR, DATABASE_URL, SCHEMA, connect

BACKUP_DIR = DATA_DIR / 'backups'
UPLOAD_DIR = DATA_DIR / 'uploads'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def _postgres_backup(target):
    """Export a consistent PostgreSQL snapshot and uploaded images to a ZIP.

    The portable SQLite snapshot is compatible with existing backup downloads.
    Archives are stored privately in PostgreSQL; download them off-site as well.
    """
    fd, tmp_name = tempfile.mkstemp(prefix='ascend_snapshot_', suffix='.db', dir=str(BACKUP_DIR))
    os.close(fd)
    tmp_db = Path(tmp_name)
    output = io.BytesIO()
    try:
        sqlite = sqlite3.connect(tmp_db)
        try:
            sqlite.executescript(SCHEMA)
            tables = [r[0] for r in sqlite.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
            with connect() as pg:
                pg.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                # The table names come from the fixed, application-owned SQLite schema.
                sqlite.execute('PRAGMA foreign_keys=OFF')
                for table in tables:
                    columns = [r[1] for r in sqlite.execute(f'PRAGMA table_info({table})')]
                    rows = pg.execute(f'SELECT * FROM {table}').fetchall()
                    placeholders = ','.join('?' for _ in columns)
                    sqlite.executemany(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({placeholders})',
                                       [tuple(row[column] for column in columns) for row in rows])
                sqlite.commit()
                with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
                    zf.write(tmp_db,'ascend.db')
                    for item in pg.execute('SELECT name,data FROM file_assets').fetchall():
                        name=item['name']
                        if Path(name).name != name:
                            raise ValueError('Invalid stored upload name')
                        zf.writestr('uploads/' + name, bytes(item['data']))
        finally:
            sqlite.close()
        with connect() as pg:
            pg.execute('INSERT INTO backup_archives(name,data,created_at) VALUES (?,?,?)',
                       (target.name,output.getvalue(),datetime.now(timezone.utc).isoformat()))
    finally:
        tmp_db.unlink(missing_ok=True)
    return target


def backup_bytes(filename):
    if DATABASE_URL:
        with connect() as conn:
            row=conn.execute('SELECT data FROM backup_archives WHERE name=?',(filename,)).fetchone()
            return bytes(row['data']) if row else None
    path=(BACKUP_DIR/filename).resolve()
    return path.read_bytes() if path.parent == BACKUP_DIR.resolve() and path.is_file() else None


def create_backup(label='auto'):
    """Create a consistent full ASCEND backup archive.

    The ZIP contains an online SQLite snapshot plus persistent uploaded assets
    such as school branding and student profile pictures.
    """
    if not DATABASE_URL and not DB_PATH.exists():
        return None
    safe_label = ''.join(c for c in label.lower() if c.isalnum() or c in ('-','_'))[:24] or 'backup'
    target = BACKUP_DIR / f'ascend_{safe_label}_{_stamp()}.zip'
    if DATABASE_URL:
        target = BACKUP_DIR / f'ascend_{safe_label}-{secrets.token_hex(3)}_{_stamp()}.zip'
        return _postgres_backup(target)
    fd, tmp_name = tempfile.mkstemp(prefix='ascend_snapshot_', suffix='.db', dir=str(BACKUP_DIR))
    os.close(fd)
    tmp_db = Path(tmp_name)
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(tmp_db)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    try:
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
            zf.write(tmp_db,'ascend.db')
            if UPLOAD_DIR.exists():
                for item in sorted(UPLOAD_DIR.rglob('*')):
                    if item.is_file() and item.resolve().parent != BACKUP_DIR.resolve():
                        zf.write(item,Path('uploads')/item.relative_to(UPLOAD_DIR))
    finally:
        try: tmp_db.unlink()
        except OSError: pass
    return target


def list_backups():
    if DATABASE_URL:
        with connect() as conn:
            rows=conn.execute('SELECT name,octet_length(data) AS size,created_at FROM backup_archives ORDER BY created_at DESC').fetchall()
        return [{'name':r['name'],'size':r['size'],'created_at':datetime.fromisoformat(r['created_at']),'kind':'Full backup'} for r in rows]
    files=list(BACKUP_DIR.glob('ascend_*.zip')) + list(BACKUP_DIR.glob('ascend_*.db'))
    items=[]
    for p in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
        stat=p.stat()
        items.append({'name':p.name,'size':stat.st_size,'created_at':datetime.fromtimestamp(stat.st_mtime,timezone.utc),'kind':'Full backup' if p.suffix=='.zip' else 'Legacy DB backup'})
    return items


def prune_backups(retention=None):
    retention = retention or int(os.getenv('PMS_BACKUP_RETENTION','14'))
    if DATABASE_URL:
        with connect() as conn:
            conn.execute('DELETE FROM backup_archives WHERE name IN (SELECT name FROM backup_archives ORDER BY created_at DESC OFFSET ?)',(max(1,retention),))
        return
    files=list(BACKUP_DIR.glob('ascend_*.zip')) + list(BACKUP_DIR.glob('ascend_*.db'))
    files=sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
    for p in files[max(1, retention):]:
        try: p.unlink()
        except OSError: pass


def backup_due(hours=None):
    hours = hours or int(os.getenv('PMS_BACKUP_INTERVAL_HOURS','24'))
    if DATABASE_URL:
        with connect() as conn:
            row=conn.execute("SELECT created_at FROM backup_archives WHERE name LIKE 'ascend_auto-%' ORDER BY created_at DESC LIMIT 1").fetchone()
        return not row or (datetime.now(timezone.utc)-datetime.fromisoformat(row['created_at'])).total_seconds() >= hours*3600
    files=list(BACKUP_DIR.glob('ascend_auto_*.zip')) + list(BACKUP_DIR.glob('ascend_auto_*.db'))
    files=sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        return True
    age = datetime.now(timezone.utc).timestamp() - files[0].stat().st_mtime
    return age >= hours * 3600


def run_scheduled_backup_if_due():
    if os.getenv('PMS_BACKUP_ENABLED','1') != '1':
        return None
    if backup_due():
        out=create_backup('auto')
        prune_backups()
        return out
    return None
