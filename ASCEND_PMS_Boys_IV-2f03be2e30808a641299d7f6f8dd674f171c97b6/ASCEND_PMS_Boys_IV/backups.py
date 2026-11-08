import os, sqlite3, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
from db import DB_PATH, DATA_DIR

BACKUP_DIR = DATA_DIR / 'backups'
UPLOAD_DIR = DATA_DIR / 'uploads'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def create_backup(label='auto'):
    """Create a consistent full ASCEND backup archive.

    The ZIP contains an online SQLite snapshot plus persistent uploaded assets
    such as school branding and student profile pictures.
    """
    if not DB_PATH.exists():
        return None
    safe_label = ''.join(c for c in label.lower() if c.isalnum() or c in ('-','_'))[:24] or 'backup'
    target = BACKUP_DIR / f'ascend_{safe_label}_{_stamp()}.zip'
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
    files=list(BACKUP_DIR.glob('ascend_*.zip')) + list(BACKUP_DIR.glob('ascend_*.db'))
    items=[]
    for p in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
        stat=p.stat()
        items.append({'name':p.name,'size':stat.st_size,'created_at':datetime.fromtimestamp(stat.st_mtime,timezone.utc),'kind':'Full backup' if p.suffix=='.zip' else 'Legacy DB backup'})
    return items


def prune_backups(retention=None):
    retention = retention or int(os.getenv('PMS_BACKUP_RETENTION','14'))
    files=list(BACKUP_DIR.glob('ascend_*.zip')) + list(BACKUP_DIR.glob('ascend_*.db'))
    files=sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)
    for p in files[max(1, retention):]:
        try: p.unlink()
        except OSError: pass


def backup_due(hours=None):
    hours = hours or int(os.getenv('PMS_BACKUP_INTERVAL_HOURS','24'))
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
