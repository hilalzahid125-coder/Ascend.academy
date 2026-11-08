import getpass, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from db import init_db, ensure_admin

init_db()
admission=(input('Admin ID [ADMIN-0001]: ').strip() or 'ADMIN-0001').upper()
name=input('Admin name [School Administrator]: ').strip() or 'School Administrator'
password=getpass.getpass('Admin password: ')
if len(password)<10:
    raise SystemExit('Use at least 10 characters for the admin password.')
ensure_admin(admission,name,password)
print(f'Admin ready: {admission}')
