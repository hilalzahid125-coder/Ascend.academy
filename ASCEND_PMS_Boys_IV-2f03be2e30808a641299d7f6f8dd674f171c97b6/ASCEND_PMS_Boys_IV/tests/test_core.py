import os, sys, tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.gettempdir()) / 'ascend_tests'
TEST_DIR.mkdir(exist_ok=True)
TEST_DB = TEST_DIR / 'ascend_test.db'
if TEST_DB.exists(): TEST_DB.unlink()
os.environ['PMS_DATA_DIR'] = str(TEST_DIR)
os.environ['PMS_DB_PATH'] = str(TEST_DB)
os.environ['PMS_SECURE_COOKIE'] = '0'
os.environ['PMS_BACKUP_ENABLED'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app import app
from db import connect, ensure_admin
from security import iso_now, hash_password


def csrf(client, path='/login'):
    client.get(path)
    token=client.cookies.get('pms_csrf')
    assert token
    return token


def post(client, path, data=None, files=None):
    data=dict(data or {})
    data['csrf_token']=client.cookies.get('pms_csrf') or csrf(client)
    return client.post(path,data=data,files=files,follow_redirects=False)


def setup_module(module):
    from db import init_db
    init_db()
    ensure_admin('ADMIN-0001','Administrator','StrongAdmin123')
    with connect() as c:
        c.execute("UPDATE settings SET value='1' WHERE key='registration_enabled'")
        c.execute('''INSERT INTO users(admission_no,full_name,role,status,class_name,section_name,activation_code,claimed,created_at)
                     VALUES ('A-6738','Ahmed Khan','student','unclaimed','10','A','CODE01',0,?)''',(iso_now(),))
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        c.execute('''INSERT INTO challenges(title,description,category,points,status,created_by,created_at)
                     VALUES ('Math Sprint','Test challenge','academic',100,'active',?,?)''',(admin,iso_now()))


def test_csrf_and_security_headers():
    with TestClient(app) as client:
        r=client.get('/login')
        assert r.status_code==200
        assert r.headers['x-frame-options']=='DENY'
        assert 'content-security-policy' in r.headers
        bad=client.post('/login',data={'admission_no':'ADMIN-0001','password':'StrongAdmin123'},follow_redirects=False)
        assert bad.status_code==403


def test_registration_login_and_role_guard():
    with TestClient(app) as client:
        csrf(client,'/register')
        r=post(client,'/register',{'admission_no':'A-6738','activation_code':'CODE01','password':'Student123','confirm_password':'Student123'})
        assert r.status_code == 303
        r=post(client,'/login',{'admission_no':'A-6738','password':'Student123'})
        assert r.status_code == 303 and r.headers['location']=='/student'
        assert client.get('/student').status_code == 200
        assert client.get('/admin').status_code == 403


def test_admin_and_duplicate_award_protection():
    student=TestClient(app)
    csrf(student)
    post(student,'/login',{'admission_no':'A-6738','password':'Student123'})
    post(student,'/challenges/1/submit',{'submission_text':'Completed'})
    with connect() as c:
        p=c.execute('SELECT id,user_id FROM challenge_participations WHERE challenge_id=1').fetchone()
    assert p is not None
    admin=TestClient(app)
    csrf(admin)
    post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(admin,f'/admin/submissions/{p["id"]}/review',{'decision':'approved','review_note':'ok'})
    post(admin,f'/admin/submissions/{p["id"]}/review',{'decision':'approved','review_note':'again'})
    with connect() as c:
        total=c.execute('SELECT COALESCE(SUM(amount),0) n FROM point_transactions WHERE user_id=?',(p['user_id'],)).fetchone()['n']
    assert total == 100


def test_bulk_csv_import_and_activation_export():
    admin=TestClient(app)
    csrf(admin)
    post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    csv_data='Admission Number,Full Name,Class,Section\nA-7101,Ali Test,9,B\nA-7102,Umar Test,8,A\n'
    r=post(admin,'/admin/students/import',files={'roster':('students.csv',csv_data.encode(),'text/csv')})
    assert r.status_code==200
    assert '2 students added' in r.text
    export=admin.get('/admin/students/activation-codes.csv')
    assert export.status_code==200
    assert 'A-7101' in export.text and 'A-7102' in export.text
    with connect() as c:
        rows=c.execute("SELECT activation_code,activation_code_expires_at FROM users WHERE admission_no IN ('A-7101','A-7102')").fetchall()
        assert len(rows)==2 and all(r['activation_code'] and r['activation_code_expires_at'] for r in rows)


def test_launch_structure_backup_and_hardened_logo_upload():
    admin=TestClient(app)
    csrf(admin)
    post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    page=admin.get('/admin/launch')
    assert page.status_code==200 and 'Launch & backups' in page.text
    r=post(admin,'/admin/launch/prepare-production',{'confirmation':'PREPARE ASCEND'})
    assert r.status_code==303
    with connect() as c:
        assert c.execute("SELECT 1 FROM achievements WHERE name='ASCEND Elite'").fetchone()
        ch=c.execute("SELECT status FROM challenges WHERE title='Creative Showcase'").fetchone()
        assert ch and ch['status']=='draft'
        assert c.execute("SELECT 1 FROM users WHERE admission_no='A-6738'").fetchone() is None
        assert c.execute("SELECT value FROM settings WHERE key='registration_enabled'").fetchone()['value']=='0'
    r=post(admin,'/admin/backups/create')
    assert r.status_code==303
    backup_dir=TEST_DIR/'backups'
    assert any(backup_dir.glob('ascend_manual_*.zip'))
    bad_svg=b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    r=post(admin,'/admin/settings/logo',files={'logo':('school.svg',bad_svg,'image/svg+xml')})
    assert r.status_code==303 and 'SVG%20uploads%20are%20disabled' in r.headers['location']


def test_production_bulk_onboarding_after_prepare():
    admin=TestClient(app)
    csrf(admin)
    post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    csv_data='Admission Number,Full Name,Class,Section\nA-7201,Production Student,10,A\n'
    r=post(admin,'/admin/students/import',files={'roster':('production.csv',csv_data.encode(),'text/csv')})
    assert r.status_code==200
    with connect() as c:
        student=c.execute("SELECT activation_code FROM users WHERE admission_no='A-7201'").fetchone()
        assert student and student['activation_code']
        code=student['activation_code']
    post(admin,'/admin/settings',{'school_name':'Peshawar Model School Boys IV','app_name':'ASCEND','tagline':'Compete • Achieve • Grow','creator_credit':'Made by Abdul Hanan Sethi','registration_enabled':'on'})
    student_client=TestClient(app)
    csrf(student_client,'/register')
    r=post(student_client,'/register',{'admission_no':'A-7201','activation_code':code,'password':'Student7201','confirm_password':'Student7201'})
    assert r.status_code==303 and r.headers['location'].startswith('/login?')
    r=post(student_client,'/login',{'admission_no':'A-7201','password':'Student7201'})
    assert r.status_code==303 and r.headers['location']=='/student'


def test_login_rate_limit():
    client=TestClient(app)
    csrf(client)
    last=None
    for _ in range(9):
        last=post(client,'/login',{'admission_no':'ADMIN-0001','password':'wrong-password'})
    assert last.status_code==303
    assert 'Too%20many%20sign-in%20attempts' in last.headers['location']


def test_super_admin_delegates_staff_permissions_and_protects_owner_controls():
    with connect() as c: c.execute('DELETE FROM auth_attempts')
    owner=TestClient(app)
    csrf(owner)
    post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    r=post(owner,'/admin/admins/create',{
        'admin_id':'ADMIN-0002','full_name':'Activities Coordinator','password':'StaffAdmin1234',
        'permissions':['students','challenges']
    })
    assert r.status_code==303
    page=owner.get('/admin/admins')
    assert page.status_code==200 and 'Activities Coordinator' in page.text
    with connect() as c:
        staff=c.execute("SELECT role,admin_level,admin_permissions FROM users WHERE admission_no='ADMIN-0002'").fetchone()
        assert staff and staff['role']=='admin' and staff['admin_level']=='staff'
        assert 'students' in staff['admin_permissions'] and 'rewards' not in staff['admin_permissions']

    staff_client=TestClient(app)
    csrf(staff_client)
    r=post(staff_client,'/login',{'admission_no':'ADMIN-0002','password':'StaffAdmin1234'})
    assert r.status_code==303 and r.headers['location']=='/admin'
    assert staff_client.get('/admin/students').status_code==200
    assert staff_client.get('/admin/challenges').status_code==200
    assert staff_client.get('/admin/rewards').status_code==403
    assert staff_client.get('/admin/admins').status_code==403
    assert staff_client.get('/admin/settings').status_code==403
    assert staff_client.get('/admin/launch').status_code==403
    assert staff_client.get('/admin/account').status_code==200


def test_student_profile_picture_is_safely_processed_and_persisted():
    from PIL import Image
    import io
    client=TestClient(app)
    csrf(client)
    post(client,'/login',{'admission_no':'A-7201','password':'Student7201'})
    image=Image.new('RGB',(800,500),(230,120,30))
    buf=io.BytesIO(); image.save(buf,'PNG')
    r=post(client,'/profile/photo',files={'photo':('student.png',buf.getvalue(),'image/png')})
    assert r.status_code==303
    with connect() as c:
        row=c.execute("SELECT profile_picture_path FROM users WHERE admission_no='A-7201'").fetchone()
        assert row and row['profile_picture_path'].endswith('.webp')
    page=client.get('/profile')
    assert page.status_code==200 and row['profile_picture_path'] in page.text
    board=client.get('/leaderboards')
    assert board.status_code==200 and row['profile_picture_path'] in board.text


def test_public_presentation_about_privacy_and_version_health():
    client=TestClient(app)
    home=client.get('/')
    assert home.status_code==200
    assert 'Turn effort into' in home.text and 'Peshawar Model School Boys IV' in home.text
    assert client.get('/about').status_code==200
    privacy=client.get('/privacy')
    assert privacy.status_code==200 and 'Privacy in ASCEND' in privacy.text
    health=client.get('/health').json()
    assert health['ok'] is True and health['version']=='1.4.0'


def test_admin_reports_exports_and_staff_permission_boundaries():
    with connect() as c: c.execute('DELETE FROM auth_attempts')
    owner=TestClient(app)
    csrf(owner)
    post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    page=owner.get('/admin/reports')
    assert page.status_code==200 and 'Student points report' in page.text
    report=owner.get('/admin/reports/students.csv')
    assert report.status_code==200 and 'Admission Number,Full Name' in report.text
    challenges=owner.get('/admin/reports/challenges.csv')
    assert challenges.status_code==200 and 'Participation Status' in challenges.text

    staff=TestClient(app)
    csrf(staff)
    post(staff,'/login',{'admission_no':'ADMIN-0002','password':'StaffAdmin1234'})
    assert staff.get('/admin/reports').status_code==200
    assert staff.get('/admin/reports/students.csv').status_code==200
    assert staff.get('/admin/reports/challenges.csv').status_code==200
    # remove the challenges permission and confirm report export is also protected server-side
    with connect() as c:
        c.execute("UPDATE users SET admin_permissions='[\"students\"]' WHERE admission_no='ADMIN-0002'")
    assert staff.get('/admin/reports/challenges.csv').status_code==403
    assert staff.get('/admin/reports/students.csv').status_code==200


def test_launch_center_shows_non_sensitive_system_status():
    with connect() as c: c.execute('DELETE FROM auth_attempts')
    owner=TestClient(app)
    csrf(owner)
    post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    page=owner.get('/admin/launch')
    assert page.status_code==200
    assert 'ASCEND version' in page.text and 'v1.4.0' in page.text
    assert 'Stored uploads' in page.text



def test_student_home_has_leaderboard_challenge_achievement_reward_previews():
    client=TestClient(app)
    csrf(client)
    post(client,'/login',{'admission_no':'A-7201','password':'Student7201'})
    page=client.get('/student')
    assert page.status_code==200
    assert 'School leaderboard' in page.text
    assert 'View all challenges' in page.text
    assert 'Achievements' in page.text
    assert 'Rewards' in page.text
    assert 'Open full leaderboard' in page.text


def test_mobile_drawer_supports_overlay_escape_and_swipe_code():
    client=TestClient(app)
    csrf(client)
    post(client,'/login',{'admission_no':'A-7201','password':'Student7201'})
    page=client.get('/student')
    assert 'id="sidebarOverlay"' in page.text
    assert 'aria-controls="sidebar"' in page.text
    js=client.get('/static/app.js').text
    assert 'function closeSidebar()' in js
    assert 'touchstart' in js and 'touchend' in js
    assert 'sidebarOverlay' in js


def test_profile_identity_css_is_circular():
    client=TestClient(app)
    css=client.get('/static/v14.css').text
    assert 'border-radius:50%!important' in css
    assert '.profile-photo' in css and '.mini-avatar' in css and '.topbar-avatar' in css


def test_super_admin_can_delete_student_with_cascade_but_staff_cannot():
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
        c.execute("DELETE FROM users WHERE admission_no='A-7999'")
        cur=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,class_name,section_name,claimed,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      ('A-7999','Disposable Test Student',hash_password('Disposable123'),'student','active','9','A',1,iso_now()))
        uid=cur.lastrowid
        c.execute('INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,?,?,?,?)',(uid,50,'academic','temporary',iso_now()))
        c.execute('INSERT INTO notifications(user_id,title,body,created_at) VALUES (?,?,?,?)',(uid,'Temp','Temp',iso_now()))
    staff=TestClient(app)
    csrf(staff)
    post(staff,'/login',{'admission_no':'ADMIN-0002','password':'StaffAdmin1234'})
    r=post(staff,f'/admin/students/{uid}/delete')
    assert r.status_code==403
    with connect() as c:
        assert c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone()
    owner=TestClient(app)
    csrf(owner)
    post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    r=post(owner,f'/admin/students/{uid}/delete')
    assert r.status_code==303
    with connect() as c:
        assert c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone() is None
        assert c.execute('SELECT 1 FROM point_transactions WHERE user_id=?',(uid,)).fetchone() is None
        assert c.execute('SELECT 1 FROM notifications WHERE user_id=?',(uid,)).fetchone() is None
