"""Persist uploaded images on local disk or in the PostgreSQL private schema."""
from pathlib import Path
from db import connect, DATA_DIR, DATABASE_URL
from security import iso_now

UPLOAD_DIR = DATA_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(name, data, content_type):
    if Path(name).name != name:
        raise ValueError('Invalid upload name')
    if DATABASE_URL:
        with connect() as conn:
            conn.execute('''INSERT INTO file_assets(name,content_type,data,created_at) VALUES (?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET content_type=excluded.content_type,data=excluded.data,created_at=excluded.created_at''',
                (name, content_type, data, iso_now()))
    else:
        (UPLOAD_DIR / name).write_bytes(data)
    return f'/uploads/{name}'


def delete_upload(name):
    if Path(name).name != name:
        return
    if DATABASE_URL:
        with connect() as conn:
            conn.execute('DELETE FROM file_assets WHERE name=?', (name,))
    else:
        (UPLOAD_DIR / name).unlink(missing_ok=True)


def get_upload(name):
    if Path(name).name != name:
        return None
    with connect() as conn:
        return conn.execute('SELECT data,content_type FROM file_assets WHERE name=?', (name,)).fetchone()


def count_uploads():
    if DATABASE_URL:
        with connect() as conn:
            return conn.execute('SELECT COUNT(*) n FROM file_assets').fetchone()['n']
    return sum(1 for item in UPLOAD_DIR.iterdir() if item.is_file())
