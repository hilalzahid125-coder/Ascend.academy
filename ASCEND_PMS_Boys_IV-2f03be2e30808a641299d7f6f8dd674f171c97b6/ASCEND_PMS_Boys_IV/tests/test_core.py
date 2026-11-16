import os, sys, tempfile
from pathlib import Path

# Isolate each test process: SQLite and PostgreSQL suites can run concurrently.
_TEST_TMP = tempfile.TemporaryDirectory(prefix='ascend_tests_')
TEST_DIR = Path(_TEST_TMP.name)
TEST_DB = TEST_DIR / 'ascend_test.db'
os.environ['PMS_DATA_DIR'] = str(TEST_DIR)
os.environ['PMS_DB_PATH'] = str(TEST_DB)
os.environ['PMS_SECURE_COOKIE'] = '0'
os.environ['PMS_BACKUP_ENABLED'] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app import app
from db import connect, ensure_admin
from security import iso_now, hash_password
from datetime import date, timedelta as _timedelta


def csrf(client, path='/login'):
    client.get(path)
    token=client.cookies.get('pms_csrf')
    assert token
    return token


def post(client, path, data=None, files=None):
    data=dict(data or {})
    data['csrf_token']=client.cookies.get('pms_csrf') or csrf(client)
    return client.post(path,data=data,files=files,follow_redirects=False)


def review_progress(client,record_id,data):
    with connect() as c: version=c.execute('SELECT version FROM student_progress_records WHERE id=?',(record_id,)).fetchone()['version']
    return post(client,f'/admin/teaching/records/{record_id}/review',dict(data,version=version))


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
        import json
        r=post(client,'/register/academy',{'profile':json.dumps(academy_profile(admissionNo='A-6738',activationCode='CODE01',fullName='Ahmed Khan'))})
        assert r.status_code == 200
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
    csv_data='Admission Number,Full Name,Class,Section\nA-7101,Ali Test,O-Level - Grade 9,B\nA-7102,Umar Test,O-Level - Grade 10,A\n'
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
    from backups import list_backups
    assert any(b['name'].startswith('ascend_manual') for b in list_backups())
    bad_svg=b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    r=post(admin,'/admin/settings/logo',files={'logo':('school.svg',bad_svg,'image/svg+xml')})
    assert r.status_code==303 and 'SVG%20uploads%20are%20disabled' in r.headers['location']


def test_production_bulk_onboarding_after_prepare():
    admin=TestClient(app)
    csrf(admin)
    post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    csv_data='Admission Number,Full Name,Class,Section\nA-7201,Production Student,O-Level - Grade 10,A\n'
    r=post(admin,'/admin/students/import',files={'roster':('production.csv',csv_data.encode(),'text/csv')})
    assert r.status_code==200
    with connect() as c:
        student=c.execute("SELECT activation_code FROM users WHERE admission_no='A-7201'").fetchone()
        assert student and student['activation_code']
        code=student['activation_code']
    post(admin,'/admin/settings',{'school_name':'Peshawar Model School Boys IV','app_name':'ASCEND','tagline':'Compete • Achieve • Grow','creator_credit':'Made by Abdul Hanan Sethi','registration_enabled':'on'})
    student_client=TestClient(app)
    csrf(student_client,'/register')
    import json
    r=post(student_client,'/register/academy',{'profile':json.dumps(academy_profile(admissionNo='A-7201',activationCode=code,fullName='Production Student',password='Student7201',confirmPassword='Student7201'))})
    assert r.status_code==200 and r.json()['redirect']=='/student'
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
    assert 'Academy leaderboard' in page.text
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
        uid=c.execute("SELECT id FROM users WHERE admission_no='A-7999'").fetchone()['id']
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


def academy_profile(**changes):
    profile = {'fullName': 'New Student', 'email': 'student@example.com', 'phone': '03001112222',
               'countryCode': '+92', 'gender': 'Male', 'dob': '2010-02-03',
               'guardianName': 'Parent', 'guardianPhone': '03001234567', 'country': 'Pakistan',
               'province': 'Khyber Pakhtunkhwa', 'program': 'O-Level', 'subjects': ['Maths'],
               'schoolName': 'Test School', 'schoolRegion': 'Peshawar', 'schoolType': 'Private', 'grade': 'O-Level - Grade 10',
               'section': 'A', 'admissionNo': 'A-9981', 'activationCode': 'CODE81',
               'password': 'Student123', 'confirmPassword': 'Student123', 'terms': True, 'captcha': '5'}
    profile.update(changes)
    return profile


def test_academy_signup_connects_real_dashboard():
    import json
    with connect() as c:
        c.execute('''INSERT INTO users(admission_no,full_name,role,status,class_name,section_name,activation_code,claimed,created_at)
                     VALUES ('A-9981','School Record','student','unclaimed','10','A','CODE81',0,?)''', (iso_now(),))
    with TestClient(app) as client:
        page = client.get('/register')
        assert page.status_code == 200 and '/static/academy-signup/signup.js' in page.text
        assert client.get('/static/academy-signup/signup.js').status_code == 200
        bad = post(client, '/register/academy', {'profile': json.dumps(academy_profile(activationCode='WRONG'))})
        assert bad.status_code == 400
        assert client.get('/student', follow_redirects=False).status_code == 303
        good = post(client, '/register/academy', {'profile': json.dumps(academy_profile())})
        assert good.status_code == 200 and good.json()['redirect'] == '/student'
        assert client.get('/student').status_code == 200
        replay = post(client, '/register/academy', {'profile': json.dumps(academy_profile())})
        assert replay.status_code == 400
    with connect() as c:
        row = c.execute("SELECT u.full_name,u.claimed,p.profile_json FROM users u JOIN academy_signup_profiles p ON p.user_id=u.id WHERE u.admission_no='A-9981'").fetchone()
        assert row['full_name'] == 'New Student' and row['claimed'] == 1
        saved = json.loads(row['profile_json'])
        assert saved['email'] == 'student@example.com' and 'password' not in saved and 'activationCode' not in saved


def test_academy_signup_respects_csrf_and_registration_setting():
    import json
    with TestClient(app) as client:
        csrf(client, '/register')
        assert client.post('/register/academy', data={'profile': json.dumps(academy_profile())}).status_code == 403
        with connect() as c:
            c.execute("UPDATE settings SET value='0' WHERE key='registration_enabled'")
        try:
            page = client.get('/register')
            assert 'data-registration-enabled="0"' in page.text
            assert post(client, '/register/academy', {'profile': json.dumps(academy_profile())}).status_code == 400
        finally:
            with connect() as c:
                c.execute("UPDATE settings SET value='1' WHERE key='registration_enabled'")


def test_branding_defaults_migrate_without_overwriting_custom_credit():
    from db import init_db, get_settings
    with connect() as c:
        original = get_settings(c)
        c.execute("UPDATE settings SET value='Made by Abdul Hanan Sethi' WHERE key='creator_credit'")
        c.execute("UPDATE settings SET value='#f97316' WHERE key='primary_color'")
    try:
        init_db()
        with connect() as c:
            migrated = get_settings(c)
            assert migrated['creator_credit'] == 'Made by Hilal Zahid'
            assert migrated['primary_color'] == '#c20a0a'
        with TestClient(app) as client:
            assert 'Made by Hilal Zahid' in client.get('/').text
            assert '#087f63' in client.get('/static/design-system.css').text.lower()
            assert '#064e3b' in client.get('/static/app-logo.svg').text.lower()
        with connect() as c:
            c.execute("UPDATE settings SET value='Custom credit' WHERE key='creator_credit'")
        init_db()
        with connect() as c:
            assert get_settings(c)['creator_credit'] == 'Custom credit'
    finally:
        with connect() as c:
            c.execute("UPDATE settings SET value=? WHERE key='creator_credit'", (original['creator_credit'],))
            c.execute("UPDATE settings SET value=? WHERE key='primary_color'", (original['primary_color'],))


def test_end_to_end_academy_and_role_workflow():
    """School creates a student; academy activation, challenges and rewards share real records."""
    import json
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
        c.execute("UPDATE settings SET value='1' WHERE key='registration_enabled'")
    with TestClient(app) as owner, TestClient(app) as student, TestClient(app) as staff:
        csrf(owner)
        assert post(owner, '/login', {'admission_no':'ADMIN-0001','password':'StrongAdmin123'}).headers['location'] == '/admin'
        assert post(owner, '/admin/students/create', {'admission_no':'A-9901','full_name':'Flow Student','class_name':'O-Level - Grade 10','section_name':'A'}).status_code == 303
        with connect() as c:
            record = c.execute("SELECT id,activation_code FROM users WHERE admission_no='A-9901'").fetchone()
            student_id, code = record['id'], record['activation_code']

        page = student.get('/register')
        assert page.status_code == 200 and 'data-registration-enabled="1"' in page.text
        data = academy_profile(admissionNo='A-9901', activationCode=code, fullName='Flow Student')
        # Match the browser's multipart FormData request, rather than only urlencoded requests.
        activated = student.post('/register/academy', files={
            'csrf_token': (None, student.cookies['pms_csrf']),
            'profile': (None, json.dumps(data)),
        })
        assert activated.status_code == 200 and activated.json()['redirect'] == '/student'
        assert 'Flow Student' in student.get('/student').text
        assert student.get('/admin').status_code == 403
        for path in ('/challenges','/leaderboards','/achievements','/rewards','/notifications','/profile'):
            assert student.get(path).status_code == 200, path

        assert post(owner, '/admin/admins/create', {'admin_id':'ADMIN-0099','full_name':'Workflow Staff','password':'StaffAdmin9900','permissions':['students','challenges']}).status_code == 303
        csrf(staff)
        assert post(staff, '/login', {'admission_no':'ADMIN-0099','password':'StaffAdmin9900'}).headers['location'] == '/admin'
        assert staff.get('/admin/students').status_code == 200
        assert staff.get('/admin/challenges').status_code == 200
        assert staff.get('/admin/admins').status_code == 403
        assert post(staff, '/admin/rewards/create', {'name':'Unauthorized','description':'No','points_required':'10'}).status_code == 403

        for title, klass in [('Flow Challenge', 'O-Level - Grade 10'), ('Restricted Challenge', 'O-Level - Grade 9')]:
            r=post(staff, '/admin/challenges/create', {'title':title,'description':'Show your work','category':'academic','points':'50','status':'active','eligibility_class':klass,'eligibility_section':'A'})
            assert r.status_code == 303 and 'Challenge%20created' in r.headers['location']
        assert post(owner,'/admin/achievements/create',{'name':'Flow Achievement','description':'Great work','category':'academic','points_required':'50'}).status_code == 303
        assert post(owner,'/admin/rewards/create',{'name':'Flow Reward','description':'A prize','points_required':'50'}).status_code == 303
        assert post(owner,'/admin/announcements/create',{'title':'Flow Announcement','body':'Welcome','audience':'class','class_name':'O-Level - Grade 10'}).status_code == 303
        with connect() as c:
            allowed=c.execute("SELECT id FROM challenges WHERE title='Flow Challenge'").fetchone()['id']
            restricted=c.execute("SELECT id FROM challenges WHERE title='Restricted Challenge'").fetchone()['id']
            reward=c.execute("SELECT id FROM rewards WHERE name='Flow Reward'").fetchone()['id']
        assert 'Flow Challenge' in student.get('/challenges').text
        assert 'Restricted Challenge' not in student.get('/challenges').text
        assert 'Flow Announcement' in student.get('/student').text
        for action in ('join','submit'):
            res=post(student,f'/challenges/{restricted}/{action}',{'submission_text':'not eligible'} if action=='submit' else {})
            assert 'not%20eligible' in res.headers['location']
        with connect() as c:
            assert c.execute('SELECT 1 FROM challenge_participations WHERE challenge_id=? AND user_id=?',(restricted,student_id)).fetchone() is None
        assert 'required%20points' in post(student,f'/rewards/{reward}/claim').headers['location']
        assert 'Challenge%20joined' in post(student,f'/challenges/{allowed}/join').headers['location']
        assert 'Submission%20sent' in post(student,f'/challenges/{allowed}/submit',{'submission_text':'Finished my work'}).headers['location']
        with connect() as c:
            participation=c.execute('SELECT id FROM challenge_participations WHERE challenge_id=? AND user_id=?',(allowed,student_id)).fetchone()['id']
        assert 'Finished my work' in staff.get('/admin/challenges').text
        assert 'Submission%20reviewed' in post(staff,f'/admin/submissions/{participation}/review',{'decision':'approved'}).headers['location']
        assert 'not%20awaiting%20review' in post(staff,f'/admin/submissions/{participation}/review',{'decision':'approved'}).headers['location']
        assert 'already%20been%20approved' in post(student,f'/challenges/{allowed}/submit',{'submission_text':'Again'}).headers['location']
        with connect() as c:
            assert c.execute('SELECT SUM(amount) n FROM point_transactions WHERE user_id=?',(student_id,)).fetchone()['n'] == 50
            assert c.execute('SELECT COUNT(*) n FROM student_achievements sa JOIN achievements a ON a.id=sa.achievement_id WHERE sa.user_id=? AND a.name=?',(student_id,'Flow Achievement')).fetchone()['n'] == 1
        assert 'Flow Achievement' in student.get('/achievements').text
        assert 'Flow Student' in student.get('/leaderboards').text
        assert 'Flow Reward' in student.get('/rewards').text
        post(student,f'/rewards/{reward}/claim'); post(student,f'/rewards/{reward}/claim')
        with connect() as c:
            claim=c.execute('SELECT id,status FROM reward_claims WHERE reward_id=? AND user_id=?',(reward,student_id)).fetchone()
            assert claim and claim['status']=='pending'
            assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND title='Reward claim submitted'",(student_id,)).fetchone()['n'] == 1
        assert post(owner,f'/admin/reward-claims/{claim["id"]}/status',{'status':'approved'}).status_code==303
        assert 'Approved' in student.get('/rewards').text
        assert 'Reward claim updated' in student.get('/notifications').text
        assert post(student,'/notifications/read-all').status_code == 303
        assert post(student,'/logout').status_code == 303
        assert student.get('/student',follow_redirects=False).status_code == 303
        assert post(student,'/login',{'admission_no':'A-9901','password':'Student123'}).headers['location']=='/student'


def test_activation_security_and_zero_point_reward():
    import json
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
        c.execute("UPDATE settings SET value='1' WHERE key='registration_enabled'")
        for adm, status, code in [('A-9902','disabled','SAFE01'),('A-9903','unclaimed',None)]:
            c.execute('INSERT INTO users(admission_no,full_name,role,status,activation_code,claimed,created_at) VALUES (?,?,\'student\',?,?,0,?)',(adm,'Security Test',status,code,iso_now()))
    with TestClient(app) as client:
        csrf(client, '/register')
        for adm, code in [('A-9902','SAFE01'),('A-9903','')]:
            r=post(client,'/register',{'admission_no':adm,'activation_code':code,'password':'Student123','confirm_password':'Student123'})
            assert r.status_code == 303 and 'complete%20the%20academy%20registration' in r.headers['location']
        r=post(client,'/register/academy',{'profile':json.dumps(academy_profile(admissionNo='A-9902', activationCode='SAFE01'))})
        assert r.status_code==400
    with TestClient(app) as owner:
        csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
        r=post(owner,'/admin/rewards/create',{'name':'Zero Reward','description':'invalid','points_required':'0'})
        assert 'invalid' in r.headers['location']
        with connect() as c:
            assert c.execute("SELECT 1 FROM rewards WHERE name='Zero Reward'").fetchone() is None


def test_reward_inventory_cannot_be_over_approved():
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
        other_id=c.execute("SELECT id FROM users WHERE admission_no='A-7201'").fetchone()['id']
    with TestClient(app) as owner, TestClient(app) as first, TestClient(app) as second:
        csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
        csrf(first); post(first,'/login',{'admission_no':'A-9901','password':'Student123'})
        csrf(second); post(second,'/login',{'admission_no':'A-7201','password':'Student7201'})
        post(owner,f'/admin/students/{other_id}/points',{'amount':'50','category':'academic','reason':'Inventory test'})
        post(owner,'/admin/rewards/create',{'name':'Limited Reward','description':'One available','points_required':'20','quantity':'1'})
        with connect() as c:
            reward=c.execute("SELECT id FROM rewards WHERE name='Limited Reward'").fetchone()['id']
        assert 'submitted' in post(first,f'/rewards/{reward}/claim').headers['location']
        assert 'submitted' in post(second,f'/rewards/{reward}/claim').headers['location']
        with connect() as c:
            claims=c.execute('SELECT id,user_id FROM reward_claims WHERE reward_id=? ORDER BY id',(reward,)).fetchall()
            assert len(claims)==2
        assert 'Claim%20updated' in post(owner,f'/admin/reward-claims/{claims[0]["id"]}/status',{'status':'approved'}).headers['location']
        assert 'out%20of%20stock' in post(owner,f'/admin/reward-claims/{claims[1]["id"]}/status',{'status':'approved'}).headers['location']
        with connect() as c:
            assert c.execute("SELECT COUNT(*) n FROM reward_claims WHERE reward_id=? AND status IN ('approved','fulfilled')",(reward,)).fetchone()['n']==1
        assert 'out%20of%20stock' in post(second,f'/rewards/{reward}/claim').headers['location']


def test_simultaneous_challenge_reviews_award_only_once():
    from concurrent.futures import ThreadPoolExecutor
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
    with TestClient(app) as first_admin, TestClient(app) as second_admin, TestClient(app) as student:
        for admin in (first_admin, second_admin):
            csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
        csrf(student); post(student,'/login',{'admission_no':'A-9901','password':'Student123'})
        post(first_admin,'/admin/challenges/create',{'title':'Concurrent Review','description':'Concurrency test','category':'academic','points':'30','status':'active'})
        with connect() as c: challenge=c.execute("SELECT id FROM challenges WHERE title='Concurrent Review'").fetchone()['id']
        post(student,f'/challenges/{challenge}/submit',{'submission_text':'Ready for review'})
        with connect() as c: participation=c.execute('SELECT id FROM challenge_participations WHERE challenge_id=?',(challenge,)).fetchone()['id']
        def review(admin):
            return post(admin,f'/admin/submissions/{participation}/review',{'decision':'approved'}).headers['location']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(review, (first_admin, second_admin)))
        assert sum('Submission%20reviewed' in loc for loc in results) == 1
        with connect() as c:
            row=c.execute('SELECT COUNT(*) n,SUM(amount) total FROM point_transactions WHERE challenge_id=?',(challenge,)).fetchone()
            assert row['n']==1 and row['total']==30


def test_https_embedded_preview_cookie_settings(monkeypatch):
    monkeypatch.setenv('PMS_PREVIEW_PARTITIONED_COOKIES','1')
    with connect() as c: c.execute('DELETE FROM auth_attempts')
    with TestClient(app, base_url='https://testserver') as client:
        page=client.get('/login')
        cookie=page.headers.get('set-cookie','').lower()
        assert 'samesite=none' in cookie and 'secure' in cookie and 'partitioned' in cookie
        r=post(client,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
        cookie=r.headers.get('set-cookie','').lower()
        assert r.headers['location']=='/admin' and 'httponly' in cookie and 'secure' in cookie and 'partitioned' in cookie
        assert client.get('/admin').status_code==200
        out=post(client,'/logout')
        assert 'partitioned' in out.headers.get('set-cookie','').lower()


def test_security_error_is_visible_to_signed_out_users():
    with TestClient(app) as client:
        response = client.post('/login', data={'admission_no':'ADMIN-0001', 'password':'incorrect'})
        assert response.status_code == 403
        assert 'Security session expired' in response.text
        assert 'cookies are unavailable' in response.text
        assert 'Return to sign in' in response.text
        response = client.post('/register/academy', data={'profile':'{}'})
        assert response.status_code == 403 and 'security session' in response.json()['detail'].lower()


def test_vercel_cannot_silently_use_ephemeral_sqlite():
    import subprocess
    env = dict(os.environ, VERCEL='1')
    env.pop('PMS_DATABASE_URL', None)
    result = subprocess.run([sys.executable, '-c', 'import db'], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'requires PMS_DATABASE_URL' in result.stderr


def test_upload_can_be_served_and_backup_contains_data():
    import io, zipfile
    from PIL import Image
    from backups import create_backup, backup_bytes
    from db import DATABASE_URL
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
    with TestClient(app) as student:
        csrf(student); post(student,'/login',{'admission_no':'A-9901','password':'Student123'})
        picture=io.BytesIO(); Image.new('RGB',(80,80),(20,60,120)).save(picture,'PNG')
        assert post(student,'/profile/photo',files={'photo':('photo.png',picture.getvalue(),'image/png')}).status_code == 303
        with connect() as c:
            row=c.execute("SELECT id,profile_picture_path FROM users WHERE admission_no='A-9901'").fetchone()
        image=student.get(row['profile_picture_path'])
        assert image.status_code==200 and image.headers['content-type'].startswith('image/webp')
        archive=create_backup('test')
        data=backup_bytes(archive.name)
        assert data
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert 'ascend.db' in z.namelist()
            assert 'uploads/profile_%s.webp' % row['id'] in z.namelist()
            assert z.read('uploads/profile_%s.webp' % row['id']) == image.content
        assert student.get('/uploads/not-a-photo').status_code==404


def test_scheduled_backup_requires_secret(monkeypatch):
    monkeypatch.setenv('CRON_SECRET', 'a-long-random-cron-secret')
    with TestClient(app) as client:
        assert client.get('/internal/scheduled-backup').status_code == 403
        assert client.get('/internal/scheduled-backup', headers={'Authorization': 'Bearer wrong'}).status_code == 403
        response = client.get('/internal/scheduled-backup', headers={'Authorization': 'Bearer a-long-random-cron-secret'})
        assert response.status_code == 200
        assert response.json() == {'ok': True, 'created': False}


def test_bootstrap_does_not_promote_existing_staff():
    with connect() as c:
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,created_at) VALUES (?,?,?,?,?,?,?,?)",
                  ('BOOTSTRAP-STAFF','Staff',hash_password('Password123'),'admin','active',1,'staff',iso_now()))
    ensure_admin('BOOTSTRAP-STAFF', 'Staff', 'DifferentPassword123')
    with connect() as c:
        row=c.execute("SELECT admin_level FROM users WHERE admission_no='BOOTSTRAP-STAFF'").fetchone()
        assert row['admin_level'] == 'staff'


def test_academy_details_are_consistent_and_private():
    import json
    with connect() as c:
        c.execute('DELETE FROM auth_attempts')
        row=c.execute("SELECT id,full_name,class_name,section_name FROM users WHERE admission_no='A-9901'").fetchone()
        student_id=row['id']
    with TestClient(app) as student, TestClient(app) as owner:
        csrf(student); post(student,'/login',{'admission_no':'A-9901','password':'Student123'})
        overview=student.get('/student')
        assert overview.status_code == 200
        for text in ('Flow Student','O-Level - Grade 10','Test School','Pakistan','Maths'):
            assert text in overview.text
        assert 'Attendance' not in overview.text
        csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
        listing=owner.get('/admin/students').text
        for text in ('Parent','03001112222','student@example.com','Pakistan','Test School','O-Level - Grade 10'):
            assert text in listing
        updated=post(owner,f'/admin/students/{student_id}/edit',{
            'full_name':'Flow Student','class_name':'A-Level - AS (Grade 12)','section_name':'B',
            'guardian_name':'Parent Updated','phone':'123456789','country_code':'+92',
            'email':'updated@example.com','country':'Pakistan','school_name':'Updated School'})
        assert updated.status_code == 303 and 'updated' in updated.headers['location']
        overview=student.get('/student').text
        assert 'A-Level - AS (Grade 12)' in overview and 'Updated School' in overview
        with connect() as c:
            stored=json.loads(c.execute('SELECT profile_json FROM academy_signup_profiles WHERE user_id=?',(student_id,)).fetchone()['profile_json'])
            assert stored['guardianName']=='Parent Updated' and stored['program']=='A-Level'
            assert stored['subjects']==['Maths']
        # A bad new grade is rejected without overwriting the record.
        bad=post(owner,f'/admin/students/{student_id}/edit',{'full_name':'Flow Student','class_name':'Grade 3','section_name':'B'})
        assert 'valid%20academy%20grade' in bad.headers['location']
        with connect() as c:
            assert c.execute('SELECT class_name FROM users WHERE id=?',(student_id,)).fetchone()['class_name']=='A-Level - AS (Grade 12)'
        assert student.get('/admin/students').status_code == 403


def test_signup_rejects_unsupported_grade_subject_and_missing_school():
    import json
    with connect() as c:
        c.execute("UPDATE settings SET value='1' WHERE key='registration_enabled'")
        c.execute('DELETE FROM auth_attempts')
    with TestClient(app) as client:
        csrf(client,'/register')
        for changed in ({'grade':'Grade 3'}, {'subjects':['Physics']}, {'schoolName':''}, {'phone':''}):
            result=post(client,'/register/academy',{'profile':json.dumps(academy_profile(**changed))})
            assert result.status_code==400


def test_roster_template_and_unsupported_grade_validation():
    with connect() as c: c.execute('DELETE FROM auth_attempts')
    with TestClient(app) as owner:
        csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
        template=owner.get('/admin/students/import-template.csv')
        assert template.text.splitlines()[1]=='A-7001,Student Name,O-Level - Grade 10,A'
        r=post(owner,'/admin/students/import',files={'roster':('roster.csv',b'Admission Number,Full Name,Grade,Section\nA-8877,Invalid Grade,Grade 2,A\n','text/csv')})
        assert r.status_code==200 and 'valid O-Level or A-Level' in r.text
        with connect() as c: assert not c.execute("SELECT 1 FROM users WHERE admission_no='A-8877'").fetchone()


def test_my_classes_schedule_roster_attendance_and_isolation(monkeypatch):
    import json
    import app as app_module
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(app_module, '_class_now', lambda: datetime(2026, 11, 9, 10, 0, tzinfo=ZoneInfo('Asia/Karachi')))
    with connect() as c:
        for admission,name,grade,subjects in [
            ('T-8401','Class Student One','O-Level - Grade 9',['Maths','Computer Science']),
            ('T-8402','Class Student Two','O-Level - Grade 9',['Maths']),
            ('T-8403','Class Student Three','O-Level - Grade 10',['Maths'])]:
            c.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at)
                VALUES (?,?,?,'student','active',1,?,?)''',(admission,name,hash_password('ClassTest1234'),grade,iso_now()))
            u=c.execute('SELECT id FROM users WHERE admission_no=?',(admission,)).fetchone()
            c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(u['id'],json.dumps({'subjects':subjects}),iso_now()))
        ids={r['admission_no']:r['id'] for r in c.execute("SELECT id,admission_no FROM users WHERE admission_no IN ('T-8401','T-8402','T-8403')").fetchall()}
        admin_id=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
    admin=TestClient(app); csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    student=TestClient(app); csrf(student); post(student,'/login',{'admission_no':'T-8401','password':'ClassTest1234'})
    other=TestClient(app); csrf(other); post(other,'/login',{'admission_no':'T-8403','password':'ClassTest1234'})
    assert student.get('/admin/my-classes').status_code==403
    assert other.get('/my-classes').status_code==200
    data={'grade':'O-Level - Grade 9','subject':'Maths','teacher_id':str(admin_id),'recurrence':'weekly','weekday':'0','start_time':'09:00','duration_minutes':'60'}
    assert post(admin,'/admin/my-classes/create',data).status_code==303
    with connect() as c: schedule=c.execute("SELECT id FROM class_schedules WHERE grade=? AND subject=?",(data['grade'],data['subject'])).fetchone()['id']
    assert '09:00' in student.get('/my-classes').text
    assert '09:00' not in other.get('/my-classes').text
    assert 'Class Student Two' in admin.get('/admin/my-classes').text
    # A single-student change must not move the rest of the grade.
    r=post(admin,'/admin/my-classes/update',{'selection':f'{schedule}:{ids["T-8401"]}','start_time':'11:00'})
    assert 'updated' in r.headers['location'].lower()
    assert '11:00' in student.get('/my-classes').text and '09:00' not in student.get('/my-classes').text
    second=TestClient(app); csrf(second); post(second,'/login',{'admission_no':'T-8402','password':'ClassTest1234'})
    assert '09:00' in second.get('/my-classes').text and '11:00' not in second.get('/my-classes').text
    # Base roster excludes the individually rescheduled student.
    post(admin,f'/admin/my-classes/{schedule}/start')
    with connect() as c:
        session=c.execute('SELECT id FROM class_sessions WHERE schedule_id=?',(schedule,)).fetchone()['id']
        roster=c.execute('SELECT student_id,status FROM class_attendance WHERE session_id=?',(session,)).fetchall()
        assert [r['student_id'] for r in roster]==[ids['T-8402']]
        assert c.execute('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND title=?',(ids['T-8402'],'Class session started')).fetchone()['n']==1
    assert 'Join live class' in second.get('/my-classes').text
    assert 'Join live class' not in student.get('/my-classes').text
    assert post(student,f'/admin/my-classes/session/{session}/end').status_code==403
    assert 'already%20been%20started' in post(admin,f'/admin/my-classes/{schedule}/start').headers['location']
    post(admin,f'/admin/my-classes/session/{session}/end')
    post(admin,f'/admin/my-classes/session/{session}/attendance',{f'attendance_{ids["T-8402"]}':'present'})
    response=second.get('/my-classes').text
    assert '100<small>%</small>' in response and '1 <small>class</small>' in response
    assert '100<small>%</small>' not in student.get('/my-classes').text
    with connect() as c:
        assert c.execute('SELECT status FROM class_attendance WHERE session_id=? AND student_id=?',(session,ids['T-8402'])).fetchone()['status']=='present'
        assert c.execute('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND title=?',(ids['T-8402'],'Attendance updated')).fetchone()['n']==1
    # Once-only schedule runs only on its specified date.
    data.update({'recurrence':'once','class_date':'2026-11-10','start_time':'14:00'})
    post(admin,'/admin/my-classes/create',data)
    with connect() as c: once=c.execute("SELECT id FROM class_schedules WHERE recurrence='once'").fetchone()['id']
    assert 'scheduled%20day' in post(admin,f'/admin/my-classes/{once}/start').headers['location']


def test_my_classes_subject_edit_and_student_deletion():
    import json
    admin=TestClient(app); csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    with connect() as c:
        student=c.execute("SELECT id FROM users WHERE admission_no='T-8401'").fetchone()['id']
        override=c.execute('SELECT id FROM class_schedules WHERE student_id=? AND parent_id IS NOT NULL',(student,)).fetchone()['id']
        original=c.execute('SELECT parent_id FROM class_schedules WHERE id=?',(override,)).fetchone()['parent_id']
    # Removing an individual override restores the group class, and reapplying it works.
    assert 'removed' in post(admin,f'/admin/my-classes/{override}/remove').headers['location'].lower()
    assert 'updated' in post(admin,'/admin/my-classes/update',{'selection':f'{original}:{student}','start_time':'12:00'}).headers['location'].lower()
    with connect() as c:
        assert c.execute('SELECT active,start_time FROM class_schedules WHERE id=?',(override,)).fetchone()['start_time']=='12:00'
    data={'full_name':'Class Student One','class_name':'O-Level - Grade 9','subjects_present':'1','subjects':'Computer Science'}
    assert 'updated' in post(admin,f'/admin/students/{student}/edit',data).headers['location'].lower()
    with connect() as c:
        profile=json.loads(c.execute('SELECT profile_json FROM academy_signup_profiles WHERE user_id=?',(student,)).fetchone()['profile_json'])
        assert profile['subjects']==['Computer Science']
    client=TestClient(app); csrf(client); post(client,'/login',{'admission_no':'T-8401','password':'ClassTest1234'})
    assert '12:00' not in client.get('/my-classes').text
    # Existing student deletion remains functional even with class data.
    assert post(admin,f'/admin/students/{student}/delete').status_code==303
    with connect() as c:
        assert c.execute('SELECT id FROM users WHERE id=?',(student,)).fetchone() is None
        assert c.execute('SELECT id FROM class_schedules WHERE id=?',(override,)).fetchone() is None


def test_achievement_sync_avoids_per_achievement_queries():
    from app import sync_achievements
    with connect() as c:
        student=c.execute("SELECT id FROM users WHERE admission_no='T-8402'").fetchone()['id']
        sync_achievements(c,student)
        class CountQueries:
            def __init__(self,conn): self.conn=conn; self.count=0
            def execute(self,sql,params=()):
                self.count+=1
                return self.conn.execute(sql,params)
        counter=CountQueries(c)
        scores=sync_achievements(counter,student)
        assert counter.count==2
        assert scores['overall']==0


def test_attendance_batch_corrections_and_notifications():
    admin=TestClient(app); csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    with connect() as c:
        a=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        ids=[c.execute('SELECT id FROM users WHERE admission_no=?',(n,)).fetchone()['id'] for n in ('T-8402','T-8403')]
        schedule=c.execute('SELECT id FROM class_schedules WHERE parent_id IS NULL').fetchone()['id']
        c.execute("""INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at)
            VALUES (?,'2026-12-31','Maths','O-Level - Grade 9','09:00',40,?,?,'ended',?)""",(schedule,a,a,iso_now()))
        session=c.execute("SELECT id FROM class_sessions WHERE schedule_id=? AND session_date='2026-12-31'",(schedule,)).fetchone()['id']
        for uid in ids: c.execute('INSERT INTO class_attendance(session_id,student_id) VALUES (?,?)',(session,uid))
    path=f'/admin/my-classes/session/{session}/attendance'
    data={f'attendance_{ids[0]}':'present',f'attendance_{ids[1]}':'absent'}
    post(admin,path,data)
    with connect() as c:
        rows=c.execute('SELECT student_id,status FROM class_attendance WHERE session_id=? ORDER BY student_id',(session,)).fetchall()
        assert {r['student_id']:r['status'] for r in rows}=={ids[0]:'present',ids[1]:'absent'}
        before=c.execute("SELECT COUNT(*) n FROM notifications WHERE title='Attendance updated' AND user_id IN (?,?)",ids).fetchone()['n']
    post(admin,path,data)
    with connect() as c:
        after=c.execute("SELECT COUNT(*) n FROM notifications WHERE title='Attendance updated' AND user_id IN (?,?)",ids).fetchone()['n']
        assert after==before
    post(admin,path,{f'attendance_{ids[0]}':'',f'attendance_{ids[1]}':'present'})
    with connect() as c:
        rows=c.execute('SELECT student_id,status FROM class_attendance WHERE session_id=?',(session,)).fetchall()
        assert {r['student_id']:r['status'] for r in rows}=={ids[0]:None,ids[1]:'present'}


def test_postgres_pool_rolls_back_and_recovers_closed_connections():
    import pytest
    from db import DATABASE_URL, init_db
    if not DATABASE_URL: pytest.skip('PostgreSQL-specific connection test')
    init_db()  # Repeated initialization must use the existing migration ledger.
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM app_schema_migrations').fetchone()['n']>=3
    with pytest.raises(RuntimeError):
        with connect() as c:
            c.execute("INSERT INTO settings(key,value) VALUES ('pool_rollback_test','not committed')")
            raise RuntimeError('rollback')
    with connect() as c:
        assert c.execute("SELECT value FROM settings WHERE key='pool_rollback_test'").fetchone() is None
        c.connection.close()  # Simulate an idle connection closed by the server.
    with connect() as c:
        assert c.execute('SELECT 1 AS value').fetchone()['value']==1


def test_auth_and_display_settings_stay_fresh_between_requests():
    client=TestClient(app); csrf(client); post(client,'/login',{'admission_no':'T-8402','password':'ClassTest1234'})
    with connect() as c:
        previous=c.execute("SELECT value FROM settings WHERE key='school_name'").fetchone()['value']
        c.execute("UPDATE settings SET value='New Fresh Academy' WHERE key='school_name'")
    try:
        assert 'New Fresh Academy' in client.get('/my-classes').text
        with connect() as c: c.execute("UPDATE users SET status='disabled' WHERE admission_no='T-8402'")
        assert client.get('/my-classes').status_code==403
        with connect() as c: c.execute("UPDATE users SET status='active' WHERE admission_no='T-8402'")
        assert client.get('/my-classes').status_code==200
    finally:
        with connect() as c:
            c.execute("UPDATE settings SET value=? WHERE key='school_name'",(previous,))
            c.execute("UPDATE users SET status='active' WHERE admission_no='T-8402'")


def test_live_class_room_authorization_lifecycle_and_randomness(monkeypatch):
    import re
    import app as app_module
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(app_module,'_class_now',lambda: datetime(2026,12,31,10,tzinfo=ZoneInfo('Asia/Karachi')))
    with connect() as c:
        teacher=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        student=c.execute("SELECT id FROM users WHERE admission_no='T-8402'").fetchone()['id']
        for index in range(2):
            c.execute("""INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,class_date,start_time,duration_minutes,created_at)
                VALUES ('O-Level - Grade 9','Maths',?,'once','2026-12-31',?,40,?)""",(teacher,f'{index+10}:00',iso_now()))
        schedules=[r['id'] for r in c.execute("SELECT id FROM class_schedules WHERE class_date='2026-12-31' ORDER BY id").fetchall()][-2:]
    admin=TestClient(app);csrf(admin);post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    pupil=TestClient(app);csrf(pupil);post(pupil,'/login',{'admission_no':'T-8402','password':'ClassTest1234'})
    outsider=TestClient(app);csrf(outsider);post(outsider,'/login',{'admission_no':'T-8403','password':'ClassTest1234'})
    rooms=[]
    for sched in schedules:
        response=post(admin,f'/admin/my-classes/{sched}/start')
        assert 'open_session=' in response.headers['location']
        with connect() as c:
            session=c.execute("SELECT id FROM class_sessions WHERE schedule_id=?",(sched,)).fetchone()['id']
            room=c.execute('SELECT room_name FROM class_live_rooms WHERE session_id=?',(session,)).fetchone()['room_name']
        rooms.append(room)
        assert re.fullmatch(r'DeltaAcademy[a-f0-9]{48}',room)
        page=pupil.get('/my-classes')
        assert room not in page.text and 'meet.jit.si/' not in page.text
        assert 'frame-src \'self\' https://meet.jit.si' in page.headers['content-security-policy']
        assert 'camera=(self "https://meet.jit.si")' in page.headers['permissions-policy']
        assert post(outsider,f'/my-classes/live/{session}/room').status_code==404
        assert outsider.get(f'/my-classes/live/{session}/status').status_code==404
        assert pupil.post(f'/my-classes/live/{session}/room').status_code==403
        for who in (pupil,admin):
            response=post(who,f'/my-classes/live/{session}/room')
            assert response.status_code==200 and response.json()['room']==room
            assert response.headers['cache-control']=='no-store'
            assert who.get(f'/my-classes/live/{session}/status').status_code==200
        # A live session created before this feature gets an idempotent room on first open.
        with connect() as c: c.execute('DELETE FROM class_live_rooms WHERE session_id=?',(session,))
        replacement=post(pupil,f'/my-classes/live/{session}/room').json()['room']
        assert replacement!=room and replacement==post(admin,f'/my-classes/live/{session}/room').json()['room']
        post(admin,f'/admin/my-classes/session/{session}/end')
        assert post(pupil,f'/my-classes/live/{session}/room').status_code==404
        assert admin.get(f'/my-classes/live/{session}/status').status_code==404
    assert rooms[0]!=rooms[1]


def test_fee_management_manual_workflow_and_security():
    import io, secrets
    from PIL import Image
    with connect() as c:
        for no,name,grade in [('F-8801','Fee Student','Fee Grade'),('F-8802','Other Student','Fee Grade')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,class_name,claimed,created_at) VALUES (?,?,?,'student','active',?,1,?)",(no,name,hash_password('StudentFee123'),grade,iso_now()))
        student_id=c.execute("SELECT id FROM users WHERE admission_no='F-8801'").fetchone()['id']
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-FEE1','Limited Staff',?,'admin','active',1,'staff','[]',?)",(hash_password('LimitedAdmin123'),iso_now()))
    admin=TestClient(app); student=TestClient(app); other=TestClient(app); staff=TestClient(app)
    for client,no,pw in [(admin,'ADMIN-0001','StrongAdmin123'),(student,'F-8801','StudentFee123'),(other,'F-8802','StudentFee123'),(staff,'ADMIN-FEE1','LimitedAdmin123')]:
        csrf(client); assert post(client,'/login',{'admission_no':no,'password':pw}).status_code==303
    assert staff.get('/admin/fees').status_code==403
    assert student.get('/admin/fees').status_code==403
    assert admin.get('/admin/fees').status_code==200
    post(admin,'/admin/fees/methods',{'name':'Transfer','currency':'PKR','holder':'Academy','account':'1234'})
    with connect() as c: method=c.execute("SELECT id FROM fee_methods WHERE name='Transfer'").fetchone()['id']
    token=secrets.token_hex(16)
    assignment={'batch_key':token,'title':'Term fee','period':'2027','installment':'First','amount':'1000.00','currency':'PKR','scope':'grade','grade':'Fee Grade','due_date':'2030-01-01'}
    assert post(admin,'/admin/fees/assign',assignment).status_code==303
    post(admin,'/admin/fees/assign',assignment)
    with connect() as c:
        fees=c.execute('SELECT * FROM fee_assignments WHERE batch_key=? ORDER BY student_id',(token,)).fetchall()
        assert len(fees)==2
        fee=next(f for f in fees if f['student_id']==student_id)
    page=student.get('/fees'); assert page.status_code==200 and 'Term fee' in page.text and '1,000.00' in page.text
    with connect() as c: c.execute("UPDATE fee_methods SET active=0 WHERE id=?",(method,))
    unavailable=student.get(f'/fees/{fee["id"]}/pay').text
    assert 'Receipt submission unavailable' in unavailable and 'name="receipt"' in unavailable and 'disabled' in unavailable
    assert 'Payment method needed' in admin.get('/admin/fees').text
    with connect() as c: c.execute("UPDATE fee_methods SET active=1 WHERE id=?",(method,))
    assert student.get(f'/fees/{fee["id"]}/pay').status_code==200
    assert other.get(f'/fees/{fee["id"]}/pay').status_code==404
    assert '1234' in student.get(f'/fees/{fee["id"]}/pay').text
    edit={'title':'Term fee','period':'2027','installment':'First','amount':'1000.00','currency':'PKR','due_date':'2030-01-01'}
    assert 'Fee%20updated' in post(admin,f'/admin/fees/{fee["id"]}/edit',edit).headers['location']
    assert post(staff,f'/admin/fees/{fee["id"]}/edit',edit).status_code==403
    image=io.BytesIO(); Image.new('RGB',(8,8),'white').save(image,format='PNG'); data=image.getvalue()
    form={'submission_key':secrets.token_hex(16),'method_id':str(method),'amount':'400.00','currency':'PKR','payment_date':'2024-01-01','reference':'REF-1','notes':'Paid from my account <test>'}
    upload={'receipt':('receipt.png',data,'image/png')}
    assert post(other,f'/fees/{fee["id"]}/submit',form,files=upload).status_code==404
    bad=dict(form,amount='1000.01',submission_key=secrets.token_hex(16))
    assert 'exceeds' in post(student,f'/fees/{fee["id"]}/submit',bad,files=upload).headers['location']
    bad=dict(form,submission_key=secrets.token_hex(16))
    assert 'valid%20image' in post(student,f'/fees/{fee["id"]}/submit',bad,files={'receipt':('fake.png',b'not an image','image/png')}).headers['location']
    assert post(student,f'/fees/{fee["id"]}/submit',form,files=upload).status_code==303
    post(student,f'/fees/{fee["id"]}/submit',form,files=upload)
    with connect() as c:
        payments=c.execute('SELECT id,status FROM fee_payments WHERE fee_id=?',(fee['id'],)).fetchall(); assert len(payments)==1 and payments[0]['status']=='submitted'
        payment=payments[0]['id']
    assert other.get(f'/fees/receipt/{payment}').status_code==404
    assert staff.get(f'/fees/receipt/{payment}').status_code==403
    assert student.get(f'/fees/receipt/{payment}').headers['content-type']=='image/webp'
    assert admin.get('/notifications').status_code==200 and 'Fee receipt submitted' in admin.get('/notifications').text
    assert 'Submitted for Verification' in student.get('/fees').text
    admin_page=admin.get('/admin/fees').text
    for value in ['1 awaiting review','Fee Student','F-8801','Fee Grade','First','REF-1','Paid from my account &lt;test&gt;',f'/fees/receipt/{payment}','Current outstanding']:
        assert value in admin_page
    assert 'Paid from my account' not in other.get('/fees').text
    assert 'cannot%20be%20edited' in post(admin,f'/admin/fees/{fee["id"]}/edit',edit).headers['location']
    assert 'pending%20submission' in post(student,f'/fees/{fee["id"]}/submit',dict(form,submission_key=secrets.token_hex(16)),files=upload).headers['location']
    post(admin,f'/admin/fees/payments/{payment}/review',{'decision':'rejected'})
    with connect() as c: assert c.execute('SELECT status FROM fee_payments WHERE id=?',(payment,)).fetchone()['status']=='submitted'
    post(admin,f'/admin/fees/payments/{payment}/review',{'decision':'rejected','note':'Please send a clearer image'})
    assert 'Please send a clearer image' in student.get('/fees').text
    assert 'Reviewed payments (1)' in admin.get('/admin/fees').text
    form['submission_key']=secrets.token_hex(16)
    post(student,f'/fees/{fee["id"]}/submit',form,files=upload)
    with connect() as c: second=c.execute('SELECT MAX(id) id FROM fee_payments WHERE fee_id=?',(fee['id'],)).fetchone()['id']
    post(admin,f'/admin/fees/payments/{second}/review',{'decision':'approved'})
    post(admin,f'/admin/fees/payments/{second}/review',{'decision':'approved'})
    page=student.get('/fees'); assert 'Partially Paid' in page.text and '600.00' in page.text
    assert 'Fee payment approved' in student.get('/notifications').text
    with connect() as c: c.execute("UPDATE users SET admin_permissions=? WHERE admission_no=?", ('["fees"]','ADMIN-FEE1'))
    assert staff.get('/admin/fees').status_code==200
    assert staff.get(f'/fees/receipt/{payment}').status_code==200
    form.update(submission_key=secrets.token_hex(16),amount='600.00')
    post(student,f'/fees/{fee["id"]}/submit',form,files=upload)
    with connect() as c: third=c.execute('SELECT MAX(id) id FROM fee_payments WHERE fee_id=?',(fee['id'],)).fetchone()['id']
    post(staff,f'/admin/fees/payments/{third}/review',{'decision':'approved'})
    assert 'Paid' in student.get('/fees').text
    assert 'already%20paid' in student.get(f'/fees/{fee["id"]}/pay',follow_redirects=False).headers['location']
    r=post(admin,f'/admin/students/{student_id}/delete'); assert 'cannot%20be%20deleted' in r.headers['location']
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM fee_payments WHERE fee_id=?',(fee['id'],)).fetchone()['n']==3
        assert c.execute('SELECT id FROM users WHERE id=?',(student_id,)).fetchone()


def test_fee_backup_restore_preserves_private_receipts():
    import pytest
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup, backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        before=c.execute("SELECT id,receipt,status FROM fee_payments WHERE status='approved' ORDER BY id DESC LIMIT 1").fetchone()
        assert before
        before=dict(before)
    backup=create_backup('fee-test')
    path=TEST_DIR/'fee-restore-test.zip'; path.write_bytes(backup_bytes(backup.name))
    restore_backup(path)
    with connect() as c:
        after=c.execute('SELECT receipt,status FROM fee_payments WHERE id=?',(before['id'],)).fetchone()
        assert bytes(after['receipt'])==bytes(before['receipt']) and after['status']==before['status']


def test_fee_currency_picker_preserves_currency_and_supports_other():
    import secrets
    admin=TestClient(app); csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    page=admin.get('/admin/fees')
    assert 'Pakistani rupee (PKR)' in page.text and 'US dollar (USD)' in page.text
    for name,currency,other,expected in [('PKR choice','PKR','','PKR'),('Dollar choice','USD','','USD'),('Other choice','OTHER','jpy','JPY')]:
        r=post(admin,'/admin/fees/methods',{'name':name,'currency':currency,'currency_other':other,'account':'123'})
        assert 'Payment%20method%20saved' in r.headers['location']
        with connect() as c:
            m=c.execute('SELECT id,currency FROM fee_methods WHERE name=?',(name,)).fetchone()
            assert m['currency']==expected
            if expected=='JPY': other_id=m['id']
    page=admin.get('/admin/fees').text
    assert 'value="OTHER" selected' in page and 'value="JPY"' in page
    assert 'Payment%20method%20saved' in post(admin,'/admin/fees/methods',{'method_id':other_id,'name':'Other choice','currency':'OTHER','currency_other':'JPY','account':'123'}).headers['location']
    invalid=post(admin,'/admin/fees/methods',{'name':'Invalid choice','currency':'OTHER','currency_other':'US','account':'123'})
    assert 'three-letter' in invalid.headers['location']
    with connect() as c:
        student=c.execute("SELECT id FROM users WHERE admission_no='F-8801'").fetchone()['id']
        assert not c.execute("SELECT id FROM fee_methods WHERE name='Invalid choice'").fetchone()
    assignment={'batch_key':secrets.token_hex(16),'scope':'student','student_id':student,'title':'Dollar fee','period':'2028','amount':'25.00','currency':'USD'}
    assert 'Fee%20assigned' in post(admin,'/admin/fees/assign',assignment).headers['location']
    with connect() as c: assert c.execute("SELECT currency FROM fee_assignments WHERE batch_key=?",(assignment['batch_key'],)).fetchone()['currency']=='USD'


def test_daily_timetable_selected_days_one_off_and_session():
    import json
    from app import _class_now
    with connect() as c:
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,class_name,claimed,created_at) VALUES ('T-8804','Timetable Student',?,'student','active','O-Level - Grade 9',1,?)",(hash_password('ClassTest1234'),iso_now()))
        student_id=c.execute("SELECT id FROM users WHERE admission_no='T-8804'").fetchone()['id']
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(student_id,json.dumps({'subjects':['Maths']}),iso_now()))
        teacher=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
    admin=TestClient(app); student=TestClient(app)
    csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    csrf(student); post(student,'/login',{'admission_no':'T-8804','password':'ClassTest1234'})
    today=_class_now().date(); days=sorted({str(today.weekday()),str((today.weekday()+1)%7)})
    base={'grade':'O-Level - Grade 9','subject':'Maths','teacher_id':str(teacher),'student_id':str(student_id),'recurrence':'daily','days':days,'start_time':'11:20','duration_minutes':'40'}
    assert 'added' in post(admin,'/admin/my-classes/create',base).headers['location']
    with connect() as c:
        schedules=c.execute("SELECT * FROM class_schedules WHERE student_id=? AND start_time='11:20' ORDER BY weekday",(student_id,)).fetchall()
        assert len(schedules)==2 and {s['weekday'] for s in schedules}=={int(d) for d in days}
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND title='Class scheduled'",(student_id,)).fetchone()['n']==1
    page=student.get('/my-classes'); assert page.status_code==200 and page.text.count('11:20')>=2
    for entry in schedules: assert entry['recurrence']=='weekly'
    current=next(s for s in schedules if s['weekday']==today.weekday())
    start=post(admin,f'/admin/my-classes/{current["id"]}/start')
    assert 'open_session' in start.headers['location']
    assert 'Join live class' in student.get('/my-classes').text
    invalid=dict(base,days=['0','9'],start_time='12:20')
    assert 'valid%20day' in post(admin,'/admin/my-classes/create',invalid).headers['location']
    with connect() as c: assert not c.execute("SELECT id FROM class_schedules WHERE student_id=? AND start_time='12:20'",(student_id,)).fetchone()
    once=dict(base,recurrence='once',class_date=today.isoformat(),start_time='13:30')
    assert 'added' in post(admin,'/admin/my-classes/create',once).headers['location']
    assert '13:30' in student.get('/my-classes').text


def test_challenge_all_section_legacy_normalization_and_permissions():
    import json
    with connect() as c:
        student=c.execute("SELECT id FROM users WHERE admission_no='T-8804'").fetchone()['id']
        c.execute("UPDATE users SET section_name='A' WHERE id=?",(student,))
        admin_id=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        c.execute("INSERT INTO challenges(title,description,category,points,status,eligibility_section,created_by,created_at) VALUES ('Legacy All Section','Test','general',10,'active','All section',?,?)",(admin_id,iso_now()))
        legacy=c.execute("SELECT id FROM challenges WHERE title='Legacy All Section'").fetchone()['id']
    admin=TestClient(app); client=TestClient(app)
    csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    csrf(client); post(client,'/login',{'admission_no':'T-8804','password':'ClassTest1234'})
    assert 'Legacy All Section' in client.get('/student').text
    assert 'Legacy All Section' in client.get('/challenges').text
    assert 'joined' in post(client,f'/challenges/{legacy}/join').headers['location']
    assert 'sent%20for%20review' in post(client,f'/challenges/{legacy}/submit',{'submission_text':'Completed'}).headers['location']
    with connect() as c: participation=c.execute('SELECT id FROM challenge_participations WHERE challenge_id=? AND user_id=?',(legacy,student)).fetchone()['id']
    post(admin,f'/admin/submissions/{participation}/review',{'decision':'approved'})
    post(admin,f'/admin/submissions/{participation}/review',{'decision':'approved'})
    with connect() as c: assert c.execute('SELECT COUNT(*) n FROM point_transactions WHERE user_id=? AND challenge_id=?',(student,legacy)).fetchone()['n']==1
    for title,section in [('Open to all','ALL SECTIONS'),('Restricted section','B')]:
        post(admin,'/admin/challenges/create',{'title':title,'description':'Test','status':'active','eligibility_section':section})
    with connect() as c:
        open_challenge=c.execute("SELECT eligibility_section FROM challenges WHERE title='Open to all'").fetchone()
        restricted=c.execute("SELECT id FROM challenges WHERE title='Restricted section'").fetchone()['id']
        assert open_challenge['eligibility_section'] is None
    assert 'Open to all' in client.get('/challenges').text
    assert 'Restricted section' not in client.get('/challenges').text
    assert 'not%20eligible' in post(client,f'/challenges/{restricted}/join').headers['location']


def test_parent_accounts_authorization_and_live_records():
    import io, secrets
    from PIL import Image
    owner=TestClient(app); parent=TestClient(app); other=TestClient(app); staff=TestClient(app); student=TestClient(app)
    with connect() as c:
        for no,name in [('A-88171','Parent Test Student'),('A-88172','Unlinked Test Student')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES (?,?,?,'student','active',1,'Test Grade',?)",(no,name,hash_password('StudentStrong123'),iso_now()))
        child=c.execute("SELECT id FROM users WHERE admission_no='A-88171'").fetchone()['id']
        stranger=c.execute("SELECT id FROM users WHERE admission_no='A-88172'").fetchone()['id']
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-PARENT1','Limited Staff',?,'admin','active',1,'staff','[]',?)",(hash_password('LimitedAdmin123'),iso_now()))
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(staff,'ADMIN-PARENT1','LimitedAdmin123'),(student,'A-88171','StudentStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/fees/methods',{'name':'Parent Test Method','currency':'PKR','account':'test'})
    with connect() as c: method=c.execute("SELECT id FROM fee_methods WHERE name='Parent Test Method'").fetchone()['id']
    key=secrets.token_hex(16)
    post(owner,'/admin/fees/assign',{'batch_key':key,'title':'Parent Test Fee','period':'2026','amount':'100','currency':'PKR','scope':'student','student_id':child})
    with connect() as c: fee=c.execute('SELECT id FROM fee_assignments WHERE batch_key=?',(key,)).fetchone()['id']
    image=io.BytesIO(); Image.new('RGB',(8,8),'white').save(image,format='PNG')
    post(student,f'/fees/{fee}/submit',{'submission_key':secrets.token_hex(16),'method_id':method,'amount':'50','currency':'PKR','payment_date':'2024-01-01'},files={'receipt':('receipt.png',image.getvalue(),'image/png')})
    with connect() as c: payment=c.execute('SELECT id FROM fee_payments WHERE fee_id=?',(fee,)).fetchone()['id']
    assert staff.get('/admin/parents').status_code==403
    assert post(staff,'/admin/parents/create',{'full_name':'Denied','student_id':child,'password':'ParentStrong123'}).status_code==403
    r=post(owner,'/admin/parents/create',{'full_name':'Test Guardian','student_id':child,'password':'ParentStrong123'})
    assert 'P-88171' in r.headers['location']
    post(owner,'/admin/parents/create',{'full_name':'Second Guardian','student_id':child,'password':'ParentStrong123'})
    with connect() as c:
        one=c.execute("SELECT id FROM users WHERE admission_no='P-88171' AND role='parent'").fetchone()['id']
        two=c.execute("SELECT id FROM users WHERE admission_no='P-88171-2' AND role='parent'").fetchone()['id']
    csrf(parent); assert post(parent,'/login',{'admission_no':'P-88171','password':'ParentStrong123'}).headers['location']=='/parent'
    page=parent.get('/parent'); assert page.status_code==200 and 'Parent Test Student' in page.text
    assert 'Parent Test Fee' in parent.get(f'/parent/children/{child}/fees').text
    assert parent.get(f'/parent?child={stranger}').status_code==404
    pdf=parent.get(f'/parent/children/{child}/report.pdf')
    assert pdf.status_code==200 and pdf.headers['content-type']=='application/pdf' and pdf.content.startswith(b'%PDF-')
    assert parent.get(f'/parent/children/{stranger}/report.pdf').status_code==404
    assert parent.get('/admin/parents').status_code==403
    assert parent.get('/student').status_code==403
    assert parent.get('/leaderboards').status_code==403
    assert parent.get(f'/fees/receipt/{payment}').status_code==200
    post(owner,f'/admin/parents/{one}/link',{'student_id':stranger})
    assert 'Unlinked Test Student' in parent.get(f'/parent?child={stranger}').text
    post(owner,f'/admin/parents/{one}/unlink',{'student_id':child})
    assert parent.get(f'/parent?child={child}').status_code==404
    assert parent.get(f'/fees/receipt/{payment}').status_code==404
    assert parent.get(f'/parent/children/{child}/report.pdf').status_code==404
    csrf(other); post(other,'/login',{'admission_no':'P-88171-2','password':'ParentStrong123'})
    assert other.get(f'/parent?child={child}').status_code==200
    post(owner,f'/admin/parents/{two}/update',{'full_name':'Second Guardian','status':'disabled'})
    assert other.get('/parent',follow_redirects=False).status_code==303
    assert 'not%20active' in post(other,'/login',{'admission_no':'P-88171-2','password':'ParentStrong123'}).headers['location']


def test_teacher_progress_is_scoped_and_reviewed():
    import json
    with connect() as c:
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-TEACHER1','Teacher One',?,'admin','active',1,'staff',?,?)",(hash_password('TeacherStrong123'),'["teaching"]',iso_now()))
        teacher=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-TEACHER1'").fetchone()['id']
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES ('A-994319','Progress Student',?,'student','active',1,'O-Level - Grade 9',?)",(hash_password('StudentStrong123'),iso_now()))
        student=c.execute("SELECT id FROM users WHERE admission_no='A-994319'").fetchone()['id']
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(student,json.dumps({'subjects':['Maths']}),iso_now()))
        c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('O-Level - Grade 9','Maths',?,'weekly',0,'09:00',40,?)",(teacher,iso_now()))
    owner=TestClient(app); tutor=TestClient(app); guardian=TestClient(app)
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(tutor,'ADMIN-TEACHER1','TeacherStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    assert 'Progress Student' in tutor.get('/admin/teaching').text
    post(owner,'/admin/parents/create',{'full_name':'Progress Guardian','student_id':student,'password':'ParentStrong123'})
    csrf(guardian); post(guardian,'/login',{'admission_no':'P-994319','password':'ParentStrong123'})
    record={'student_id':student,'subject':'Maths','kind':'assessment','title':'Assessment One','details':'Good progress','record_date':'2024-01-01','score':'0','score_max':'20'}
    assert 'submitted%20for' in post(tutor,'/admin/teaching/records',record).headers['location']
    assert 'Assessment One' not in guardian.get('/parent').text
    with connect() as c: rid=c.execute("SELECT id FROM student_progress_records WHERE title='Assessment One'").fetchone()['id']
    assert review_progress(tutor,rid,{'decision':'approved'}).status_code==403
    assert post(tutor,'/admin/teaching/records',dict(record,subject='Computer Science')).status_code==403
    review_progress(owner,rid,{'decision':'approved'})
    assert 'Assessment One' in guardian.get(f'/parent/children/{student}/report').text
    assert 'New assessment result' in guardian.get('/notifications').text
    review_progress(owner,rid,{'decision':'approved'})
    with connect() as c: assert c.execute("SELECT COUNT(*) n FROM notifications WHERE title='New assessment result' AND kind='assessment' AND user_id=(SELECT id FROM users WHERE admission_no='P-994319')").fetchone()['n']==1


def test_sqlite_parent_role_migration_preserves_foreign_keys_and_data(tmp_path):
    import sqlite3
    from db import SCHEMA, _migrate_sqlite_parent_role
    conn=sqlite3.connect(tmp_path/'legacy.db'); conn.row_factory=sqlite3.Row
    legacy=SCHEMA.replace("role TEXT NOT NULL CHECK(role IN ('student','admin','parent','teacher'))", "role TEXT NOT NULL CHECK(role IN ('student','admin'))")
    conn.executescript(legacy)
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('A-1234','Legacy','student','active',?)",(iso_now(),))
    uid=conn.execute("SELECT id FROM users WHERE admission_no='A-1234'").fetchone()['id']
    conn.execute("INSERT INTO notifications(user_id,title,body,created_at) VALUES (?,'Old','Preserved',?)",(uid,iso_now()))
    conn.execute("CREATE INDEX legacy_user_name ON users(full_name)")
    conn.commit(); conn.execute('PRAGMA foreign_keys=ON')
    _migrate_sqlite_parent_role(conn)
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('P-1234','Parent','parent','active',?)",(iso_now(),))
    assert conn.execute('SELECT body FROM notifications WHERE user_id=?',(uid,)).fetchone()['body']=='Preserved'
    assert not conn.execute('PRAGMA foreign_key_check').fetchone()
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='legacy_user_name'").fetchone()
    _migrate_sqlite_parent_role(conn)
    conn.close()


def test_parent_attendance_and_fee_are_live_and_link_scoped():
    import io,secrets
    from PIL import Image
    owner=TestClient(app); parent=TestClient(app); student=TestClient(app); stranger=TestClient(app)
    with connect() as c:
        for no,name in [('A-88231','Linked Calendar Student'),('A-88232','Other Calendar Student')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES (?,?,?,'student','active',1,'Calendar Grade',?)",(no,name,hash_password('StudentStrong123'),iso_now()))
        sid=c.execute("SELECT id FROM users WHERE admission_no='A-88231'").fetchone()['id']
        uid=c.execute("SELECT id FROM users WHERE admission_no='A-88232'").fetchone()['id']
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        schedule=c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('Calendar Grade','Maths',?,'weekly',0,'09:00',40,?) RETURNING id",(admin,iso_now())).fetchone()['id']
        session=c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at,ended_at) VALUES (?,'2024-01-01','Maths','Calendar Grade','09:00',40,?,?,'ended',?,?) RETURNING id",(schedule,admin,admin,iso_now(),iso_now())).fetchone()['id']
        c.execute("INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,'present')",(session,sid))
        c.execute("INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,'absent')",(session,uid))
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(student,'A-88231','StudentStrong123'),(stranger,'A-88232','StudentStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/parents/create',{'full_name':'Calendar Parent','student_id':sid,'password':'ParentStrong123'})
    csrf(parent); post(parent,'/login',{'admission_no':'P-88231','password':'ParentStrong123'})
    page=parent.get(f'/parent/children/{sid}/attendance?month=2024-01&day=2024-01-01').text
    assert '2024-01-01, present recorded' in page and '09:00 · Maths · Present' in page
    assert 'Other Calendar Student' not in page and '100%' in page
    assert parent.get('/parent?month=2024-02&day=2024-01-01').status_code==400
    assert parent.get('/admin/holidays').status_code==403
    assert post(parent,'/admin/holidays',{'holiday_date':'2024-01-02','title':'School holiday'}).status_code==403
    assert owner.get('/admin/holidays').status_code==200
    post(owner,'/admin/holidays',{'holiday_date':'2024-01-02','title':'School holiday'})
    holiday=parent.get(f'/parent/children/{sid}/attendance?month=2024-01&day=2024-01-02').text
    assert '2024-01-02, holiday: School holiday' in holiday and 'Holiday · School holiday' in holiday
    assert 'No marked completed sessions on this date.' in holiday
    post(owner,'/admin/holidays/remove',{'holiday_date':'2024-01-02'})
    assert 'Holiday · School holiday' not in parent.get(f'/parent/children/{sid}/attendance?month=2024-01&day=2024-01-02').text
    post(owner,f'/admin/my-classes/session/{session}/attendance',{f'attendance_{sid}':'late',f'attendance_{uid}':'absent'})
    page=parent.get(f'/parent/children/{sid}/attendance?month=2024-01&day=2024-01-01').text
    assert '2024-01-01, late recorded' in page and '09:00 · Maths · Late' in page and '100%' in page
    post(owner,f'/admin/my-classes/session/{session}/attendance',{f'attendance_{sid}':'excused',f'attendance_{uid}':'absent'})
    page=parent.get(f'/parent/children/{sid}/attendance?month=2024-01&day=2024-01-01').text
    assert '2024-01-01, excused recorded' in page and '09:00 · Maths · Excused' in page and 'Not recorded' in page
    post(owner,'/admin/fees/methods',{'name':'Calendar Transfer','currency':'PKR','account':'test'})
    with connect() as c: method=c.execute("SELECT id FROM fee_methods WHERE name='Calendar Transfer'").fetchone()['id']
    key=secrets.token_hex(16)
    post(owner,'/admin/fees/assign',{'batch_key':key,'scope':'student','student_id':sid,'title':'Calendar Fee','period':'2024','amount':'100','currency':'PKR'})
    with connect() as c: fee=c.execute('SELECT id FROM fee_assignments WHERE batch_key=?',(key,)).fetchone()['id']
    assert 'Fee assigned' in parent.get('/notifications').text
    assert '100.00' in parent.get('/parent').text
    image=io.BytesIO(); Image.new('RGB',(8,8),'white').save(image,format='PNG')
    post(student,f'/fees/{fee}/submit',{'submission_key':secrets.token_hex(16),'method_id':method,'amount':'40','currency':'PKR','payment_date':'2024-01-01'},files={'receipt':('receipt.png',image.getvalue(),'image/png')})
    with connect() as c: pay=c.execute('SELECT id FROM fee_payments WHERE fee_id=?',(fee,)).fetchone()['id']
    assert 'Submitted for Verification' in parent.get(f'/parent/children/{sid}/fees').text
    post(owner,f'/admin/fees/payments/{pay}/review',{'decision':'approved'})
    page=parent.get(f'/parent/children/{sid}/fees').text
    assert 'Partially Paid' in page and '60.00' in page and '40.00' in page
    assert 'Fee payment approved' in parent.get('/notifications').text
    post(parent,'/notifications/read-all')
    assert 'unread' not in parent.get('/notifications').text.split('<section class="panel">',1)[1].split('</section>',1)[0]
    assert stranger.get(f'/fees/receipt/{pay}').status_code==404


def test_restricted_teacher_account_and_class_scope():
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    owner=TestClient(app); tutor=TestClient(app); stranger=TestClient(app)
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    assert owner.get('/admin/teachers').status_code==200
    assert 'created' in post(owner,'/admin/teachers/create',{'teacher_id':'T-UNIT773','full_name':'Scoped Teacher','password':'TeacherStrong123'}).headers['location']
    with connect() as c:
        tid=c.execute("SELECT id FROM users WHERE admission_no='T-UNIT773'").fetchone()['id']
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES ('A-TEACH773','Scoped Child',?,'student','active',1,'O-Level - Grade 11',?)",(hash_password('StudentStrong123'),iso_now()))
        child=c.execute("SELECT id FROM users WHERE admission_no='A-TEACH773'").fetchone()['id']
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(child,json.dumps({'subjects':['Maths']}),iso_now()))
        today=datetime.now(ZoneInfo('Asia/Karachi')).date().isoformat()
        schedule=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,class_date,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 11','Maths',?,'once',?,'09:00',40,?) RETURNING id",(child,tid,today,iso_now())).fetchone()['id']
        other=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        other_schedule=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,class_date,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 11','Maths',?,'once',?,'10:00',40,?) RETURNING id",(child,other,today,iso_now())).fetchone()['id']
    csrf(tutor); assert post(tutor,'/login',{'admission_no':'T-UNIT773','password':'TeacherStrong123'}).headers['location']=='/teacher'
    for path in ['/teacher','/teacher/classes','/teacher/progress','/teacher/account',f'/teacher/students/{child}']:
        r=tutor.get(path); assert r.status_code==200, (path,r.status_code,r.text[:200])
    assert 'Scoped Child' in tutor.get('/teacher').text
    for path in ['/admin','/admin/fees','/admin/teachers','/admin/parents','/admin/my-classes','/admin/teaching','/student','/fees','/leaderboards']:
        assert tutor.get(path).status_code==403,path
    assert tutor.get('/teacher/students/99999999').status_code==404
    assert post(tutor,f'/teacher/classes/{other_schedule}/start').status_code==404
    assert post(tutor,f'/admin/my-classes/{schedule}/start').status_code==403
    assert post(tutor,f'/teacher/classes/{schedule}/start').status_code==303
    with connect() as c: session=c.execute('SELECT id FROM class_sessions WHERE schedule_id=?',(schedule,)).fetchone()['id']
    assert post(tutor,f'/my-classes/live/{session}/room').status_code==200
    with connect() as c: c.execute('UPDATE class_schedules SET active=0 WHERE id=?',(schedule,))
    assert tutor.get(f'/my-classes/live/{session}/status').status_code==404
    with connect() as c: c.execute('UPDATE class_schedules SET active=1 WHERE id=?',(schedule,))
    assert post(tutor,f'/teacher/classes/session/{session}/end').status_code==303
    assert post(tutor,f'/teacher/classes/session/{session}/attendance',{f'attendance_{child}':'present'}).status_code==303
    assert 'Present' in tutor.get(f'/teacher/students/{child}').text
    assert post(tutor,'/teacher/progress/records',{'student_id':child,'subject':'Computer Science','kind':'feedback','title':'No','record_date':'2024-01-01'}).status_code==403
    assert post(tutor,'/teacher/progress/records',{'student_id':child,'subject':'Maths','kind':'feedback','title':'Scoped feedback','record_date':'2024-01-01'}).status_code==303
    with connect() as c:
        c.execute('UPDATE class_schedules SET active=0 WHERE id=?',(schedule,))
    assert tutor.get(f'/teacher/students/{child}').status_code==404
    assert 'Scoped Child' not in tutor.get('/teacher/classes').text
    post(tutor,f'/teacher/classes/session/{session}/attendance',{f'attendance_{child}':'absent'})
    with connect() as c: assert c.execute('SELECT status FROM class_attendance WHERE session_id=? AND student_id=?',(session,child)).fetchone()['status']=='present'
    assert post(tutor,f'/admin/teachers/{tid}/update',{'full_name':'Scoped Teacher','status':'disabled'}).status_code==403
    post(owner,f'/admin/teachers/{tid}/update',{'full_name':'Scoped Teacher','status':'disabled'})
    assert tutor.get('/teacher',follow_redirects=False).status_code==303


def test_sqlite_existing_parent_role_upgrades_to_teacher(tmp_path):
    import sqlite3
    from db import SCHEMA, _migrate_sqlite_parent_role
    conn=sqlite3.connect(tmp_path/'parent.db'); conn.row_factory=sqlite3.Row
    conn.executescript(SCHEMA.replace("role TEXT NOT NULL CHECK(role IN ('student','admin','parent','teacher'))", "role TEXT NOT NULL CHECK(role IN ('student','admin','parent'))"))
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('P-OTHER','Guardian','parent','active',?)",(iso_now(),)); conn.commit()
    _migrate_sqlite_parent_role(conn)
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('T-OTHER','Teacher','teacher','active',?)",(iso_now(),))
    assert conn.execute("SELECT COUNT(*) n FROM users WHERE role IN ('parent','teacher')").fetchone()['n']==2
    assert not conn.execute('PRAGMA foreign_key_check').fetchone(); conn.close()


def test_sqlite_attendance_status_migration_preserves_data(tmp_path):
    import sqlite3
    from db import SCHEMA, _migrate_sqlite_attendance_status
    conn=sqlite3.connect(tmp_path/'old_attendance.db'); conn.row_factory=sqlite3.Row
    conn.executescript(SCHEMA.replace("status TEXT CHECK(status IN ('present','absent','late','excused') OR status IS NULL)","status TEXT CHECK(status IN ('present','absent') OR status IS NULL)"))
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('A-TEST1','Student','student','active',?)",(iso_now(),))
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('ADMIN-TEST1','Admin','admin','active',?)",(iso_now(),))
    st=conn.execute("SELECT id FROM users WHERE admission_no='A-TEST1'").fetchone()['id']; admin=conn.execute("SELECT id FROM users WHERE admission_no='ADMIN-TEST1'").fetchone()['id']
    schedule=conn.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('Grade','Maths',?,'weekly',0,'09:00',40,?)",(admin,iso_now())).lastrowid
    session=conn.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at) VALUES (?,'2024-01-01','Maths','Grade','09:00',40,?,?,'ended',?)",(schedule,admin,admin,iso_now())).lastrowid
    conn.execute("INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,'present')",(session,st)); conn.commit()
    _migrate_sqlite_attendance_status(conn)
    assert conn.execute('SELECT status FROM class_attendance').fetchone()['status']=='present'
    conn.execute("UPDATE class_attendance SET status='late'"); conn.execute("UPDATE class_attendance SET status='excused'")
    assert not conn.execute('PRAGMA foreign_key_check').fetchone()
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='idx_class_attendance_student'").fetchone()
    _migrate_sqlite_attendance_status(conn); conn.close()


def test_parent_teacher_and_holiday_postgres_backup_restore():
    import pytest
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup, backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        c.execute("INSERT INTO academy_holidays(holiday_date,title,created_at) VALUES ('2024-06-01','Restore holiday',?)",(iso_now(),))
        session=c.execute("SELECT s.id FROM class_sessions s JOIN users t ON t.id=s.teacher_id WHERE t.admission_no='T-UNIT773'").fetchone()['id']
        c.execute("UPDATE class_attendance SET status='late' WHERE session_id=?",(session,))
        links=c.execute('SELECT COUNT(*) n FROM parent_student_links').fetchone()['n']
        assert links>0
    backup=create_backup('portal-test')
    path=TEST_DIR/'portal-restore-test.zip'; path.write_bytes(backup_bytes(backup.name))
    with connect() as c:
        c.execute('DELETE FROM academy_holidays')
        c.execute("UPDATE class_attendance SET status='absent' WHERE session_id=?",(session,))
        c.execute('DELETE FROM parent_student_links')
    restore_backup(path)
    with connect() as c:
        assert c.execute("SELECT title FROM academy_holidays WHERE holiday_date='2024-06-01'").fetchone()['title']=='Restore holiday'
        assert c.execute('SELECT status FROM class_attendance WHERE session_id=?',(session,)).fetchone()['status']=='late'
        assert c.execute('SELECT COUNT(*) n FROM parent_student_links').fetchone()['n']==links
        assert c.execute("SELECT role FROM users WHERE admission_no='T-UNIT773'").fetchone()['role']=='teacher'


def test_progress_edit_rejection_resubmission_and_approval_lock():
    import json
    owner=TestClient(app); teacher=TestClient(app); other=TestClient(app); parent=TestClient(app)
    with connect() as c:
        for no,name in [('T-EDIT01','Editing Teacher'),('T-EDIT02','Other Teacher')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES (?,?,?,'teacher','active',1,?)",(no,name,hash_password('TeacherStrong123'),iso_now()))
        t=c.execute("SELECT id FROM users WHERE admission_no='T-EDIT01'").fetchone()['id']
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES ('A-EDIT01','Edit Student',?,'student','active',1,'O-Level - Grade 9',?)",(hash_password('StudentStrong123'),iso_now()))
        st=c.execute("SELECT id FROM users WHERE admission_no='A-EDIT01'").fetchone()['id']
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(st,json.dumps({'subjects':['Maths']}),iso_now()))
        sched=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 9','Maths',?,'weekly',0,'10:00',40,?) RETURNING id",(st,t,iso_now())).fetchone()['id']
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(teacher,'T-EDIT01','TeacherStrong123'),(other,'T-EDIT02','TeacherStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/parents/create',{'full_name':'Editing Parent','student_id':st,'password':'ParentStrong123'})
    csrf(parent); post(parent,'/login',{'admission_no':'P-EDIT01','password':'ParentStrong123'})
    data={'student_id':st,'subject':'Maths','kind':'assessment','title':'Original score','details':'Initial','record_date':'2024-01-01','score':'1','score_max':'10'}
    assert post(teacher,'/teacher/progress/records',data).status_code==303
    with connect() as c: rid=c.execute("SELECT id FROM student_progress_records WHERE title='Original score'").fetchone()['id']
    edit=f'/teacher/progress/records/{rid}/edit'
    assert teacher.get(edit).status_code==200
    assert other.get(edit).status_code==404
    assert post(other,edit,dict(data,title='Hijack')).status_code==404
    assert post(parent,edit,dict(data,title='Hijack')).status_code==403
    assert post(teacher,edit,dict(data,title='Updated score',score='11')).status_code==303
    with connect() as c: assert c.execute('SELECT title FROM student_progress_records WHERE id=?',(rid,)).fetchone()['title']=='Original score'
    with connect() as c: stale_version=c.execute('SELECT version FROM student_progress_records WHERE id=?',(rid,)).fetchone()['version']
    post(teacher,edit,dict(data,title='Updated score',score='0',student_id='99999',subject='Computer Science'))
    stale=post(owner,f'/admin/teaching/records/{rid}/review',{'decision':'approved','version':stale_version})
    assert 'changed%20or%20was%20already%20reviewed' in stale.headers['location']
    with connect() as c: assert c.execute('SELECT status FROM student_progress_records WHERE id=?',(rid,)).fetchone()['status']=='pending'
    with connect() as c:
        record=c.execute('SELECT * FROM student_progress_records WHERE id=?',(rid,)).fetchone()
        assert record['title']=='Updated score' and record['score']==0 and record['student_id']==st and record['subject']=='Maths'
    assert 'Updated score' not in parent.get('/parent').text
    review_progress(owner,rid,{'decision':'rejected','note':'Please clarify'})
    assert 'Progress record reviewed' in teacher.get('/notifications').text
    assert 'Please clarify' in teacher.get(edit).text
    post(teacher,edit,dict(data,title='Resubmitted score',score='2'))
    with connect() as c:
        record=c.execute('SELECT * FROM student_progress_records WHERE id=?',(rid,)).fetchone()
        assert record['status']=='pending' and record['reviewed_by'] is None and record['review_note']==''
    review_progress(owner,rid,{'decision':'approved'})
    assert 'Resubmitted score' in parent.get(f'/parent/children/{st}/report').text
    assert teacher.get(edit,follow_redirects=False).status_code==303
    post(teacher,edit,dict(data,title='Tampered approved score',score='3'))
    with connect() as c:
        assert c.execute('SELECT title FROM student_progress_records WHERE id=?',(rid,)).fetchone()['title']=='Resubmitted score'
    revise=f'/teacher/progress/records/{rid}/revise'
    assert teacher.get(revise).status_code==200
    assert other.get(revise).status_code==404
    assert 'Correction%20submitted' in post(teacher,revise,dict(data,title='Corrected score',score='3')).headers['location']
    assert 'Resubmitted score' in parent.get(f'/parent/children/{st}/report').text and 'Corrected score' not in parent.get(f'/parent/children/{st}/report').text
    with connect() as c: revision=c.execute('SELECT id FROM student_progress_records WHERE replaces_id=?',(rid,)).fetchone()['id']
    assert 'already' in post(teacher,revise,dict(data,title='Second correction')).headers['location']
    assert 'correction to record' in owner.get('/admin/teaching').text
    review_progress(owner,revision,{'decision':'approved'})
    page=parent.get(f'/parent/children/{st}/report').text
    assert 'Corrected score' in page and 'Resubmitted score' not in page
    pdf=parent.get(f'/parent/children/{st}/report.pdf'); assert pdf.status_code==200
    import importlib.util,io
    if importlib.util.find_spec('pypdf'):
        from pypdf import PdfReader
        text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
        assert 'Corrected score' in text and 'Resubmitted score' not in text and 'Fee overview' in text
    assert 'Superseded by an approved correction' in teacher.get('/teacher/progress').text
    post(teacher,'/teacher/progress/records',dict(data,title='Later assessment',score='6',record_date='2024-02-01'))
    with connect() as c: later=c.execute("SELECT id FROM student_progress_records WHERE title='Later assessment'").fetchone()['id']
    review_progress(owner,later,{'decision':'approved'})
    page=parent.get(f'/parent/children/{st}/report').text
    assert 'Latest vs previous: +30.0 percentage points' in page and 'Assessments' in page
    assignment=dict(data,kind='assignment',title='Algebra homework',outcome='pending')
    post(teacher,'/teacher/progress/records',assignment)
    with connect() as c: homework=c.execute("SELECT id FROM student_progress_records WHERE title='Algebra homework'").fetchone()['id']
    review_progress(owner,homework,{'decision':'approved'})
    post(teacher,f'/teacher/progress/records/{homework}/revise',dict(assignment,outcome='completed'))
    with connect() as c: revision2=c.execute('SELECT id FROM student_progress_records WHERE replaces_id=?',(homework,)).fetchone()['id']
    review_progress(owner,revision2,{'decision':'approved'})
    page=parent.get(f'/parent/children/{st}/report').text
    assert 'Algebra homework' in page and 'Completed' in page
    assert page.count('<h3>Algebra homework</h3>')==1
    with connect() as c: c.execute('UPDATE class_schedules SET active=0 WHERE id=?',(sched,))
    assert teacher.get(edit,follow_redirects=False).status_code==404


def test_progress_revisions_postgres_backup_restore():
    import pytest
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup, backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        rows=c.execute("SELECT id,replaces_id FROM student_progress_records WHERE replaces_id IS NOT NULL ORDER BY id").fetchall()
        assert len(rows)>=2
        expected=[(r['id'],r['replaces_id']) for r in rows]
    archive=create_backup('revision-test')
    path=TEST_DIR/'revision-restore-test.zip'; path.write_bytes(backup_bytes(archive.name))
    restore_backup(path)
    with connect() as c:
        rows=c.execute("SELECT id,replaces_id FROM student_progress_records WHERE replaces_id IS NOT NULL ORDER BY id").fetchall()
        assert [(r['id'],r['replaces_id']) for r in rows]==expected


def test_sqlite_progress_revision_migration_preserves_existing_records(tmp_path):
    import sqlite3
    from db import SCHEMA, _migrate_sqlite_progress_revisions
    conn=sqlite3.connect(tmp_path/'old_progress.db'); conn.row_factory=sqlite3.Row
    conn.executescript(SCHEMA.replace("review_note TEXT NOT NULL DEFAULT '', replaces_id INTEGER REFERENCES student_progress_records(id), version INTEGER NOT NULL DEFAULT 1","review_note TEXT NOT NULL DEFAULT ''"))
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('A-REV','Student','student','active',?)",(iso_now(),))
    conn.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('T-REV','Teacher','teacher','active',?)",(iso_now(),))
    sid=conn.execute("SELECT id FROM users WHERE admission_no='A-REV'").fetchone()['id']; tid=conn.execute("SELECT id FROM users WHERE admission_no='T-REV'").fetchone()['id']
    old=conn.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,status,created_at) VALUES (?,?,'Maths','feedback','Old record','','2024-01-01','approved',?)",(sid,tid,iso_now())).lastrowid
    conn.commit(); _migrate_sqlite_progress_revisions(conn)
    assert conn.execute('SELECT title,replaces_id FROM student_progress_records WHERE id=?',(old,)).fetchone()['replaces_id'] is None
    assert conn.execute('SELECT version FROM student_progress_records WHERE id=?',(old,)).fetchone()['version']==1
    conn.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,status,created_at,replaces_id) VALUES (?,?,'Maths','feedback','Correction','','2024-01-01','pending',?,?)",(sid,tid,iso_now(),old))
    try:
        conn.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,status,created_at,replaces_id) VALUES (?,?,'Maths','feedback','Duplicate','','2024-01-01','pending',?,?)",(sid,tid,iso_now(),old))
        assert False, 'duplicate active correction accepted'
    except sqlite3.IntegrityError: pass
    assert not conn.execute('PRAGMA foreign_key_check').fetchone()
    _migrate_sqlite_progress_revisions(conn); conn.close()


def test_parent_published_achievement_progress_and_reward_stock_are_real():
    owner=TestClient(app); parent=TestClient(app)
    with connect() as c:
        for no in ('A-RECOG1','A-RECOG2'):
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES (?,? ,?,'student','active',1,?)",(no,'Recognition Student',hash_password('StudentStrong123'),iso_now()))
        child=c.execute("SELECT id FROM users WHERE admission_no='A-RECOG1'").fetchone()['id']
        other=c.execute("SELECT id FROM users WHERE admission_no='A-RECOG2'").fetchone()['id']
        c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,30,'academic','Recorded points',?)",(child,iso_now()))
        c.execute("INSERT INTO achievements(name,description,category,points_required,status,created_at) VALUES ('Recognition Goal','Keep learning','academic',100,'active',?)",(iso_now(),))
        reward=c.execute("INSERT INTO rewards(name,description,points_required,status,quantity,created_at) VALUES ('Limited reward','Configured stock',20,'active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        c.execute("INSERT INTO reward_claims(reward_id,user_id,status,created_at) VALUES (?,?,'fulfilled',?)",(reward,other,iso_now()))
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(owner,'/admin/parents/create',{'full_name':'Recognition Parent','student_id':child,'password':'ParentStrong123'})
    csrf(parent); post(parent,'/login',{'admission_no':'P-RECOG1','password':'ParentStrong123'})
    page=parent.get(f'/parent/children/{child}/achievements').text
    assert 'Recognition Goal' in page and '30 / 100 points' in page
    rewards=parent.get(f'/parent/children/{child}/challenges-rewards').text
    assert 'Limited reward' in rewards and 'Out of stock' in rewards
    assert 'A-RECOG2' not in page and 'A-RECOG2' not in rewards


def test_parent_submit_fee_proof_uses_linked_student_and_existing_review():
    import io,secrets
    from PIL import Image
    owner=TestClient(app); parent=TestClient(app); other_parent=TestClient(app); student=TestClient(app)
    with connect() as c:
        for no,name in [('A-PAYPAR1','Payment Linked Child'),('A-PAYPAR2','Payment Unlinked Child')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES (?,?,?,'student','active',1,?)",(no,name,hash_password('StudentStrong123'),iso_now()))
        child=c.execute("SELECT id FROM users WHERE admission_no='A-PAYPAR1'").fetchone()['id']
        other=c.execute("SELECT id FROM users WHERE admission_no='A-PAYPAR2'").fetchone()['id']
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(owner,'/admin/parents/create',{'full_name':'Payment Parent','student_id':child,'password':'ParentStrong123'})
    post(owner,'/admin/parents/create',{'full_name':'Other Parent','student_id':other,'password':'ParentStrong123'})
    for client,no,pw in [(parent,'P-PAYPAR1','ParentStrong123'),(other_parent,'P-PAYPAR2','ParentStrong123'),(student,'A-PAYPAR1','StudentStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/fees/methods',{'name':'Parent transfer','currency':'PKR','account':'testing'})
    with connect() as c: method=c.execute("SELECT id FROM fee_methods WHERE name='Parent transfer'").fetchone()['id']
    for sid,label in [(child,'Parent fee'),(other,'Other fee')]:
        post(owner,'/admin/fees/assign',{'batch_key':secrets.token_hex(16),'scope':'student','student_id':sid,'title':label,'period':'2024','amount':'100','currency':'PKR'})
    with connect() as c:
        fee=c.execute("SELECT id FROM fee_assignments WHERE title='Parent fee'").fetchone()['id']
        otherfee=c.execute("SELECT id FROM fee_assignments WHERE title='Other fee'").fetchone()['id']
        parent_id=c.execute("SELECT id FROM users WHERE admission_no='P-PAYPAR1'").fetchone()['id']
    pay=f'/parent/children/{child}/fees/{fee}/pay'; submit=f'/parent/children/{child}/fees/{fee}/submit'
    page=parent.get(pay); assert page.status_code==200 and 'Payment Linked Child' in page.text and 'P-PAYPAR1' not in page.text
    assert f'/parent/children/{child}/fees/{fee}/pay' in parent.get(f'/parent/children/{child}/fees').text
    assert other_parent.get(pay).status_code==404
    assert parent.get(f'/parent/children/{other}/fees/{otherfee}/pay').status_code==404
    assert parent.get(f'/parent/children/{child}/fees/{otherfee}/pay').status_code==404
    assert student.get(pay).status_code==403
    image=io.BytesIO(); Image.new('RGB',(8,8),'white').save(image,format='PNG'); upload={'receipt':('proof.png',image.getvalue(),'image/png')}
    form={'submission_key':secrets.token_hex(16),'method_id':method,'amount':'40','currency':'PKR','payment_date':'2024-01-01'}
    assert post(other_parent,submit,form,files=upload).status_code==404
    sent=post(parent,submit,form,files=upload)
    assert sent.status_code==303 and f'/parent?child={child}&msg=' in sent.headers['location']
    assert parent.get(sent.headers['location']).status_code==200
    with connect() as c:
        payment=c.execute('SELECT * FROM fee_payments WHERE fee_id=?',(fee,)).fetchone()
        assert payment['status']=='submitted' and payment['student_id']==child and payment['submitted_by']==parent_id
        assert c.execute("SELECT id FROM audit_logs WHERE action='fee_payment_proof_submitted' AND admin_id=?",(parent_id,)).fetchone()
    assert '100.00' in parent.get('/parent').text and 'Submitted for Verification' in student.get('/fees').text
    assert 'already%20submitted' in post(parent,submit,form,files=upload).headers['location']
    assert 'Payment Parent' in owner.get('/admin/fees').text
    with connect() as c:
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-AUDIT-PAY','Activity Staff',?,'admin','active',1,'staff',?,?)",(hash_password('StaffStrong123'),'["activity"]',iso_now()))
    activity_staff=TestClient(app); csrf(activity_staff); post(activity_staff,'/login',{'admission_no':'ADMIN-AUDIT-PAY','password':'StaffStrong123'})
    assert activity_staff.get('/admin/fees').status_code==403
    activity=activity_staff.get('/admin/activity').text
    assert 'Fee Payment Proof Submitted' not in activity and 'Fee Assigned' not in activity
    assert 'Fee Payment Proof Submitted' in owner.get('/admin/activity').text
    assert parent.get(f'/fees/receipt/{payment["id"]}').status_code==200
    post(owner,f'/admin/fees/payments/{payment["id"]}/review',{'decision':'rejected','note':'Unreadable'})
    assert 'Unreadable' in parent.get(f'/parent/children/{child}/fees/{fee}').text
    form['submission_key']=secrets.token_hex(16)
    post(parent,submit,form,files=upload)
    with connect() as c: second=c.execute('SELECT MAX(id) id FROM fee_payments WHERE fee_id=?',(fee,)).fetchone()['id']
    post(owner,f'/admin/fees/payments/{second}/review',{'decision':'approved'})
    assert '60.00' in parent.get('/parent').text and 'Partially Paid' in student.get('/fees').text
    import importlib.util
    if importlib.util.find_spec('pypdf'):
        from pypdf import PdfReader
        pdf=parent.get(f'/parent/children/{child}/report.pdf')
        text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
        assert 'assigned 100.00' in text and 'approved payments 40.00' in text and 'balance 60.00' in text
    post(owner,f'/admin/parents/{parent_id}/unlink',{'student_id':child})
    assert parent.get(pay).status_code==404 and post(parent,submit,form,files=upload).status_code==404
    assert parent.get(f'/fees/receipt/{second}').status_code==404
    post(owner,f'/admin/parents/{parent_id}/link',{'student_id':child})
    post(owner,f'/admin/parents/{parent_id}/update',{'full_name':'Payment Parent','status':'disabled'})
    assert post(parent,submit,form,files=upload).status_code==303
    with connect() as c: assert c.execute('SELECT COUNT(*) n FROM fee_payments WHERE fee_id=?',(fee,)).fetchone()['n']==2


def test_sqlite_fee_submitter_upgrade_preserves_existing_payment(tmp_path):
    import sqlite3
    from db import SCHEMA, _migrate_sqlite_fee_submitter
    c=sqlite3.connect(tmp_path/'old_fee.db'); c.row_factory=sqlite3.Row
    c.executescript(SCHEMA.replace('submission_key TEXT NOT NULL UNIQUE, submitted_by INTEGER REFERENCES users(id)','submission_key TEXT NOT NULL UNIQUE'))
    c.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('A-OLD','Student','student','active',?)",(iso_now(),))
    sid=c.execute("SELECT id FROM users WHERE admission_no='A-OLD'").fetchone()['id']
    method=c.execute("INSERT INTO fee_methods(name,currency,details,created_at) VALUES ('Transfer','PKR','{}',?)",(iso_now(),)).lastrowid
    fee=c.execute("INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,created_at,batch_key) VALUES (?,'Old Fee','2024','','',100,'PKR',?,'oldbatch')",(sid,iso_now())).lastrowid
    c.execute("INSERT INTO fee_payments(fee_id,student_id,method_id,method_name,amount,currency,payment_date,reference,notes,receipt,status,submitted_at,submission_key) VALUES (?,?,?,'Transfer',100,'PKR','2024-01-01','','',?,'approved',?,'oldkey')",(fee,sid,method,b'proof',iso_now()))
    c.commit(); _migrate_sqlite_fee_submitter(c)
    assert c.execute('SELECT status,submitted_by FROM fee_payments').fetchone()['submitted_by'] is None
    c.execute('UPDATE fee_payments SET submitted_by=?',(sid,))
    assert not c.execute('PRAGMA foreign_key_check').fetchone()
    _migrate_sqlite_fee_submitter(c); c.close()


def test_parent_submission_postgres_backup_restores_submitter():
    import pytest
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup, backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        row=c.execute("SELECT p.id,p.submitted_by FROM fee_payments p JOIN users u ON u.id=p.submitted_by WHERE u.admission_no='P-PAYPAR1' ORDER BY p.id DESC LIMIT 1").fetchone()
        assert row and row['submitted_by']; payment,submitter=row['id'],row['submitted_by']
    archive=create_backup('parent-payment-test')
    path=TEST_DIR/'parent-payment-restore.zip'; path.write_bytes(backup_bytes(archive.name))
    restore_backup(path)
    with connect() as c: assert c.execute('SELECT submitted_by FROM fee_payments WHERE id=?',(payment,)).fetchone()['submitted_by']==submitter


def test_parent_and_student_concurrent_receipts_only_one_pending():
    import io,secrets
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    owner=TestClient(app); parent=TestClient(app); student=TestClient(app)
    with connect() as c:
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('A-RACEPAY','Race Child',?,'student','active',1,?)",(hash_password('StudentStrong123'),iso_now()))
        sid=c.execute("SELECT id FROM users WHERE admission_no='A-RACEPAY'").fetchone()['id']
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(owner,'/admin/parents/create',{'full_name':'Race Parent','student_id':sid,'password':'ParentStrong123'})
    for client,no,pw in [(parent,'P-RACEPAY','ParentStrong123'),(student,'A-RACEPAY','StudentStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/fees/methods',{'name':'Race transfer','currency':'PKR','account':'test'})
    post(owner,'/admin/fees/assign',{'batch_key':secrets.token_hex(16),'scope':'student','student_id':sid,'title':'Race fee','period':'2024','amount':'100','currency':'PKR'})
    with connect() as c:
        fee=c.execute("SELECT id FROM fee_assignments WHERE title='Race fee'").fetchone()['id']
        method=c.execute("SELECT id FROM fee_methods WHERE name='Race transfer'").fetchone()['id']
    image=io.BytesIO(); Image.new('RGB',(8,8),'white').save(image,format='PNG'); raw=image.getvalue()
    def send(args):
        client,path=args
        form={'submission_key':secrets.token_hex(16),'method_id':method,'amount':'100','currency':'PKR','payment_date':'2024-01-01'}
        return post(client,path,form,files={'receipt':('proof.png',raw,'image/png')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(send,[(parent,f'/parent/children/{sid}/fees/{fee}/submit'),(student,f'/fees/{fee}/submit')]))
    assert all(r.status_code==303 for r in responses)
    with connect() as c: assert c.execute("SELECT COUNT(*) n FROM fee_payments WHERE fee_id=? AND status='submitted'",(fee,)).fetchone()['n']==1


def test_parent_dashboard_timetable_uses_real_student_membership_and_child_selector():
    import json
    owner=TestClient(app); parent=TestClient(app); unlinked=TestClient(app)
    with connect() as c:
        for no,name in [('A-WORK01','Workspace Child One'),('A-WORK02','Workspace Child Two'),('A-WORK03','Private Workspace Child')]:
            row=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES (?,?,?,'student','active',1,'O-Level - Grade 10',?) RETURNING id",(no,name,hash_password('StudentStrong123'),iso_now())).fetchone()
            c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(row['id'],json.dumps({'subjects':['Maths','Computer Science']}),iso_now()))
        ids={r['admission_no']:r['id'] for r in c.execute("SELECT id,admission_no FROM users WHERE admission_no IN ('A-WORK01','A-WORK02','A-WORK03')").fetchall()}
        for no,name in [('T-WORK01','General Teacher'),('T-WORK02','Individual Teacher'),('T-WORK03','Past Teacher')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES (?,?,?,'teacher','active',1,?)",(no,name,hash_password('TeacherStrong123'),iso_now()))
        teachers={r['admission_no']:r['id'] for r in c.execute("SELECT id,admission_no FROM users WHERE admission_no IN ('T-WORK01','T-WORK02','T-WORK03')").fetchall()}
        base=c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('O-Level - Grade 10','Maths',?,'weekly',0,'09:00',40,?) RETURNING id",(teachers['T-WORK01'],iso_now())).fetchone()['id']
        c.execute("INSERT INTO class_schedules(parent_id,student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,?,'O-Level - Grade 10','Maths',?,'weekly',0,'10:00',40,?)",(base,ids['A-WORK01'],teachers['T-WORK02'],iso_now()))
        c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,class_date,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 10','Computer Science',?,'once','2020-01-01','08:00',40,?)",(ids['A-WORK01'],teachers['T-WORK03'],iso_now()))
        c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,37,'academic','Actual points',?)",(ids['A-WORK01'],iso_now()))
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(owner,'/admin/parents/create',{'full_name':'Workspace Parent','student_id':ids['A-WORK01'],'password':'ParentStrong123'})
    with connect() as c: parent_id=c.execute("SELECT id FROM users WHERE admission_no='P-WORK01'").fetchone()['id']
    post(owner,f'/admin/parents/{parent_id}/link',{'student_id':ids['A-WORK02']})
    csrf(parent); post(parent,'/login',{'admission_no':'P-WORK01','password':'ParentStrong123'})
    one=parent.get(f'/parent?child={ids["A-WORK01"]}').text
    assert 'Workspace Child One’s overview' in one and '>37<' in one
    assert 'Individual Teacher' in one and 'General Teacher' not in one and 'Past Teacher' not in one and 'Private Workspace Child' not in one
    assert all(f'href="/parent/children/{ids["A-WORK01"]}/{part}"' in one for part in ('classes','attendance','report','participation','analytics','leaderboard','achievements','challenges-rewards','fees'))
    one_classes=parent.get(f'/parent/children/{ids["A-WORK01"]}/classes').text
    assert 'Assigned classes' in one_classes and 'Individual Teacher' in one_classes and '10:00 – 10:40' in one_classes
    assert 'General Teacher' not in one_classes and 'Past Teacher' not in one_classes
    two=parent.get(f'/parent?child={ids["A-WORK02"]}').text
    assert 'Workspace Child Two’s overview' in two and 'Private Workspace Child' not in two
    assert 'name="child"' in two  # Selector appears when there is more than one linked child.
    two_classes=parent.get(f'/parent/children/{ids["A-WORK02"]}/classes').text
    assert 'General Teacher' in two_classes and '09:00 – 09:40' in two_classes and 'Individual Teacher' not in two_classes
    assert parent.get(f'/parent?child={ids["A-WORK03"]}').status_code==404
    # Removing the individual override immediately restores the grade-wide class.
    with connect() as c:
        c.execute('UPDATE class_schedules SET active=0 WHERE parent_id=? AND student_id=?',(base,ids['A-WORK01']))
    updated=parent.get(f'/parent/children/{ids["A-WORK01"]}/classes').text
    assert 'General Teacher' in updated and 'Individual Teacher' not in updated and '09:00 – 09:40' in updated
    post(owner,f'/admin/parents/{parent_id}/unlink',{'student_id':ids['A-WORK02']})
    single=parent.get('/parent').text
    assert '<select name="child">' not in single and 'Workspace Child One’s overview' in single
    post(owner,f'/admin/parents/{parent_id}/unlink',{'student_id':ids['A-WORK01']})
    empty=parent.get('/parent').text
    assert 'No student linked yet' in empty and 'Workspace Child One' not in empty and 'General Teacher' not in empty


def test_dedicated_parent_authentication_and_explicit_links():
    owner=TestClient(app); parent=TestClient(app); guardian=TestClient(app); student=TestClient(app); teacher=TestClient(app)
    with connect() as c:
        for no,name in [('A-74291','Linked Child'),('A-74292','Unlinked Child')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES (?,?,?,'student','active',1,?)",(no,name,hash_password('StudentStrong123'),iso_now()))
        ids={r['admission_no']:r['id'] for r in c.execute("SELECT id,admission_no FROM users WHERE admission_no IN ('A-74291','A-74292')").fetchall()}
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('TEACHER-74291','Login Teacher',?,'teacher','active',1,?)",(hash_password('TeacherStrong123'),iso_now()))
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(owner,'/admin/parents/create',{'full_name':'First Guardian','student_id':ids['A-74291'],'password':'ParentStrong123'})
    post(owner,'/admin/parents/create',{'full_name':'Second Guardian','student_id':ids['A-74291'],'password':'SecondStrong123'})
    with connect() as c:
        p=c.execute("SELECT id FROM users WHERE admission_no='P-74291' AND role='parent'").fetchone()['id']
        assert p != ids['A-74291']
        links=c.execute('SELECT student_id FROM parent_student_links WHERE parent_id=?',(p,)).fetchall()
        assert [r['student_id'] for r in links]==[ids['A-74291']]
    page=parent.get('/parent/login')
    assert page.status_code==200 and 'Parent sign in' in page.text and 'action="/parent/login"' in page.text and 'name="csrf_token"' in page.text
    assert 'href="/parent/login"' in TestClient(app).get('/login').text
    assert 'href="/parent/login"' in TestClient(app).get('/').text
    assert parent.post('/parent/login',data={'admission_no':'P-74291','password':'ParentStrong123'},follow_redirects=False).status_code==403
    failed=post(parent,'/parent/login',{'admission_no':'P-74291','password':'bad'}); assert failed.headers['location'].startswith('/parent/login?')
    assert parent.get('/parent',follow_redirects=False).headers['location']=='/parent/login'
    r=post(parent,'/parent/login',{'admission_no':' p-74291 ','password':'ParentStrong123'})
    assert r.headers['location']=='/parent' and 'httponly' in r.headers['set-cookie'].lower() and 'samesite=lax' in r.headers['set-cookie'].lower()
    assert parent.get('/parent/login',follow_redirects=False).headers['location']=='/parent'
    assert 'Linked Child' in parent.get('/parent').text
    assert parent.get(f'/parent?child={ids["A-74292"]}').status_code==404
    assert parent.get(f'/parent/children/{ids["A-74292"]}/report.pdf').status_code==404
    for path in ('/student','/teacher','/admin','/my-classes','/admin/parents'):
        assert parent.get(path).status_code==403
    # The parent form is role-restricted on the server even with correct credentials.
    csrf(student,'/parent/login')
    assert post(student,'/parent/login',{'admission_no':'A-74291','password':'StudentStrong123'}).headers['location'].startswith('/parent/login?')
    assert not student.cookies.get('pms_session')
    assert post(student,'/login',{'admission_no':'A-74291','password':'StudentStrong123'}).headers['location']=='/student'
    csrf(teacher); assert post(teacher,'/login',{'admission_no':'TEACHER-74291','password':'TeacherStrong123'}).headers['location']=='/teacher'
    assert teacher.get('/parent').status_code==403
    csrf(guardian,'/parent/login'); assert post(guardian,'/parent/login',{'admission_no':'P-74291-2','password':'SecondStrong123'}).headers['location']=='/parent'
    assert guardian.get(f'/parent?child={ids["A-74291"]}').status_code==200
    post(owner,f'/admin/parents/{p}/link',{'student_id':ids['A-74292']})
    assert 'Unlinked Child' in parent.get(f'/parent?child={ids["A-74292"]}').text
    post(owner,f'/admin/parents/{p}/unlink',{'student_id':ids['A-74292']})
    assert parent.get(f'/parent?child={ids["A-74292"]}').status_code==404
    post(owner,f'/admin/parents/{p}/password',{'password':'ChangedStrong123'})
    assert parent.get('/parent',follow_redirects=False).headers['location']=='/parent/login'
    assert post(parent,'/parent/login',{'admission_no':'P-74291','password':'ParentStrong123'}).headers['location'].startswith('/parent/login?')
    assert post(parent,'/parent/login',{'admission_no':'P-74291','password':'ChangedStrong123'}).headers['location']=='/parent'
    post(owner,f'/admin/parents/{p}/update',{'full_name':'First Guardian','status':'disabled'})
    assert parent.get('/parent',follow_redirects=False).headers['location']=='/parent/login'
    assert 'not%20active' in post(parent,'/parent/login',{'admission_no':'P-74291','password':'ChangedStrong123'}).headers['location']
    post(owner,f'/admin/parents/{p}/update',{'full_name':'First Guardian','status':'active'})
    assert post(parent,'/parent/login',{'admission_no':'P-74291','password':'ChangedStrong123'}).headers['location']=='/parent'
    other_session=TestClient(app); csrf(other_session,'/parent/login')
    assert post(other_session,'/parent/login',{'admission_no':'P-74291','password':'ChangedStrong123'}).headers['location']=='/parent'
    wrong=post(parent,'/parent/account/password',{'current_password':'wrong','new_password':'NewParentStrong123','confirm_password':'NewParentStrong123'})
    assert 'incorrect' in wrong.headers['location']
    changed=post(parent,'/parent/account/password',{'current_password':'ChangedStrong123','new_password':'NewParentStrong123','confirm_password':'NewParentStrong123'})
    assert 'Password%20updated' in changed.headers['location']
    assert parent.get('/parent').status_code==200
    assert other_session.get('/parent',follow_redirects=False).headers['location']=='/parent/login'
    assert post(parent,'/logout').headers['location']=='/login'
    assert post(parent,'/parent/login',{'admission_no':'P-74291','password':'ChangedStrong123'}).headers['location'].startswith('/parent/login?')
    assert post(parent,'/parent/login',{'admission_no':'P-74291','password':'NewParentStrong123'}).headers['location']=='/parent'
    assert post(parent,'/logout').headers['location']=='/login'
    assert parent.get('/parent',follow_redirects=False).headers['location']=='/parent/login'


def test_parent_login_shares_rate_limits_with_existing_login():
    client=TestClient(app,headers={'x-forwarded-for':'192.0.2.192'}); csrf(client,'/parent/login')
    for n in range(8):
        result=post(client,'/parent/login' if n%2==0 else '/login',{'admission_no':'P-RATETEST','password':'incorrect'})
        assert 'Incorrect' in result.headers['location']
    blocked=post(client,'/parent/login',{'admission_no':'P-RATETEST','password':'incorrect'})
    assert blocked.headers['location'].startswith('/parent/login?') and 'Too%20many' in blocked.headers['location']
    blocked_shared=post(client,'/login',{'admission_no':'P-RATETEST','password':'incorrect'})
    assert blocked_shared.headers['location'].startswith('/login?') and 'Too%20many' in blocked_shared.headers['location']


def test_parent_login_and_admin_reset_cannot_leave_old_session(monkeypatch):
    import importlib, threading
    from concurrent.futures import ThreadPoolExecutor
    module=importlib.import_module('app')
    owner=TestClient(app); parent=TestClient(app)
    with connect() as c:
        child=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('A-87419','Race Child',?,'student','active',1,?) RETURNING id",(hash_password('StudentStrong123'),iso_now())).fetchone()['id']
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    post(owner,'/admin/parents/create',{'full_name':'Race Guardian','student_id':child,'password':'BeforeStrong123'})
    with connect() as c: pid=c.execute("SELECT id FROM users WHERE admission_no='P-87419'").fetchone()['id']
    csrf(parent,'/parent/login')
    entered=threading.Event(); release=threading.Event(); reset_started=threading.Event()
    original=module.verify_password
    def paused_verify(password,encoded):
        if password=='BeforeStrong123':
            entered.set()
            if not release.wait(10): raise RuntimeError('Timed out waiting for race test')
        return original(password,encoded)
    monkeypatch.setattr(module,'verify_password',paused_verify)
    def sign_in(): return post(parent,'/parent/login',{'admission_no':'P-87419','password':'BeforeStrong123'})
    def reset():
        reset_started.set()
        return post(owner,f'/admin/parents/{pid}/password',{'password':'AfterStrong123'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        login_future=pool.submit(sign_in)
        try:
            assert entered.wait(10)
            reset_future=pool.submit(reset)
            assert reset_started.wait(10)
        finally:
            release.set()
        assert login_future.result(timeout=15).headers['location']=='/parent'
        assert 'reset' in reset_future.result(timeout=15).headers['location'].lower()
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM sessions WHERE user_id=?',(pid,)).fetchone()['n']==0
    assert parent.get('/parent',follow_redirects=False).headers['location']=='/parent/login'
    assert post(parent,'/parent/login',{'admission_no':'P-87419','password':'AfterStrong123'}).headers['location']=='/parent'


def test_parent_overview_real_metrics_and_academic_session():
    import json, secrets, re
    from datetime import timedelta
    from app import _class_now
    owner=TestClient(app); teacher=TestClient(app); parent=TestClient(app)
    today=_class_now().date()
    with connect() as c:
        child=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,section_name,created_at) VALUES ('A-OVIEW1','Overview Child',?,'student','active',1,'O-Level - Grade 9','A',?) RETURNING id",(hash_password('StudentStrong123'),iso_now())).fetchone()['id']
        sibling=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES ('A-OVIEW2','Second Overview Child',?,'student','active',1,'O-Level - Grade 9',?) RETURNING id",(hash_password('StudentStrong123'),iso_now())).fetchone()['id']
        tutor=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('T-OVIEW1','Overview Teacher',?,'teacher','active',1,?) RETURNING id",(hash_password('TeacherStrong123'),iso_now())).fetchone()['id']
        owner_id=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        for sid in (child,sibling): c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(sid,json.dumps({'subjects':['Maths']}),iso_now()))
        schedule=c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('O-Level - Grade 9','Maths',?,'weekly',0,'09:00',40,?) RETURNING id",(tutor,iso_now())).fetchone()['id']
        # An absence breaks the streak; excused-only and unmarked days do not.
        for offset,status in [(5,'present'),(4,'absent'),(3,'present'),(2,'excused'),(1,None),(0,'late')]:
            day=(today-timedelta(days=offset)).isoformat()
            session=c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at) VALUES (?,?,'Maths','O-Level - Grade 9','09:00',40,?,?,'ended',?) RETURNING id",(schedule,day,tutor,tutor,iso_now())).fetchone()['id']
            c.execute('INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,?)',(session,child,status))
        achievement=c.execute("INSERT INTO achievements(name,description,category,points_required,status,created_at) VALUES ('Overview badge','Earned badge','academic',10,'active',?) RETURNING id",(iso_now(),)).fetchone()['id']
        c.execute('INSERT INTO student_achievements(user_id,achievement_id,unlocked_at) VALUES (?,?,?)',(child,achievement,iso_now()))
        for currency,amount in [('PKR',100000),('USD',5000)]:
            c.execute("INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,batch_key,created_by,created_at) VALUES (?,'Overview fee','2024','','',?,?,?,?,?)",(child,amount,currency,secrets.token_hex(16),owner_id,iso_now()))
        fee=c.execute("SELECT id FROM fee_assignments WHERE student_id=? AND currency='PKR'",(child,)).fetchone()['id']
        method=c.execute("INSERT INTO fee_methods(name,currency,details,created_at) VALUES ('Overview method','PKR','{}',?) RETURNING id",(iso_now(),)).fetchone()['id']
        for status,amount in [('approved',25000),('submitted',10000)]:
            c.execute("INSERT INTO fee_payments(fee_id,student_id,method_id,method_name,amount,currency,payment_date,reference,notes,receipt,status,submitted_at,submission_key) VALUES (?,?,?,'Overview method',?,'PKR','2024-01-01','','',?, ?,?,?)",(fee,child,method,amount,b'fake isolated test receipt',status,iso_now(),secrets.token_hex(16)))
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(teacher,'T-OVIEW1','TeacherStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/parents/create',{'full_name':'Overview Parent','student_id':child,'password':'ParentStrong123'})
    with connect() as c: pid=c.execute("SELECT id FROM users WHERE admission_no='P-OVIEW1'").fetchone()['id']
    post(owner,f'/admin/parents/{pid}/link',{'student_id':sibling})
    csrf(parent,'/parent/login'); post(parent,'/parent/login',{'admission_no':'P-OVIEW1','password':'ParentStrong123'})
    def metric(html,name):
        match=re.search(r'<div[^>]*><span>'+re.escape(name)+r'</span>(.*?)</div>',html,re.S)
        assert match,name
        return re.findall(r'<strong[^>]*>(.*?)</strong>',match.group(1),re.S)
    page=parent.get(f'/parent?child={child}').text
    assert metric(page,'Academic session')==['Not set for today']
    assert metric(page,'Overall performance')==['Not recorded'] and metric(page,'Participation score')==['Not recorded']
    assert metric(page,'Attendance')==['75%'] and metric(page,'Current learning streak')==['2 days']
    assert metric(page,'Total achievements')==['1']
    assert metric(page,'Outstanding fee balance')==['PKR 750.00','USD 50.00']
    assert metric(page,'Pending assignments')==['0']
    assert metric(page,'Leaderboard position')[0].startswith('#')
    # A mixed day counts once, and any absence breaks the day streak.
    with connect() as c:
        second_schedule=c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('O-Level - Grade 9','Maths',?,'weekly',0,'10:00',40,?) RETURNING id",(tutor,iso_now())).fetchone()['id']
        second_session=c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at) VALUES (?,?,'Maths','O-Level - Grade 9','10:00',40,?,?,'ended',?) RETURNING id",(second_schedule,today.isoformat(),tutor,tutor,iso_now())).fetchone()['id']
        c.execute("INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,'absent')",(second_session,child))
    assert metric(parent.get(f'/parent?child={child}').text,'Current learning streak')==['0 days']
    with connect() as c: c.execute("UPDATE class_attendance SET status='present' WHERE session_id=? AND student_id=?",(second_session,child))
    assert metric(parent.get(f'/parent?child={child}').text,'Current learning streak')==['2 days']
    sibling_page=parent.get(f'/parent?child={sibling}').text
    assert metric(sibling_page,'Attendance')==['Not recorded'] and metric(sibling_page,'Outstanding fee balance')==['Not assigned']
    assert 'Overview fee' not in sibling_page and metric(sibling_page,'Total achievements')==['0']
    # Session configuration belongs to the Super Admin; date boundaries use academy local time.
    data={'name':'Academy Year','start':(today-timedelta(days=1)).isoformat(),'end':(today+timedelta(days=1)).isoformat()}
    assert post(parent,'/admin/settings/academic-session',data).status_code==403
    assert post(teacher,'/admin/settings/academic-session',data).status_code==403
    assert 'saved' in post(owner,'/admin/settings/academic-session',data).headers['location']
    assert metric(parent.get(f'/parent?child={child}').text,'Academic session')==['Academy Year']
    assert 'end%20date' in post(owner,'/admin/settings/academic-session',dict(data,start=data['end'],end=data['start'])).headers['location']
    assert metric(parent.get(f'/parent?child={child}').text,'Academic session')==['Academy Year']
    assert 'saved' in post(owner,'/admin/settings/academic-session',dict(data,start=(today+timedelta(days=2)).isoformat(),end=(today+timedelta(days=4)).isoformat())).headers['location']
    assert metric(parent.get(f'/parent?child={child}').text,'Academic session')==['Not set for today']
    post(owner,'/admin/settings/academic-session',data)
    # Only approved assessments count, each percentage having equal weight.
    base={'student_id':child,'subject':'Maths','record_date':today.isoformat(),'details':'','outcome':'pending'}
    for title,kind,score,maxscore in [('Assessment One','assessment','1','2'),('Assessment Two','assessment','9','10'),('Participation One','participation','0','10'),('Participation Two','participation','3','4'),('No score participation','participation','',''),('Outstanding homework','assignment','','')]:
        result=post(teacher,'/teacher/progress/records',dict(base,title=title,kind=kind,score=score,score_max=maxscore))
        assert 'submitted' in result.headers['location']
        with connect() as c: rid=c.execute('SELECT id FROM student_progress_records WHERE title=? AND student_id=?',(title,child)).fetchone()['id']
        if title!='Assessment Two': review_progress(owner,rid,{'decision':'approved'})
    pending_page=parent.get(f'/parent?child={child}').text
    assert metric(pending_page,'Overall performance')==['50.0%']
    assert metric(pending_page,'Participation score')==['37.5%'] and metric(pending_page,'Pending assignments')==['1']
    assert 'Assessment Two' not in pending_page
    with connect() as c: rid=c.execute("SELECT id FROM student_progress_records WHERE title='Assessment Two' AND student_id=?",(child,)).fetchone()['id']
    review_progress(owner,rid,{'decision':'approved'})
    assert metric(parent.get(f'/parent?child={child}').text,'Overall performance')==['70.0%']
    invalid=post(teacher,'/teacher/progress/records',dict(base,title='Partial score rejected',kind='participation',score='4',score_max=''))
    assert 'valid%20score' in invalid.headers['location']
    with connect() as c:
        assert not c.execute("SELECT id FROM student_progress_records WHERE title='Partial score rejected'").fetchone()
        rid=c.execute("SELECT id FROM student_progress_records WHERE title='Participation Two' AND student_id=?",(child,)).fetchone()['id']
    revision=post(teacher,f'/teacher/progress/records/{rid}/revise',dict(base,title='Participation corrected',score='1',score_max='4'))
    assert 'submitted' in revision.headers['location']
    assert metric(parent.get(f'/parent?child={child}').text,'Participation score')==['37.5%']
    with connect() as c: revised=c.execute("SELECT id FROM student_progress_records WHERE title='Participation corrected' AND student_id=?",(child,)).fetchone()['id']
    review_progress(owner,revised,{'decision':'approved'})
    assert metric(parent.get(f'/parent?child={child}').text,'Participation score')==['12.5%']
    assert 'cleared' in post(owner,'/admin/settings/academic-session',{'name':'','start':'','end':''}).headers['location']


def test_academic_report_periods_quizzes_and_subjects():
    import json
    from datetime import timedelta
    from app import _class_now
    today=_class_now().date(); now=iso_now()
    owner=TestClient(app); teacher=TestClient(app); parent=TestClient(app); stranger=TestClient(app)
    with connect() as c:
        child=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES ('A-RPT01','Report Child',?,'student','active',1,'O-Level - Grade 11',?) RETURNING id",(hash_password('StudentStrong123'),now)).fetchone()['id']
        other=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES ('A-RPT02','Private Child',?,'student','active',1,'O-Level - Grade 11',?) RETURNING id",(hash_password('StudentStrong123'),now)).fetchone()['id']
        tutor=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('T-RPT01','Report Teacher',?,'teacher','active',1,?) RETURNING id",(hash_password('TeacherStrong123'),now)).fetchone()['id']
        for sid in (child,other): c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(sid,json.dumps({'subjects':['Maths','Computer Science']}),now))
        for subject in ('Maths','Computer Science'):
            c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('O-Level - Grade 11',?,?,'weekly',0,'09:00',40,?)",(subject,tutor,now))
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(teacher,'T-RPT01','TeacherStrong123')]:
        csrf(client); post(client,'/login',{'admission_no':no,'password':pw})
    post(owner,'/admin/parents/create',{'full_name':'Report Parent','student_id':child,'password':'ParentStrong123'})
    csrf(parent,'/parent/login'); post(parent,'/parent/login',{'admission_no':'P-RPT01','password':'ParentStrong123'})
    post(owner,'/admin/parents/create',{'full_name':'Other Parent','student_id':other,'password':'ParentStrong123'})
    csrf(stranger,'/parent/login'); post(stranger,'/parent/login',{'admission_no':'P-RPT02','password':'ParentStrong123'})
    path=f'/parent/children/{child}/report'
    assert stranger.get(path).status_code==404 and stranger.get(path+'.pdf').status_code==404
    assert teacher.get(path).status_code==403
    assert parent.get(path+'?period=bogus').status_code==400
    assert parent.get(path+'?period=term&term_id=999999').status_code==400
    term={'name':'Report Term','start_date':(today-timedelta(days=20)).isoformat(),'end_date':today.isoformat()}
    assert post(teacher,'/admin/settings/academic-terms',term).status_code==403
    assert 'saved' in post(owner,'/admin/settings/academic-terms',term).headers['location']
    assert 'overlap' in post(owner,'/admin/settings/academic-terms',dict(term,name='Overlapping')).headers['location']
    with connect() as c: tid=c.execute("SELECT id FROM academic_terms WHERE name='Report Term'").fetchone()['id']
    assert 'end%20date' in post(owner,'/admin/settings/academic-terms',dict(term,term_id=tid,start_date=term['end_date'],end_date=term['start_date'])).headers['location']
    base={'student_id':child,'subject':'Maths','record_date':today.isoformat(),'kind':'assessment','details':'','score':'','score_max':''}
    entries=[('Quiz current','quiz',today,8,10,'Maths'),('Test earlier','test',today-timedelta(days=12),1,2,'Maths'),('Previous term quiz','quiz',today-timedelta(days=45),1,10,'Computer Science'),('Computer test','test',today,9,10,'Computer Science')]
    ids={}
    for title,typ,day,score,maxscore,subject in entries:
        result=post(teacher,'/teacher/progress/records',dict(base,title=title,subject=subject,assessment_type=typ,record_date=day.isoformat(),score=str(score),score_max=str(maxscore)))
        assert 'submitted' in result.headers['location']
        with connect() as c: ids[title]=c.execute('SELECT id FROM student_progress_records WHERE student_id=? AND title=?',(child,title)).fetchone()['id']
        if title!='Computer test': review_progress(owner,ids[title],{'decision':'approved'})
    for title,kind,outcome,details in [('Completed work','assignment','completed',''),('Pending work','assignment','pending',''),('Teacher insight','feedback','','Review fractions regularly.')]:
        post(teacher,'/teacher/progress/records',dict(base,title=title,kind=kind,outcome=outcome,details=details))
        with connect() as c: rid=c.execute('SELECT id FROM student_progress_records WHERE student_id=? AND title=?',(child,title)).fetchone()['id']
        review_progress(owner,rid,{'decision':'approved'})
    all_page=parent.get(path).text
    assert 'Quiz current' in all_page and 'Test earlier' in all_page and 'Previous term quiz' in all_page
    assert 'Computer test' not in all_page and 'Private Child' not in all_page
    assert 'Report Teacher' in all_page and 'Review fractions regularly.' in all_page
    assert 'Higher recorded averages' in all_page and 'Lower recorded averages' in all_page
    assert '1 completed · 1 pending' in all_page and '46.7%' in all_page
    week=parent.get(path+'?period=weekly').text
    assert 'Quiz current' in week and 'Test earlier' not in week and 'Previous term quiz' not in week
    month=parent.get(path+'?period=monthly').text
    assert 'Quiz current' in month and 'Test earlier' in month and 'Previous term quiz' not in month
    term_page=parent.get(path+f'?period=term&term_id={tid}').text
    assert 'Report Term' in term_page and 'Quiz current' in term_page and 'Test earlier' in term_page and 'Previous term quiz' not in term_page
    review_progress(owner,ids['Computer test'],{'decision':'approved'})
    assert 'Computer test' in parent.get(path+'?period=weekly').text
    # Corrections stay hidden until approved, and retain their classification even for older clients.
    correction=post(teacher,f"/teacher/progress/records/{ids['Quiz current']}/revise",dict(base,title='Quiz corrected',score='4',score_max='10'))
    assert 'submitted' in correction.headers['location']
    assert 'Quiz corrected' not in parent.get(path).text
    with connect() as c: corrected=c.execute("SELECT id,assessment_type FROM student_progress_records WHERE student_id=? AND title='Quiz corrected'",(child,)).fetchone()
    assert corrected['assessment_type']=='quiz'
    review_progress(owner,corrected['id'],{'decision':'approved'})
    assert 'Quiz corrected' in parent.get(path).text and 'Quiz current' not in parent.get(path).text
    invalid=post(teacher,'/teacher/progress/records',dict(base,title='Invalid classification',score='1',score_max='2',assessment_type='madeup'))
    assert 'valid%20assessment%20type' in invalid.headers['location']
    import io
    from PIL import Image
    logo=io.BytesIO(); Image.new('RGB',(20,10),'green').save(logo,format='PNG')
    assert post(owner,'/admin/settings/logo',files={'logo':('school.png',logo.getvalue(),'image/png')}).status_code==303
    pdf=parent.get(path+f'.pdf?period=term&term_id={tid}')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-') and 'no-store' in pdf.headers['cache-control']
    try:
        import pypdf, io
    except ImportError:
        pass
    else:
        text=' '.join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf.content)).pages)
        assert 'Report Term' in text and 'Quiz corrected' in text and 'Test earlier' in text and 'Previous term quiz' not in text
        assert 'Private Child' not in text and 'Report Teacher' in text
        pdf_reader=pypdf.PdfReader(io.BytesIO(pdf.content))
        assert any(page.images for page in pdf_reader.pages)
    assert parent.get(path+'.pdf?period=term&term_id=999999').status_code==400
    with connect() as c:
        assert c.execute("SELECT COUNT(*) n FROM audit_logs WHERE action='academic_term_created' AND details LIKE '%Report Term%'").fetchone()['n']==1


def test_sqlite_assessment_type_upgrade_preserves_old_records():
    import sqlite3
    from db import _migrate_sqlite_assessment_type
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE student_progress_records(id INTEGER PRIMARY KEY, title TEXT NOT NULL)')
    conn.execute("INSERT INTO student_progress_records(title) VALUES ('Legacy assessment')")
    _migrate_sqlite_assessment_type(conn); _migrate_sqlite_assessment_type(conn)
    row=conn.execute('SELECT title,assessment_type FROM student_progress_records').fetchone()
    assert row['title']=='Legacy assessment' and row['assessment_type']=='general'
    conn.close()


def test_academic_terms_and_assessment_type_postgres_backup_restore():
    import pytest
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup,backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        student=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-RPTBK','Report Backup Student','student','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        teacher=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('T-RPTBK','Report Backup Teacher','teacher','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        term=c.execute("INSERT INTO academic_terms(name,start_date,end_date,created_at) VALUES ('Backup term','2000-01-01','2000-02-01',?) RETURNING id,name,start_date,end_date",(iso_now(),)).fetchone()
        record=c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,assessment_type,created_at) VALUES (?,?,'Maths','assessment','Backup quiz','','2000-01-02',1,2,'quiz',?) RETURNING id,assessment_type",(student,teacher,iso_now())).fetchone()
    archive=create_backup('academic-reports-test'); path=TEST_DIR/'academic-reports-restore.zip'; path.write_bytes(backup_bytes(archive.name))
    with connect() as c:
        c.execute('DELETE FROM academic_terms WHERE id=?',(term['id'],))
        c.execute("UPDATE student_progress_records SET assessment_type='general' WHERE id=?",(record['id'],))
    restore_backup(path)
    with connect() as c:
        restored=c.execute('SELECT name,start_date,end_date FROM academic_terms WHERE id=?',(term['id'],)).fetchone()
        assert (restored['name'],restored['start_date'],restored['end_date'])==(term['name'],term['start_date'],term['end_date'])
        assert c.execute('SELECT assessment_type FROM student_progress_records WHERE id=?',(record['id'],)).fetchone()['assessment_type']=='quiz'


def test_old_backup_without_academic_terms_and_type_restores_safely():
    import pytest, sqlite3, zipfile, io
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup,backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        student=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-RPTLEG','Legacy Report Student','student','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        teacher=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('T-RPTLEG','Legacy Report Teacher','teacher','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        record=c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,assessment_type,created_at) VALUES (?,?,'Maths','assessment','Legacy test','','2000-01-02',1,2,'test',?) RETURNING id",(student,teacher,iso_now())).fetchone()['id']
    backup=create_backup('legacy-academic-report-test'); archive=backup_bytes(backup.name)
    with zipfile.ZipFile(io.BytesIO(archive)) as z: assets={name:z.read(name) for name in z.namelist()}
    dbfile=TEST_DIR/'legacy-academic-report.db'; dbfile.write_bytes(assets['ascend.db'])
    with sqlite3.connect(dbfile) as sqlite:
        sqlite.execute('DROP TABLE academic_terms')
        for column in ('assessment_type','feedback_type','period_start','period_end'):
            sqlite.execute(f'ALTER TABLE student_progress_records DROP COLUMN {column}')
    assets['ascend.db']=dbfile.read_bytes()
    old=TEST_DIR/'legacy-academic-report.zip'
    with zipfile.ZipFile(old,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in assets.items(): z.writestr(name,data)
    with connect() as c: c.execute("INSERT INTO academic_terms(name,start_date,end_date,created_at) VALUES ('Stale term','1900-01-01','1900-01-02',?)",(iso_now(),))
    restore_backup(old)
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM academic_terms').fetchone()['n']==0
        restored=c.execute('SELECT assessment_type,feedback_type,period_start,period_end FROM student_progress_records WHERE id=?',(record,)).fetchone()
        assert (restored['assessment_type'],restored['feedback_type'],restored['period_start'],restored['period_end'])==('general','general',None,None)


def test_admin_teaching_assigned_profiles_periodic_feedback_and_privacy():
    import json
    from datetime import timedelta
    from app import _class_now
    today=_class_now().date(); now=iso_now()
    owner=TestClient(app); staff=TestClient(app); second=TestClient(app); guardian=TestClient(app)
    with connect() as c:
        for no,name in [('ADMIN-TCH501','Teaching Staff'),('ADMIN-TCH502','Other Teaching Staff')]:
            c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES (?,?,?,'admin','active',1,'staff',?,?)",(no,name,hash_password('TeacherStrong123'),'["teaching"]',now))
        teachers={r['admission_no']:r['id'] for r in c.execute("SELECT id,admission_no FROM users WHERE admission_no IN ('ADMIN-TCH501','ADMIN-TCH502')").fetchall()}
        for no,name in [('A-TCH501','Assigned Student'),('A-TCH502','Private Student')]:
            row=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at) VALUES (?,?,?,'student','active',1,'O-Level - Grade 10',?) RETURNING id",(no,name,hash_password('StudentStrong123'),now)).fetchone()
            c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(row['id'],json.dumps({'subjects':['Maths','Computer Science']}),now))
        students={r['admission_no']:r['id'] for r in c.execute("SELECT id,admission_no FROM users WHERE admission_no IN ('A-TCH501','A-TCH502')").fetchall()}
        for sid,tid,subject in [(students['A-TCH501'],teachers['ADMIN-TCH501'],'Maths'),(students['A-TCH502'],teachers['ADMIN-TCH502'],'Maths'),(students['A-TCH501'],teachers['ADMIN-TCH502'],'Computer Science')]:
            schedule=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 10',?,?,'weekly',0,'09:00',40,?) RETURNING id",(sid,subject,tid,now)).fetchone()['id']
            session=c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at) VALUES (?,?,?,'O-Level - Grade 10','09:00',40,?,?,'ended',?) RETURNING id",(schedule,today.isoformat(),subject,tid,tid,now)).fetchone()['id']
            c.execute("INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,'present')",(session,sid))
    for client,no,pw in [(owner,'ADMIN-0001','StrongAdmin123'),(staff,'ADMIN-TCH501','TeacherStrong123'),(second,'ADMIN-TCH502','TeacherStrong123')]:
        csrf(client); assert post(client,'/login',{'admission_no':no,'password':pw}).headers['location']=='/admin'
    post(owner,'/admin/parents/create',{'full_name':'Teaching Guardian','student_id':students['A-TCH501'],'password':'ParentStrong123'})
    csrf(guardian,'/parent/login'); post(guardian,'/parent/login',{'admission_no':'P-TCH501','password':'ParentStrong123'})
    directory=staff.get('/admin/teaching').text
    assert 'Assigned Student' in directory and 'Private Student' not in directory
    profile=staff.get(f'/admin/teaching/students/{students["A-TCH501"]}')
    assert profile.status_code==200 and 'Assigned Student' in profile.text and 'Maths' in profile.text and 'Computer Science' not in profile.text
    assert 'Present' in profile.text and '/admin/fees' not in profile.text
    assert staff.get(f'/admin/teaching/students/{students["A-TCH502"]}').status_code==404
    assert staff.get(f'/admin/teaching?student={students["A-TCH502"]}').status_code==404
    assert f'<option value="{students["A-TCH501"]}" data-subjects=' in staff.get(f'/admin/teaching?student={students["A-TCH501"]}').text
    import re
    assert re.search(fr'<option value="{students["A-TCH501"]}"[^>]* selected>',staff.get(f'/admin/teaching?student={students["A-TCH501"]}').text)
    assert staff.get('/admin/fees').status_code==403 and post(staff,'/admin/fees/assign',{}).status_code==403
    assert staff.get('/admin/parents').status_code==403
    record={'student_id':students['A-TCH501'],'subject':'Maths','kind':'feedback','title':'Monthly learning feedback','details':'Excellent improvement in mathematics.','feedback_type':'parent_feedback','record_date':today.isoformat(),'period_start':(today-timedelta(days=29)).isoformat(),'period_end':today.isoformat()}
    assert post(staff,'/admin/teaching/records',dict(record,student_id=students['A-TCH502'])).status_code==403
    assert post(staff,'/admin/teaching/records',dict(record,subject='Computer Science')).status_code==403
    for invalid in (dict(record,period_end=''),dict(record,period_start=today.isoformat(),period_end=(today-timedelta(days=1)).isoformat()),dict(record,feedback_type='invalid')):
        assert 'kind=error' in post(staff,'/admin/teaching/records',invalid).headers['location']
    assert 'submitted' in post(staff,'/admin/teaching/records',record).headers['location']
    with connect() as c: rid=c.execute("SELECT id FROM student_progress_records WHERE student_id=? AND title='Monthly learning feedback'",(students['A-TCH501'],)).fetchone()['id']
    assert second.get(f'/admin/teaching/records/{rid}/edit').status_code==404
    assert review_progress(staff,rid,{'decision':'approved'}).status_code==403
    assert 'Monthly learning feedback' not in guardian.get('/parent').text
    assert 'Feedback for parents' in owner.get('/admin/teaching').text
    review_progress(owner,rid,{'decision':'approved'})
    parent=guardian.get(f'/parent/children/{students["A-TCH501"]}/participation').text
    assert 'Monthly learning feedback' in parent and 'Feedback for parents' in parent and record['period_start'] in parent and 'Excellent improvement' in parent
    report=guardian.get(f'/parent/children/{students["A-TCH501"]}/report').text
    assert 'Feedback for parents' in report and 'Excellent improvement' in report
    # Approved feedback is immutable until an approved correction supersedes it.
    revision=post(staff,f'/admin/teaching/records/{rid}/revise',dict(record,title='Corrected classroom observation',feedback_type='behavior',details='Participates respectfully.'))
    assert 'submitted' in revision.headers['location']
    assert 'Corrected classroom observation' not in guardian.get(f'/parent/children/{students["A-TCH501"]}/participation').text
    with connect() as c: revised=c.execute("SELECT id FROM student_progress_records WHERE student_id=? AND title='Corrected classroom observation'",(students['A-TCH501'],)).fetchone()['id']
    review_progress(owner,revised,{'decision':'approved'})
    assert 'Corrected classroom observation' in guardian.get(f'/parent/children/{students["A-TCH501"]}/participation').text and 'Monthly learning feedback' not in guardian.get(f'/parent/children/{students["A-TCH501"]}/participation').text
    assert 'Classroom observation' in guardian.get(f'/parent/children/{students["A-TCH501"]}/participation').text
    # Loss of a teaching assignment immediately denies profile and updates.
    with connect() as c: c.execute("UPDATE class_schedules SET active=0 WHERE student_id=? AND teacher_id=?",(students['A-TCH501'],teachers['ADMIN-TCH501']))
    assert staff.get(f'/admin/teaching/students/{students["A-TCH501"]}').status_code==404
    assert post(staff,f'/admin/teaching/records/{revised}/revise',dict(record,title='After removal')).status_code==404
    assert 'Assigned Student' not in staff.get('/admin/teaching').text


def test_sqlite_feedback_migration_preserves_legacy_records():
    import sqlite3
    from db import _migrate_sqlite_feedback_details
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE student_progress_records(id INTEGER PRIMARY KEY, title TEXT NOT NULL)')
    conn.execute("INSERT INTO student_progress_records(title) VALUES ('Previous feedback')")
    _migrate_sqlite_feedback_details(conn); _migrate_sqlite_feedback_details(conn)
    row=conn.execute('SELECT title,feedback_type,period_start,period_end FROM student_progress_records').fetchone()
    assert (row['title'],row['feedback_type'],row['period_start'],row['period_end'])==('Previous feedback','general',None,None)
    conn.close()


def test_feedback_details_postgres_backup_restore():
    import pytest
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup,backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        student=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-FDBK01','Backup Feedback Student','student','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        teacher=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('T-FDBK01','Backup Feedback Teacher','teacher','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        rid=c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,feedback_type,period_start,period_end,created_at) VALUES (?,?,'Maths','feedback','Backup feedback','Observed improvement','2024-06-01','improvement','2024-05-01','2024-05-31',?) RETURNING id",(student,teacher,iso_now())).fetchone()['id']
    backup=create_backup('feedback-test'); path=TEST_DIR/'feedback-restore.zip'; path.write_bytes(backup_bytes(backup.name))
    with connect() as c: c.execute("UPDATE student_progress_records SET feedback_type='general',period_start=NULL,period_end=NULL WHERE id=?",(rid,))
    restore_backup(path)
    with connect() as c:
        record=c.execute('SELECT feedback_type,period_start,period_end FROM student_progress_records WHERE id=?',(rid,)).fetchone()
        assert (record['feedback_type'],record['period_start'],record['period_end'])==('improvement','2024-05-01','2024-05-31')


def test_staff_permissions_are_explicit_scoped_and_revocable():
    import json
    from app import _class_now
    owner,staff=TestClient(app),TestClient(app)
    csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    page=owner.get('/admin/admins').text
    assert 'Assigned teaching and attendance' in page and 'Academy-wide class management' in page
    response=post(owner,'/admin/admins/create',{'admin_id':'ADMIN-PRM501','full_name':'Permission Teacher','password':'TeacherStrong123'})
    assert response.status_code==303
    with connect() as c:
        tid=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-PRM501'").fetchone()['id']
        assert json.loads(c.execute('SELECT admin_permissions FROM users WHERE id=?',(tid,)).fetchone()['admin_permissions'])==[]
        sid=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-PRM501','Scoped Pupil','student','active',1,'O-Level - Grade 9',?) RETURNING id",(iso_now(),)).fetchone()['id']
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(sid,json.dumps({'subjects':['Maths']}),iso_now()))
        sch=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 9','Maths',?,'weekly',?,'09:00',40,?) RETURNING id",(sid,tid,_class_now().weekday(),iso_now())).fetchone()['id']
        other=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        other_sch=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 9','Maths',?,'weekly',?,'10:00',40,?) RETURNING id",(sid,other,_class_now().weekday(),iso_now())).fetchone()['id']
        session=c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at) VALUES (?,?,'Maths','O-Level - Grade 9','10:00',40,?,?,'live',?) RETURNING id",(other_sch,_class_now().date().isoformat(),other,other,iso_now())).fetchone()['id']
    csrf(staff); post(staff,'/login',{'admission_no':'ADMIN-PRM501','password':'TeacherStrong123'})
    for path in ['/admin/teaching','/admin/teaching/classes','/admin/my-classes','/admin/students','/admin/fees','/leaderboards']:
        assert staff.get(path).status_code==403, path
    assert post(staff,f'/admin/my-classes/{sch}/start').status_code==403
    assert post(staff,f'/admin/teaching/classes/{sch}/start').status_code==403
    assert 'Scoped Pupil' not in staff.get('/admin').text
    post(owner,f'/admin/admins/{tid}/edit',{'full_name':'Permission Teacher','permissions':'teaching'})
    assert staff.get('/admin/teaching').status_code==200
    classes=staff.get('/admin/teaching/classes'); assert classes.status_code==200 and 'Scoped Pupil' in classes.text
    assert f'/admin/teaching/classes/{sch}/start' in classes.text
    assert staff.get('/admin/my-classes').status_code==403
    assert post(staff,'/admin/my-classes/create',{}).status_code==403
    assert post(staff,f'/admin/teaching/classes/{other_sch}/start').status_code==404
    started=post(staff,f'/admin/teaching/classes/{sch}/start')
    assert 'Session%20started' in started.headers['location'] or 'Session+started' in started.headers['location']
    with connect() as c: own_session=c.execute('SELECT id FROM class_sessions WHERE schedule_id=? AND session_date=?',(sch,_class_now().date().isoformat())).fetchone()['id']
    assert post(staff,f'/admin/teaching/classes/session/{own_session}/end').status_code==303
    assert post(staff,f'/admin/teaching/classes/session/{own_session}/attendance',{f'attendance_{sid}':'present'}).status_code==303
    with connect() as c: assert c.execute('SELECT status FROM class_attendance WHERE session_id=? AND student_id=?',(own_session,sid)).fetchone()['status']=='present'
    assert post(staff,f'/admin/teaching/classes/session/{session}/end').status_code==404
    assert post(staff,f'/my-classes/live/{session}/room').status_code==404
    assert staff.get('/admin/fees').status_code==403
    assert staff.get('/admin/admins').status_code==403
    post(owner,f'/admin/admins/{tid}/edit',{'full_name':'Permission Teacher','permissions':'classes'})
    assert staff.get('/admin/my-classes').status_code==200
    assert staff.get('/admin/teaching').status_code==403
    assert staff.get('/admin/teaching/classes').status_code==403
    assert post(staff,f'/my-classes/live/{session}/room').status_code==200
    with connect() as c:
        c.execute("INSERT INTO notifications(user_id,title,body,created_at) VALUES (?,'Fee receipt submitted','Private fee notice',?)",(tid,iso_now()))
    post(owner,f'/admin/admins/{tid}/edit',{'full_name':'Permission Teacher','permissions':'fees'})
    assert 'Private fee notice' in staff.get('/notifications').text
    post(owner,f'/admin/admins/{tid}/edit',{'full_name':'Permission Teacher'})
    assert staff.get('/admin/my-classes').status_code==403
    assert post(staff,f'/my-classes/live/{session}/room').status_code==404
    assert 'Private fee notice' not in staff.get('/notifications').text


def test_sqlite_staff_permission_migration_is_once_and_preserves_access():
    import json,sqlite3
    from db import _migrate_sqlite_staff_permissions
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)')
    c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,role TEXT,admin_level TEXT,admin_permissions TEXT)')
    c.execute("INSERT INTO users VALUES (1,'admin','staff','[]'), (2,'admin','staff',NULL), (3,'admin','staff','[\"fees\"]')")
    _migrate_sqlite_staff_permissions(c)
    one=json.loads(c.execute('SELECT admin_permissions FROM users WHERE id=1').fetchone()[0])
    two=json.loads(c.execute('SELECT admin_permissions FROM users WHERE id=2').fetchone()[0])
    three=json.loads(c.execute('SELECT admin_permissions FROM users WHERE id=3').fetchone()[0])
    assert set(one)=={'classes','leaderboards'}
    assert set(two)=={'students','challenges','achievements','rewards','announcements','activity','classes','leaderboards'}
    assert set(three)=={'fees','classes','leaderboards'} and 'teaching' not in three
    c.execute("UPDATE users SET admin_permissions='[]' WHERE id=1")
    _migrate_sqlite_staff_permissions(c)
    assert json.loads(c.execute('SELECT admin_permissions FROM users WHERE id=1').fetchone()[0])==[]
    c.close()


def test_attendance_insights_day_rules_week_and_month_boundaries():
    from datetime import date
    from app import _attendance_insights
    def record(day,status): return {'session_date':day,'status':status}
    rows=[record('2024-12-30','present'),record('2024-12-31','late'),
        record('2025-01-03','absent'),record('2025-01-04','excused'),
        record('2025-03-01','present'),record('2025-03-02','present'),record('2025-03-02','absent'),
        record('2025-03-03','absent'),record('2025-03-04','late'),
        record('2025-03-05','present'),record('2025-03-05',None),record('2025-03-06','absent')]
    result=_attendance_insights(rows,{'2025-03-03'},date(2025,3,5))
    assert (result['total'],result['attended'],result['missed'],result['late'],result['excused'],result['pending'],result['holiday_absences'],result['percent'])==(11,6,2,2,1,1,1,75)
    assert (result['current_streak'],result['best_streak'])==(2,2)
    assert result['week']=={'start':'2025-02-27','end':'2025-03-05','attended':3,'total':4,'percent':75}
    assert result['rolling']==[{'days':7,'total':5,'attended':4,'percent':80},{'days':30,'total':5,'attended':4,'percent':80}]
    months={m['month']:m for m in result['months']}
    assert (months['2024-12']['attended'],months['2024-12']['total'],months['2024-12']['percent'])==(2,2,100)
    assert months['2025-01']['percent']==0 and months['2025-02']['percent'] is None
    assert (months['2025-03']['attended'],months['2025-03']['total'],months['2025-03']['percent'])==(4,5,80)
    empty=_attendance_insights([record('2025-03-03','absent'),record('2025-03-04','excused'),record('2025-03-05',None)],{'2025-03-03'},date(2025,3,5))
    assert empty['percent'] is None and empty['week']['percent'] is None and empty['current_streak']==0
    # A real attended class on a holiday still counts, while that holiday's absence does not.
    result=_attendance_insights([record('2025-03-03','absent'),record('2025-03-03','late')],{'2025-03-03'},date(2025,3,5))
    assert (result['total'],result['attended'],result['missed'],result['percent'],result['current_streak'])==(2,1,0,100,1)


def test_parent_attendance_section_calendar_privacy_and_live_corrections(monkeypatch):
    import re,io,importlib.util
    import app as module
    from datetime import datetime
    monkeypatch.setattr(module,'_class_now',lambda:datetime(2025,3,5,12,0,tzinfo=module.PAKISTAN))
    now=iso_now()
    with connect() as c:
        child=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-ATD601','Attendance Child','student','active',1,'Attendance Grade',?) RETURNING id",(now,)).fetchone()['id']
        other=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-ATD602','Private Attendance Child','student','active',1,'Attendance Grade',?) RETURNING id",(now,)).fetchone()['id']
        guardian=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-ATD601','Attendance Parent',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),now)).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(guardian,child,now))
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        rows=[('2024-12-30','present'),('2024-12-31','late'),('2025-01-03','absent'),('2025-01-04','excused'),
              ('2025-03-01','present'),('2025-03-02','present'),('2025-03-02','absent'),('2025-03-03','absent'),
              ('2025-03-04','late'),('2025-03-05','present'),('2025-03-05',None),('2025-03-06','absent')]
        ids=[]
        for number,(day,status) in enumerate(rows):
            schedule=c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,'Attendance Grade','Maths',?,'weekly',0,?,40,?) RETURNING id",(child,admin,f'{number:02d}:00',now)).fetchone()['id']
            session=c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at) VALUES (?,?,'Maths','Attendance Grade',?,40,?,?,'ended',?) RETURNING id",(schedule,day,f'{number:02d}:00',admin,admin,now)).fetchone()['id']
            c.execute('INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,?)',(session,child,status)); ids.append(session)
        c.execute("INSERT INTO class_attendance(session_id,student_id,status) VALUES (?,?,'absent')",(ids[0],other))
        c.execute("INSERT INTO academy_holidays(holiday_date,title,created_at) VALUES ('2025-03-03','Attendance Test Holiday',?) ON CONFLICT(holiday_date) DO UPDATE SET title=excluded.title",(now,))
    parent=TestClient(app); csrf(parent,'/parent/login'); post(parent,'/parent/login',{'admission_no':'P-ATD601','password':'ParentStrong123'})
    page=parent.get(f'/parent/children/{child}/attendance?month=2025-03&day=2025-03-03').text
    def metric(name):
        match=re.search(r'<div><span>'+re.escape(name)+r'</span>\s*<strong[^>]*>(.*?)</strong>',page,re.S)
        assert match,name
        return match.group(1)
    for name,value in [('Total classes','11'),('Classes attended','6'),('Classes missed','2'),('Late arrivals','2'),('Attendance percentage','75%'),('Current attendance streak','2 days'),('Longest attendance streak','2 days'),('Awaiting marking','1')]:
        assert metric(name)==value
    assert '75% · 3 of 4 recorded class days attended' in page
    assert '80%' in page and '4 of 5 sessions' in page and 'No counted sessions' in page
    assert '2025-03-02, present recorded, absent recorded' in page
    assert '2025-03-05, present recorded, attendance pending' in page
    assert 'Holiday · Attendance Test Holiday' in page and 'holiday absence excluded from totals' in page
    assert 'Private Attendance Child' not in page
    assert parent.get(f'/parent?child={other}').status_code==404
    assert parent.get(f'/parent/children/{other}/report.pdf').status_code==404
    pending=parent.get(f'/parent/children/{child}/attendance?month=2025-03&day=2025-03-05').text
    assert '10:00 · Maths · Pending' in pending
    pdf=parent.get(f'/parent/children/{child}/report.pdf'); assert pdf.status_code==200
    if importlib.util.find_spec('pypdf'):
        from pypdf import PdfReader
        pdf_text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
        assert '6 present or late; 2 absent' in pdf_text and 'holiday absences excluded' in pdf_text
    # Correct the mixed-day absence: insights refresh immediately without changing the holiday record.
    with connect() as c: c.execute("UPDATE class_attendance SET status='present' WHERE session_id=? AND student_id=?",(ids[6],child))
    corrected=parent.get(f'/parent/children/{child}/attendance?month=2025-03&day=2025-03-03').text
    assert re.search(r'<span>Classes missed</span><strong[^>]*>1</strong>',corrected)
    assert re.search(r'<span>Current attendance streak</span><strong[^>]*>4 days</strong>',corrected)
    assert '100% · 4 of 4 recorded class days attended' in corrected
    # Removing the holiday immediately restores its recorded absence to the calculation.
    with connect() as c: c.execute("DELETE FROM academy_holidays WHERE holiday_date='2025-03-03'")
    updated=parent.get(f'/parent/children/{child}/attendance?month=2025-03&day=2025-03-03').text
    assert re.search(r'<span>Classes missed</span><strong[^>]*>2</strong>',updated)
    assert '<span>Current attendance streak</span><strong>2 days</strong>' in updated


def test_participation_trends_count_real_records_and_scores():
    from datetime import date
    from app import _participation_insights
    def row(day,category,score=None,maxscore=None):
        return {'kind':'participation','record_date':day,'participation_type':category,'score':score,'score_max':maxscore}
    data=[row('2024-12-29','general',0,10),row('2025-01-10','answers',8,10),
          row('2025-03-01','group',None,None),row('2025-03-03','group',0,10),
          row('2025-03-05','events',8,10),row('2025-03-06','homework',9,10)]
    result=_participation_insights(data,date(2025,3,5))
    assert result['average']==50.0 and result['scored']==5
    categories={x['label']:x['count'] for x in result['categories']}
    assert categories['Group activities']==2 and categories['Special events']==1 and categories['Discussions']==0
    months={r['month']:r for r in result['months']}
    assert (months['2024-12']['count'],months['2024-12']['average'])==(1,0.0)
    assert (months['2025-02']['count'],months['2025-02']['average'])==(0,None)
    assert (months['2025-03']['count'],months['2025-03']['scored'],months['2025-03']['average'])==(3,2,40.0)


def test_participation_teacher_approval_categories_privacy_and_no_points():
    import json, re
    from app import _class_now, PARTICIPATION_LABELS
    now=iso_now(); today=_class_now().date().isoformat()
    owner=TestClient(app); staff=TestClient(app); other_teacher=TestClient(app); parent=TestClient(app)
    with connect() as c:
        student=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-ACTV01','Activity Child','student','active',1,'O-Level - Grade 9',?) RETURNING id",(now,)).fetchone()['id']
        private=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-ACTV02','Private Activity Child','student','active',1,'O-Level - Grade 9',?) RETURNING id",(now,)).fetchone()['id']
        teacher=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-ACTV01','Activity Teacher',?,'admin','active',1,'staff',?,?) RETURNING id",(hash_password('TeacherStrong123'),'["teaching"]',now)).fetchone()['id']
        other=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('T-ACTV02','Other Activity Teacher',?,'teacher','active',1,?) RETURNING id",(hash_password('TeacherStrong123'),now)).fetchone()['id']
        pid=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-ACTV01','Activity Parent',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),now)).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(pid,student,now))
        for sid,tid in [(student,teacher),(private,other)]:
            c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(sid,json.dumps({'subjects':['Maths']}),now))
            c.execute("INSERT INTO class_schedules(student_id,grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES (?,'O-Level - Grade 9','Maths',?,'weekly',0,'09:00',40,?)",(sid,tid,now))
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        challenge=c.execute("INSERT INTO challenges(title,description,category,points,status,created_by,created_at) VALUES ('Separate challenge','Existing challenge record','activity',25,'active',?,?) RETURNING id",(admin,now)).fetchone()['id']
        c.execute("INSERT INTO challenge_participations(challenge_id,user_id,status,created_at,updated_at) VALUES (?,?,'joined',?,?)",(challenge,student,now,now))
    for client,no,pw,path in [(owner,'ADMIN-0001','StrongAdmin123','/login'),(staff,'ADMIN-ACTV01','TeacherStrong123','/login'),(other_teacher,'T-ACTV02','TeacherStrong123','/login'),(parent,'P-ACTV01','ParentStrong123','/parent/login')]:
        csrf(client,path); post(client,path,{'admission_no':no,'password':pw})
    page=staff.get('/admin/teaching').text
    for code in PARTICIPATION_LABELS: assert f'value="{code}"' in page
    base={'student_id':student,'subject':'Maths','kind':'participation','title':'Activity test','record_date':today,'details':'Constructive activity feedback.'}
    assert post(staff,'/admin/teaching/records',dict(base,student_id=private,participation_type='classroom')).status_code==403
    assert post(staff,'/admin/teaching/records',dict(base,subject='Computer Science',participation_type='classroom')).status_code==403
    assert 'kind=error' in post(staff,'/admin/teaching/records',dict(base,participation_type='bogus')).headers['location']
    assert 'kind=error' in post(staff,'/admin/teaching/records',dict(base,participation_type='classroom',score='1',score_max='')).headers['location']
    assert staff.get('/admin/fees').status_code==403 and staff.get('/admin/students').status_code==403
    ids=[]
    for i,code in enumerate(PARTICIPATION_LABELS):
        payload=dict(base,title='Activity '+code,participation_type=code)
        if i==0: payload.update(score='0',score_max='10')
        if i==1: payload.update(score='8',score_max='10')
        assert 'submitted' in post(staff,'/admin/teaching/records',payload).headers['location']
        with connect() as c: rid=c.execute('SELECT id FROM student_progress_records WHERE student_id=? AND title=?',(student,payload['title'])).fetchone()['id']
        ids.append(rid)
    before=parent.get('/parent').text
    assert 'Activity classroom' not in before and 'Constructive activity feedback.' not in before
    challenges_before=parent.get(f'/parent/children/{student}/challenges-rewards').text
    assert 'Separate challenge' in challenges_before and 'Joined' in challenges_before
    assert other_teacher.get(f'/teacher/progress/records/{ids[0]}/edit').status_code==404
    assert review_progress(staff,ids[0],{'decision':'approved'}).status_code==403
    assert 'Classroom participation' in owner.get('/admin/teaching').text
    # Older clients omitting the new field preserve the stored category on edit.
    edit=post(staff,f'/admin/teaching/records/{ids[0]}/edit',dict(base,title='Activity classroom',score='0',score_max='10'))
    assert 'submitted' in edit.headers['location']
    with connect() as c: assert c.execute('SELECT participation_type FROM student_progress_records WHERE id=?',(ids[0],)).fetchone()['participation_type']=='classroom'
    # Rejected activities remain hidden until a valid edit is resubmitted and approved.
    assert 'rejected' in review_progress(owner,ids[3],{'decision':'rejected','note':'Please clarify the activity.'}).headers['location']
    assert 'Please clarify the activity.' in staff.get(f'/admin/teaching/records/{ids[3]}/edit').text
    assert 'kind=error' in post(staff,f'/admin/teaching/records/{ids[3]}/edit',dict(base,title='Activity group',participation_type='invalid')).headers['location']
    assert 'submitted' in post(staff,f'/admin/teaching/records/{ids[3]}/edit',dict(base,title='Activity group',participation_type='group')).headers['location']
    for rid in ids: assert 'approved' in review_progress(owner,rid,{'decision':'approved'}).headers['location']
    visible=parent.get(f'/parent/children/{student}/participation').text
    assert 'Activity classroom' in visible and 'Constructive activity feedback.' in visible
    assert '40.0%' in visible and '2 scored records' in visible
    assert 'Private Activity Child' not in visible
    assert 'Separate challenge' in parent.get(f'/parent/children/{student}/challenges-rewards').text
    assert parent.get(f'/parent?child={private}').status_code==404
    assert parent.get(f'/parent/children/{private}/report').status_code==404
    report=parent.get(f'/parent/children/{student}/report').text
    assert 'Classroom participation' in report and 'Activity classroom' in report
    # Teacher corrections retain the old approved record until review, including when the category changes.
    revised=post(staff,f'/admin/teaching/records/{ids[0]}/revise',dict(base,title='Revised participation',participation_type='events',score='6',score_max='10'))
    assert 'submitted' in revised.headers['location']
    assert 'Activity classroom' in parent.get(f'/parent/children/{student}/participation').text and 'Revised participation' not in parent.get(f'/parent/children/{student}/participation').text
    with connect() as c:
        revision=c.execute("SELECT id,participation_type FROM student_progress_records WHERE student_id=? AND title='Revised participation'",(student,)).fetchone()
        assert revision['participation_type']=='events'; revision_id=revision['id']
    assert 'Previous category: Classroom participation' in owner.get('/admin/teaching').text
    review_progress(owner,revision_id,{'decision':'approved'})
    revised_page=parent.get(f'/parent/children/{student}/participation').text
    assert 'Revised participation' in revised_page and 'Activity classroom' not in revised_page
    assert '70.0%' in revised_page
    # Neither submission, approval, nor correction creates or changes academy points.
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM point_transactions WHERE user_id=?',(student,)).fetchone()['n']==0
        assert c.execute('SELECT participation_type FROM student_progress_records WHERE id=?',(ids[0],)).fetchone()['participation_type']=='classroom'
    # Revoking the class assignment immediately removes the teacher's access.
    with connect() as c: c.execute('UPDATE class_schedules SET active=0 WHERE student_id=? AND teacher_id=?',(student,teacher))
    assert staff.get(f'/admin/teaching/records/{revision_id}/revise').status_code==404
    assert post(staff,'/admin/teaching/records',dict(base,participation_type='events')).status_code==403


def test_sqlite_participation_category_migration_preserves_legacy_data():
    import sqlite3
    from db import _migrate_sqlite_participation_type
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE student_progress_records(id INTEGER PRIMARY KEY, title TEXT NOT NULL)')
    c.execute("INSERT INTO student_progress_records(title) VALUES ('Earlier participation')")
    _migrate_sqlite_participation_type(c); _migrate_sqlite_participation_type(c)
    row=c.execute('SELECT title,participation_type FROM student_progress_records').fetchone()
    assert (row['title'],row['participation_type'])==('Earlier participation','general')
    c.close()


def test_participation_categories_postgres_backup_and_legacy_restore():
    import pytest, io, sqlite3, zipfile
    from db import DATABASE_URL
    if not DATABASE_URL: pytest.skip('PostgreSQL restore test')
    from backups import create_backup,backup_bytes
    from scripts.restore_postgres_backup import restore_backup
    with connect() as c:
        st=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-PTBK01','Participation Backup Student','student','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        teacher=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('T-PTBK01','Participation Backup Teacher','teacher','active',1,?) RETURNING id",(iso_now(),)).fetchone()['id']
        rid=c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,participation_type,created_at) VALUES (?,?,'Maths','participation','Backup activity','','2024-06-01','events',?) RETURNING id",(st,teacher,iso_now())).fetchone()['id']
    backup=create_backup('participation-category-test'); archive=backup_bytes(backup.name)
    path=TEST_DIR/'participation-restore.zip';path.write_bytes(archive)
    with connect() as c: c.execute("UPDATE student_progress_records SET participation_type='general' WHERE id=?",(rid,))
    restore_backup(path)
    with connect() as c: assert c.execute('SELECT participation_type FROM student_progress_records WHERE id=?',(rid,)).fetchone()['participation_type']=='events'
    with zipfile.ZipFile(io.BytesIO(archive)) as z: assets={name:z.read(name) for name in z.namelist()}
    dbfile=TEST_DIR/'old-participation.db'; dbfile.write_bytes(assets['ascend.db'])
    with sqlite3.connect(dbfile) as sqlite: sqlite.execute('ALTER TABLE student_progress_records DROP COLUMN participation_type')
    assets['ascend.db']=dbfile.read_bytes()
    legacy=TEST_DIR/'legacy-participation.zip'
    with zipfile.ZipFile(legacy,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in assets.items(): z.writestr(name,data)
    restore_backup(legacy)
    with connect() as c:
        row=c.execute('SELECT title,participation_type FROM student_progress_records WHERE id=?',(rid,)).fetchone()
        assert (row['title'],row['participation_type'])==('Backup activity','general')


def test_parent_leaderboard_subject_points_approved_results_and_access():
    import json
    from datetime import datetime, timezone, timedelta
    from app import _class_now
    now=iso_now(); past=(datetime.now(timezone.utc)-timedelta(days=10)).isoformat(); day=_class_now().date().isoformat()
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        ids=[]
        for no,name in [('A-LBOARD1','Leaderboard Child'),('A-LBOARD2','Leaderboard Peer'),('A-LBOARD3','Leaderboard Outside')]:
            ids.append(c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,section_name,created_at) VALUES (?,?,?,'student','active',1,?,'A',?) RETURNING id",(no,name,hash_password('StudentStrong123'),'Leaderboard Grade' if len(ids)<2 else 'Other Grade',past)).fetchone()['id'])
        child,peer,outside=ids
        parent=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-LBOARD1','Leaderboard Parent',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),past)).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,child,now))
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(peer,json.dumps({'country':'Pakistan','phone':'PRIVATE-PHONE'}),now))
        c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,90,'academic','untagged',?)",(child,now))
        for uid,kind,title,score,maxscore,outcome,status in [(child,'assessment','Private Quiz Title',8,10,'','approved'),(peer,'assessment','Peer secret quiz',9,10,'','approved'),(peer,'assessment','Pending secret',10,10,'','pending'),(child,'assignment','Private homework',None,None,'completed','approved'),(peer,'assignment','Peer homework',None,None,'pending','approved')]:
            c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,outcome,status,created_at) VALUES (?,?,'Maths',?,?,'PRIVATE FEEDBACK',?,?,?,?,?,?)",(uid,admin,kind,title,day,score,maxscore,outcome,status,now))
    owner=TestClient(app); guardian=TestClient(app); student=TestClient(app); guest=TestClient(app)
    for client,no,pw,path in [(owner,'ADMIN-0001','StrongAdmin123','/login'),(guardian,'P-LBOARD1','ParentStrong123','/parent/login'),(student,'A-LBOARD1','StudentStrong123','/login')]:
        csrf(client,path); post(client,path,{'admission_no':no,'password':pw})
    path=f'/parent/children/{child}/leaderboard'
    assert guest.get(path,follow_redirects=False).status_code in (303,403)
    assert student.get(path).status_code==403
    assert guardian.get(f'/parent/children/{peer}/leaderboard').status_code==404
    assert f'href="{path}"' in guardian.get(f'/parent?child={child}').text
    page=guardian.get(path); assert page.status_code==200
    assert 'Leaderboard Peer' in page.text and 'A-LBOARD2' in page.text and 'Pakistan' in page.text and 'Your child' in page.text
    assert 'PRIVATE-PHONE' not in page.text and 'PRIVATE FEEDBACK' not in page.text
    assert guardian.get(path,params={'subject':'invalid'}).status_code==400
    page=guardian.get(path,params={'subject':'Maths','class_name':'Leaderboard Grade'}); assert page.status_code==200
    assert '80.0%' in page.text and '90.0%' in page.text and '1 / 1 completed' in page.text
    assert 'Private Quiz Title' not in page.text and 'Peer secret quiz' not in page.text and 'Pending secret' not in page.text
    assert 'No point records match' in page.text and 'Leaderboard Outside' not in page.text
    assert 'kind=error' in post(owner,f'/admin/students/{child}/points',{'amount':15,'category':'academic','reason':'Invalid subject','subject':'bad'}).headers['location']
    post(owner,f'/admin/students/{child}/points',{'amount':15,'category':'academic','reason':'Math award','subject':'Maths'})
    post(owner,'/admin/challenges/create',{'title':'Subject leaderboard challenge','description':'Test','category':'academic','points':20,'status':'active','subject':'Maths'})
    with connect() as c:
        ch=c.execute("SELECT id FROM challenges WHERE title='Subject leaderboard challenge'").fetchone()['id']
        participation=c.execute("INSERT INTO challenge_participations(challenge_id,user_id,status,created_at,updated_at) VALUES (?,?,'pending',?,?) RETURNING id",(ch,peer,now,now)).fetchone()['id']
    post(owner,f'/admin/submissions/{participation}/review',{'decision':'approved'})
    post(owner,f'/admin/submissions/{participation}/review',{'decision':'approved'})
    with connect() as c:
        points=c.execute('SELECT amount,subject FROM point_transactions WHERE challenge_id=?',(ch,)).fetchall()
        assert len(points)==1 and points[0]['amount']==20 and points[0]['subject']=='Maths'
    post(owner,f'/admin/challenges/{ch}/edit',{'title':'Subject leaderboard challenge','description':'Test','category':'academic','points':20,'subject':'Computer Science'})
    with connect() as c: assert c.execute('SELECT subject FROM point_transactions WHERE challenge_id=?',(ch,)).fetchone()['subject']=='Maths'
    page=guardian.get(path,params={'subject':'Maths','class_name':'Leaderboard Grade'})
    assert '15 pts' in page.text and '20 pts' in page.text and '90 pts' not in page.text
    page=guardian.get(path,params={'challenge_id':ch}); assert '20 pts' in page.text and 'Not ranked' in page.text
    assert guardian.get(path,params={'class_name':'nonexistent'}).status_code==400
    with connect() as c: c.execute('DELETE FROM parent_student_links WHERE parent_id=? AND student_id=?',(parent,child))
    assert guardian.get(path).status_code==404


def test_parent_leaderboard_history_corrections_and_subject_snapshots(monkeypatch):
    import app as module
    from datetime import datetime, timezone, timedelta
    now=datetime(2026,6,20,12,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'_now',lambda:now)
    monkeypatch.setattr(module,'_class_now',lambda:now)
    stamp=lambda days:(now-timedelta(days=days)).isoformat()
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        child=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-LBHIST1','Alpha History','student','active',1,'History Grade',?) RETURNING id",(stamp(50),)).fetchone()['id']
        peer=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,created_at) VALUES ('A-LBHIST2','Beta History','student','active',1,'History Grade',?) RETURNING id",(stamp(50),)).fetchone()['id']
        parent=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-LBHIST1','History Parent',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),stamp(50))).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,child,stamp(50)))
        for uid,amount,days in [(child,10,20),(peer,20,20),(child,20,2),(peer,100,40),(peer,5,10)]:
            c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,?,'general','history',?)",(uid,amount,stamp(days)))
        ch=c.execute("INSERT INTO challenges(title,description,category,points,status,subject,created_at) VALUES ('History challenge','description','academic',5,'active','Maths',?) RETURNING id",(stamp(50),)).fetchone()['id']
        c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,challenge_id,created_at) VALUES (?,5,'academic','legacy challenge',?,?)",(child,ch,stamp(1)))
        old=c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,status,created_at) VALUES (?,?,'Maths','assessment','old quiz','private','2026-06-19',4,10,'approved',?) RETURNING id",(child,admin,stamp(2))).fetchone()['id']
        correction=c.execute("INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,status,replaces_id,created_at) VALUES (?,?,'Maths','assessment','corrected','private','2026-06-19',9,10,'pending',?,?) RETURNING id",(child,admin,old,stamp(1))).fetchone()['id']
    guardian=TestClient(app);csrf(guardian,'/parent/login');post(guardian,'/parent/login',{'admission_no':'P-LBHIST1','password':'ParentStrong123'})
    path=f'/parent/children/{child}/leaderboard'
    page=guardian.get(path,params={'class_name':'History Grade','period':'week'})
    assert page.status_code==200 and '↑ 1' in page.text
    page=guardian.get(path,params={'class_name':'History Grade','subject':'Maths'})
    assert '40.0%' in page.text and '90.0%' not in page.text and '5 pts' in page.text
    with connect() as c:
        c.execute("UPDATE student_progress_records SET status='approved' WHERE id=?",(correction,))
        c.execute("UPDATE challenges SET subject='Computer Science' WHERE id=?",(ch,))
    page=guardian.get(path,params={'class_name':'History Grade','subject':'Maths'})
    assert '90.0%' in page.text and '40.0%' not in page.text and 'No point records match' in page.text
    assert '5 pts' in guardian.get(path,params={'class_name':'History Grade','subject':'Computer Science'}).text
    with connect() as c:
        c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,2,'general','undated','invalid')",(peer,))
    page=guardian.get(path,params={'class_name':'History Grade'})
    assert 'Not available' in page.text


def test_parent_achievements_follow_student_awards_history_and_link_scope():
    owner=TestClient(app); guardian=TestClient(app); student=TestClient(app); guest=TestClient(app)
    now=iso_now()
    with connect() as c:
        first=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('A-BADGE1','First Badge Child',?,'student','active',1,?) RETURNING id",(hash_password('StudentStrong123'),now)).fetchone()['id']
        second=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-BADGE2','Second Badge Child','student','active',1,?) RETURNING id",(now,)).fetchone()['id']
        third=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-BADGE3','Unlinked Badge Child','student','active',1,?) RETURNING id",(now,)).fetchone()['id']
        pid=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-BADGE1','Badge Guardian',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),now)).fetchone()['id']
        for sid in (first,second): c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(pid,sid,now))
    for client,no,pw,path in [(owner,'ADMIN-0001','StrongAdmin123','/login'),(guardian,'P-BADGE1','ParentStrong123','/parent/login'),(student,'A-BADGE1','StudentStrong123','/login')]:
        csrf(client,path); post(client,path,{'admission_no':no,'password':pw})
    for name,points in [('Badge milestone 40',40),('Badge milestone 80',80)]:
        assert 'Achievement%20created' in post(owner,'/admin/achievements/create',{'name':name,'description':'Recorded academic achievement','category':'academic','points_required':points}).headers['location']
    path=f'/parent/children/{first}/achievements'
    assert guest.get(path,follow_redirects=False).status_code in (303,403)
    assert student.get(path).status_code==403 and guardian.get(f'/parent/children/{third}/achievements').status_code==404
    assert f'href="{path}"' in guardian.get(f'/parent?child={first}').text
    page=guardian.get(path); assert page.status_code==200 and 'Badge milestone 40' in page.text and '40 Academic points' in page.text and '0 / 40 points' in page.text
    post(owner,f'/admin/students/{first}/points',{'amount':40,'category':'academic','reason':'Badge test'})
    with connect() as c:
        badge=c.execute("SELECT id FROM achievements WHERE name='Badge milestone 40'").fetchone()['id']
        unlock=c.execute('SELECT unlocked_at FROM student_achievements WHERE user_id=? AND achievement_id=?',(first,badge)).fetchone()['unlocked_at']
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND title='Achievement unlocked' AND body='You unlocked Badge milestone 40.'",(first,)).fetchone()['n']==1
    page=guardian.get(path).text
    assert 'Badge milestone 40' in page and unlock[:10] in page and '40 / 80 points' in page
    assert 'Badge milestone 40' in student.get('/achievements').text
    assert 'Badge milestone 40' in guardian.get(f'/parent?child={first}').text
    other=guardian.get(f'/parent/children/{second}/achievements').text
    assert '0 / 40 points' in other and unlock[:10] not in other
    for _ in range(2): assert guardian.get(path).status_code==200
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM student_achievements WHERE user_id=? AND achievement_id=?',(first,badge)).fetchone()['n']==1
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND title='Achievement unlocked' AND body='You unlocked Badge milestone 40.'",(first,)).fetchone()['n']==1
    post(owner,f'/admin/achievements/{badge}/status',{'status':'inactive'})
    post(owner,f'/admin/students/{first}/points',{'amount':-40,'category':'academic','reason':'Badge adjustment'})
    page=guardian.get(path).text
    assert 'Badge milestone 40' in page and unlock[:10] in page and 'No longer active · preserved in history' in page and '0 / 80 points' in page
    with connect() as c: c.execute('DELETE FROM parent_student_links WHERE parent_id=? AND student_id=?',(pid,first))
    assert guardian.get(path).status_code==404 and guardian.get(f'/parent/children/{second}/achievements').status_code==200


def test_parent_achievements_use_shared_sync_on_reactivation_and_skip_disabled():
    now=iso_now()
    with connect() as c:
        active=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-BSYNC1','Active Badge Child','student','active',1,?) RETURNING id",(now,)).fetchone()['id']
        disabled=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-BSYNC2','Disabled Badge Child','student','disabled',1,?) RETURNING id",(now,)).fetchone()['id']
        parent=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-BSYNC1','Badge Parent',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),now)).fetchone()['id']
        for sid in (active,disabled):
            c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,sid,now))
            c.execute("INSERT INTO point_transactions(user_id,amount,category,reason,created_at) VALUES (?,10,'sports','Recorded',?)",(sid,now))
        badge=c.execute("INSERT INTO achievements(name,description,category,points_required,status,created_at) VALUES ('Reactivated Badge','Existing rule','sports',10,'active',?) RETURNING id",(now,)).fetchone()['id']
    guardian=TestClient(app);csrf(guardian,'/parent/login');post(guardian,'/parent/login',{'admission_no':'P-BSYNC1','password':'ParentStrong123'})
    page=guardian.get(f'/parent?child={active}').text
    assert 'Reactivated Badge' in page
    assert 'Reactivated Badge' in guardian.get(f'/parent/children/{active}/achievements').text
    guardian.get(f'/parent/children/{disabled}/achievements')
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM student_achievements WHERE user_id=? AND achievement_id=?',(active,badge)).fetchone()['n']==1
        assert c.execute('SELECT COUNT(*) n FROM student_achievements WHERE user_id=? AND achievement_id=?',(disabled,badge)).fetchone()['n']==0


def test_parent_challenges_rewards_use_real_student_flow_and_scoped_history():
    now=iso_now()
    with connect() as c:
        child=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,section_name,created_at) VALUES ('A-PRIZE1','Challenge Child',?,'student','active',1,'O-Level - Grade 9','A',?) RETURNING id",(hash_password('StudentStrong123'),now)).fetchone()['id']
        sibling=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,class_name,section_name,created_at) VALUES ('A-PRIZE2','Challenge Sibling','student','active',1,'O-Level - Grade 10','B',?) RETURNING id",(now,)).fetchone()['id']
        stranger=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-PRIZE3','Unlinked Challenge Student','student','active',1,?) RETURNING id",(now,)).fetchone()['id']
        parent=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-PRIZE1','Challenge Guardian',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),now)).fetchone()['id']
        for sid in (child,sibling): c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,sid,now))
        def challenge(title,status,grade,section):
            return c.execute("INSERT INTO challenges(title,description,category,subject,points,status,eligibility_class,eligibility_section,start_date,end_date,created_at) VALUES (?,'Real challenge','academic','Maths',30,?,?,?,'2026-01-01','2026-12-31',?) RETURNING id",(title,status,grade,section,now)).fetchone()['id']
        challenge_id=challenge('Scoped challenge','active','O-Level - Grade 9','A')
        challenge('Scheduled challenge','scheduled','O-Level - Grade 9','A')
        challenge('Other grade challenge','active','O-Level - Grade 10','A')
        challenge('Other section challenge','active','O-Level - Grade 9','B')
        challenge('Secret draft challenge','draft',None,None)
        available=c.execute("INSERT INTO rewards(name,description,points_required,status,quantity,created_at) VALUES ('Scoped prize','Configured reward',20,'active',1,?) RETURNING id",(now,)).fetchone()['id']
        c.execute("INSERT INTO rewards(name,description,points_required,status,quantity,created_at) VALUES ('Future prize','Configured milestone',60,'active',1,?)",(now,))
        stocked=c.execute("INSERT INTO rewards(name,description,points_required,status,quantity,created_at) VALUES ('Stock prize','Configured stock',10,'active',1,?) RETURNING id",(now,)).fetchone()['id']
        c.execute("INSERT INTO reward_claims(reward_id,user_id,status,created_at) VALUES (?,?,'fulfilled',?)",(stocked,sibling,now))
        hidden=c.execute("INSERT INTO rewards(name,description,points_required,status,created_at) VALUES ('Inactive prize','Hidden reward',10,'inactive',?) RETURNING id",(now,)).fetchone()['id']
        c.execute("INSERT INTO reward_claims(reward_id,user_id,status,created_at) VALUES (?,?,'rejected',?)",(hidden,child,now))
    owner=TestClient(app); guardian=TestClient(app); student=TestClient(app); guest=TestClient(app)
    for cl,no,pw,path in [(owner,'ADMIN-0001','StrongAdmin123','/login'),(guardian,'P-PRIZE1','ParentStrong123','/parent/login'),(student,'A-PRIZE1','StudentStrong123','/login')]:
        csrf(cl,path);post(cl,path,{'admission_no':no,'password':pw})
    path=f'/parent/children/{child}/challenges-rewards'
    assert guest.get(path,follow_redirects=False).status_code in (303,403) and student.get(path).status_code==403
    assert guardian.get(f'/parent/children/{stranger}/challenges-rewards').status_code==404
    assert f'href="{path}"' in guardian.get(f'/parent?child={child}').text
    page=guardian.get(path).text
    assert 'Scoped challenge' in page and 'Scheduled challenge' in page and 'Not joined' in page
    assert 'Other grade challenge' not in page and 'Other section challenge' not in page and 'Secret draft challenge' not in page
    assert 'Future prize' in page and 'Stock prize' in page and 'Out of stock' in page
    assert 'Inactive prize' in page and 'Rejected' in page and 'No longer active' in page
    assert guardian.post(f'/rewards/{available}/claim',data={'csrf_token':guardian.cookies['pms_csrf']}).status_code==403
    assert guardian.post(f'/challenges/{challenge_id}/join',data={'csrf_token':guardian.cookies['pms_csrf']}).status_code==403
    post(student,f'/challenges/{challenge_id}/join')
    assert 'Joined · in progress' in guardian.get(path).text
    post(student,f'/challenges/{challenge_id}/submit',{'submission_text':'Private submission proof'})
    assert 'Submitted · awaiting review' in guardian.get(path).text
    with connect() as c: participation=c.execute('SELECT id FROM challenge_participations WHERE challenge_id=? AND user_id=?',(challenge_id,child)).fetchone()['id']
    post(owner,f'/admin/submissions/{participation}/review',{'decision':'approved','review_note':'Private review note'})
    page=guardian.get(path).text
    assert 'Completed · approved' in page and '30 points' in page
    assert 'Private submission proof' not in page and 'Private review note' not in page
    assert 'Scoped prize' in page and 'Threshold reached' in page and '30 / 60 points' in page
    assert 'submitted' in post(student,f'/rewards/{available}/claim').headers['location']
    with connect() as c: claim=c.execute('SELECT id FROM reward_claims WHERE reward_id=? AND user_id=?',(available,child)).fetchone()['id']
    page=guardian.get(path).text; assert 'Pending' in page and 'Redeemed rewards</span><strong>0' in page
    post(owner,f'/admin/reward-claims/{claim}/status',{'status':'approved'})
    assert 'Approved' in guardian.get(path).text
    post(owner,f'/admin/reward-claims/{claim}/status',{'status':'fulfilled'})
    assert 'Fulfilled' in guardian.get(path).text and 'Redeemed rewards</span><strong>1' in guardian.get(path).text
    with connect() as c:
        c.execute("UPDATE challenges SET status='archived',points=55 WHERE id=?",(challenge_id,))
        c.execute("UPDATE rewards SET status='inactive' WHERE id=?",(available,))
        before=c.execute('SELECT COUNT(*) n FROM point_transactions WHERE user_id=?',(child,)).fetchone()['n']
    page=guardian.get(path).text
    assert 'Archived' in page and '55 points' in page and '30 points' in page and 'Fulfilled' in page
    sibling_page=guardian.get(f'/parent/children/{sibling}/challenges-rewards').text
    assert 'Scoped challenge' not in sibling_page and 'Inactive prize' not in sibling_page and 'Stock prize' in sibling_page
    guardian.get(path);guardian.get(path)
    with connect() as c:
        assert c.execute('SELECT COUNT(*) n FROM point_transactions WHERE user_id=?',(child,)).fetchone()['n']==before
        assert c.execute('SELECT COUNT(*) n FROM reward_claims WHERE reward_id=? AND user_id=?',(available,child)).fetchone()['n']==1
        c.execute('DELETE FROM parent_student_links WHERE parent_id=? AND student_id=?',(parent,child))
    assert guardian.get(path).status_code==404


def test_parent_fees_vouchers_proofs_and_admin_waiver_flow():
    import io, secrets
    from PIL import Image
    from app import _fee_rows,_fee_totals
    now=iso_now()
    with connect() as c:
        child=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('A-FEEVIEW1','Fee View Child',?,'student','active',1,?) RETURNING id",(hash_password('StudentStrong123'),now)).fetchone()['id']
        other=c.execute("INSERT INTO users(admission_no,full_name,role,status,claimed,created_at) VALUES ('A-FEEVIEW2','Fee View Other','student','active',1,?) RETURNING id",(now,)).fetchone()['id']
        parent=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('P-FEEVIEW1','Fee Parent',?,'parent','active',1,?) RETURNING id",(hash_password('ParentStrong123'),now)).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,child,now))
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-FEEVIEW','Fee Staff',?,'admin','active',1,'staff','[\"fees\"]',?)",(hash_password('StaffStrong123'),now))
        c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,admin_level,admin_permissions,created_at) VALUES ('ADMIN-NOFEEVW','No Fee Staff',?,'admin','active',1,'staff','[\"students\"]',?)",(hash_password('StaffStrong123'),now))
        method=c.execute("INSERT INTO fee_methods(name,currency,details,active,created_at) VALUES ('Fee Test Bank','PKR','{}',1,?) RETURNING id",(now,)).fetchone()['id']
        def fee(sid,title,amount,currency,due):
            return c.execute("INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,due_date,batch_key,created_at) VALUES (?,?,'June 2026','Current fee','First',?,?,?, ?,?) RETURNING id",(sid,title,amount,currency,due,secrets.token_hex(16),now)).fetchone()['id']
        fid=fee(child,'Parent test tuition',10000,'PKR','2099-01-02')
        usd=fee(child,'Parent test USD',5000,'USD','2099-01-01')
        overdue=fee(child,'Overdue tuition',8000,'PKR','2000-01-01')
        otherfee=fee(other,'Other private fee',30000,'PKR',None)
    owner=TestClient(app); guardian=TestClient(app); student=TestClient(app); fee_staff=TestClient(app); nofee=TestClient(app); guest=TestClient(app)
    for cl,no,pw,path in [(owner,'ADMIN-0001','StrongAdmin123','/login'),(guardian,'P-FEEVIEW1','ParentStrong123','/parent/login'),(student,'A-FEEVIEW1','StudentStrong123','/login'),(fee_staff,'ADMIN-FEEVIEW','StaffStrong123','/login'),(nofee,'ADMIN-NOFEEVW','StaffStrong123','/login')]:
        csrf(cl,path);post(cl,path,{'admission_no':no,'password':pw})
    base=f'/parent/children/{child}/fees'; view=f'{base}/{fid}'; voucher=view+'/voucher.pdf'
    assert guest.get(base,follow_redirects=False).status_code in (303,403) and student.get(base).status_code==403
    assert guardian.get(f'/parent/children/{other}/fees').status_code==404 and guardian.get(f'{base}/{otherfee}').status_code==404
    assert guardian.get(f'{base}/{otherfee}/voucher.pdf').status_code==404 and guardian.get('/admin/fees').status_code==403
    page=guardian.get(base); assert page.status_code==200
    assert f'href="{base}"' in guardian.get(f'/parent?child={child}').text
    assert 'PKR 180.00' in page.text and 'USD 50.00' in page.text and '2099-01-01' in page.text and 'Overdue' in page.text
    assert 'Other private fee' not in page.text and f'Fee reference #{fid}' in page.text
    assert 'Parent test tuition' in guardian.get(view).text
    pdf=guardian.get(voucher); assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-') and 'attachment' in pdf.headers['content-disposition'] and 'no-store' in pdf.headers['cache-control']
    import importlib.util
    if importlib.util.find_spec('pypdf'):
        from pypdf import PdfReader
        text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
        assert 'Parent test tuition' in text and '100.00' in text and 'not proof of payment' in text
    im=io.BytesIO();Image.new('RGB',(8,8),'white').save(im,'PNG'); upload={'receipt':('receipt.png',im.getvalue(),'image/png')}
    form={'submission_key':secrets.token_hex(16),'method_id':method,'amount':'40','currency':'PKR','payment_date':'2024-06-01','reference':'REF-TEST'}
    assert post(guardian,f'{base}/{fid}/submit',form,files=upload).status_code==303
    with connect() as c: payment=c.execute('SELECT id FROM fee_payments WHERE fee_id=?',(fid,)).fetchone()['id']
    receipt=f'{base}/receipts/{payment}/download'
    download=guardian.get(receipt); assert download.status_code==200 and download.headers['content-type']=='image/webp' and 'attachment' in download.headers['content-disposition']
    assert student.get(receipt).status_code==403 and guardian.get(f'/parent/children/{other}/fees/receipts/{payment}/download').status_code==404
    page=guardian.get(base).text; assert 'Submitted for verification' in page and '100.00' in page and 'REF-TEST' in page and 'Fee Test Bank' in page
    assert post(guardian,f'/admin/fees/{fid}/waive',{'reason':'not permitted'}).status_code==403
    assert post(nofee,f'/admin/fees/{fid}/waive',{'reason':'not permitted'}).status_code==403
    assert 'kind=error' in post(fee_staff,f'/admin/fees/{fid}/waive',{'reason':'Pending review'}).headers['location']
    post(fee_staff,f'/admin/fees/payments/{payment}/review',{'decision':'approved'})
    assert 'Partially Paid' in guardian.get(view).text
    assert 'kind=error' in post(fee_staff,f'/admin/fees/{fid}/waive',{'reason':''}).headers['location']
    assert 'Remaining%20balance%20waived' in post(fee_staff,f'/admin/fees/{fid}/waive',{'reason':'Academy assistance'}).headers['location']
    assert 'kind=error' in post(owner,f'/admin/fees/{fid}/waive',{'reason':'duplicate'}).headers['location']
    with connect() as c:
        row=next(r for r in _fee_rows(c,child) if r['id']==fid)
        assert (row['amount'],row['paid'],row['waived'],row['balance'],row['status'])==(10000,4000,6000,0,'Waived')
        assert c.execute('SELECT COUNT(*) n FROM fee_payments WHERE fee_id=?',(fid,)).fetchone()['n']==1
        assert c.execute("SELECT COUNT(*) n FROM fee_waivers WHERE fee_id=? AND revoked_at IS NULL",(fid,)).fetchone()['n']==1
        assert dict(_fee_totals(_fee_rows(c,child)))['PKR']['waived']==6000
    assert 'Waived' in guardian.get(view).text and 'Academy assistance' in guardian.get(base).text and 'Waived' in student.get('/fees').text
    assert 'Pay Fee / Submit Payment' not in guardian.get(view).text
    assert 'kind=error' in post(guardian,f'{base}/{fid}/submit',dict(form,submission_key=secrets.token_hex(16)),files=upload).headers['location']
    assert 'kind=error' in post(fee_staff,f'/admin/fees/{fid}/waiver/reverse',{'reason':''}).headers['location']
    assert 'Waiver%20reversed' in post(fee_staff,f'/admin/fees/{fid}/waiver/reverse',{'reason':'Correction'}).headers['location']
    with connect() as c:
        row=next(r for r in _fee_rows(c,child) if r['id']==fid)
        assert (row['paid'],row['waived'],row['balance'],row['status'])==(4000,0,6000,'Partially Paid')
        w=c.execute('SELECT * FROM fee_waivers WHERE fee_id=?',(fid,)).fetchone()
        assert w['revoked_at'] and w['revocation_reason']=='Correction'
        assert c.execute("SELECT COUNT(*) n FROM audit_logs WHERE action IN ('fee_waived','fee_waiver_reversed') AND details LIKE ?",(f'Fee {fid};%',)).fetchone()['n']==2
    assert '60.00' in guardian.get(view).text
    with connect() as c: c.execute('DELETE FROM parent_student_links WHERE parent_id=? AND student_id=?',(parent,child))
    for url in [base,view,voucher,receipt,f'/fees/receipt/{payment}']: assert guardian.get(url).status_code==404


def test_fee_waiver_and_payment_race_are_serialized():
    import io, secrets
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    now=iso_now()
    with connect() as c:
        student=c.execute("INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at) VALUES ('A-WAIVERACE','Waiver Race',?,'student','active',1,?) RETURNING id",(hash_password('StudentStrong123'),now)).fetchone()['id']
        fee=c.execute("INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,batch_key,created_at) VALUES (?,'Waiver race fee','2026','','',10000,'PKR',?,?) RETURNING id",(student,secrets.token_hex(16),now)).fetchone()['id']
        method=c.execute("INSERT INTO fee_methods(name,currency,details,created_at) VALUES ('Waiver race bank','PKR','{}',?) RETURNING id",(now,)).fetchone()['id']
    admin=TestClient(app); pupil=TestClient(app)
    for cl,no,pw in [(admin,'ADMIN-0001','StrongAdmin123'),(pupil,'A-WAIVERACE','StudentStrong123')]: csrf(cl);post(cl,'/login',{'admission_no':no,'password':pw})
    img=io.BytesIO();Image.new('RGB',(8,8)).save(img,'PNG')
    def waive(): return post(admin,f'/admin/fees/{fee}/waive',{'reason':'Concurrency test'})
    def pay(): return post(pupil,f'/fees/{fee}/submit',{'submission_key':secrets.token_hex(16),'method_id':method,'amount':'100','currency':'PKR','payment_date':'2024-01-01'},files={'receipt':('receipt.png',img.getvalue(),'image/png')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        waiving=pool.submit(waive); paying=pool.submit(pay)
        assert waiving.result().status_code==303 and paying.result().status_code==303
    with connect() as c:
        waivers=c.execute('SELECT COUNT(*) n FROM fee_waivers WHERE fee_id=? AND revoked_at IS NULL',(fee,)).fetchone()['n']
        pending=c.execute("SELECT COUNT(*) n FROM fee_payments WHERE fee_id=? AND status='submitted'",(fee,)).fetchone()['n']
        assert waivers+pending==1


def test_sqlite_fee_waivers_upgrade_preserves_legacy_data(tmp_path):
    import sqlite3
    from db import SCHEMA
    start=SCHEMA.index('CREATE TABLE IF NOT EXISTS fee_waivers (')
    end=SCHEMA.index("CREATE UNIQUE INDEX IF NOT EXISTS fee_one_pending",start)
    old_schema=SCHEMA[:start]+SCHEMA[end:]
    c=sqlite3.connect(tmp_path/'legacy-fee.db');c.row_factory=sqlite3.Row;c.executescript(old_schema)
    c.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('A-WLEG','Legacy','student','active','2024-01-01')")
    sid=c.execute("SELECT id FROM users WHERE admission_no='A-WLEG'").fetchone()['id']
    c.execute("INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,batch_key,created_at) VALUES (?,'Saved Fee','2024','','',10000,'PKR','legacy-waiver','2024-01-01')",(sid,))
    c.commit();c.executescript(SCHEMA);c.executescript(SCHEMA)
    assert c.execute("SELECT amount FROM fee_assignments WHERE batch_key='legacy-waiver'").fetchone()['amount']==10000
    assert c.execute('SELECT COUNT(*) n FROM fee_waivers').fetchone()['n']==0
    assert not c.execute('PRAGMA foreign_key_check').fetchone(); c.close()


def _step12_parent_student(admission_no='A-N1201',class_name='O-Level - Grade 9',parent_no=None):
    if parent_no is None: parent_no='P-'+admission_no[-4:]
    with connect() as c:
        c.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at)
            VALUES (?,?,?,?,?,?,?,?)''',(admission_no,'Notify Student',hash_password('StudentStrong123'),'student','active',1,class_name,iso_now()))
        student=c.execute("SELECT id FROM users WHERE admission_no=?",(admission_no,)).fetchone()['id']
        c.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at)
            VALUES (?,'Notify Guardian',?,'parent','active',1,?)''',(parent_no,hash_password('ParentStrong123'),iso_now()))
        parent=c.execute("SELECT id FROM users WHERE admission_no=?",(parent_no,)).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,student,iso_now()))
    return student,parent

def test_parent_notification_center_scoping_and_read_flow():
    student,parent=_step12_parent_student()
    with connect() as c:
        c.execute("INSERT INTO notifications(user_id,title,body,is_read,kind,student_id,created_at) VALUES (?,?,?,0,'absence',?,?)",(parent,'Student absence recorded','Absent',student,iso_now()))
        c.execute("INSERT INTO notifications(user_id,title,body,is_read,kind,student_id,created_at) VALUES (?,?,?,0,'fee_overdue',?,?)",(parent,'Fee overdue: Tuition','Overdue',student,iso_now()))
        other=c.execute("SELECT id FROM users WHERE role='parent' AND id!=? LIMIT 1",(parent,)).fetchone()
        if other: c.execute("INSERT INTO notifications(user_id,title,body,is_read,kind,created_at) VALUES (?,?,?,0,'absence',?)",(other['id'],'Secret','x',iso_now()))
        notif_id=c.execute("SELECT id FROM notifications WHERE user_id=? AND kind='absence'",(parent,)).fetchone()['id']
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1201','password':'ParentStrong123'})
    page=guardian.get('/parent/notifications')
    assert page.status_code==200 and 'Student absence recorded' in page.text and 'Fee overdue' in page.text
    assert 'nav-badge' in guardian.get('/parent').text
    assert post(guardian,f'/parent/notifications/{notif_id}/read').status_code==303
    after=guardian.get('/parent/notifications')
    assert 'notif-tick' in after.text and 'Mark as read' in after.text
    with connect() as c: row=c.execute('SELECT is_read,read_at FROM notifications WHERE id=?',(notif_id,)).fetchone()
    assert row['is_read']==1 and row['read_at']
    assert post(guardian,'/parent/notifications/read-all',{}).status_code==303
    with connect() as c: assert c.execute('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND is_read=0',(parent,)).fetchone()['n']==0
    filtered=guardian.get('/parent/notifications?filter=fee_overdue')
    assert 'Fee overdue' in filtered.text and 'Student absence recorded' not in filtered.text
    # A parent cannot read another parent's notification.
    if other:
        assert guardian.get('/parent/notifications').status_code==200
        assert post(guardian,'/parent/notifications/1/read').status_code in (303,404)

def test_absence_and_attendance_milestone_notifications():
    student,parent=_step12_parent_student('A-N1202')
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        c.execute('''INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at)
            VALUES ('O-Level - Grade 9','Maths',?,'weekly',0,'09:00',40,?)''',(admin,iso_now()))
        schedule=c.execute("SELECT id FROM class_schedules LIMIT 1").fetchone()['id']
        c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at,ended_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(schedule,'2026-11-02','Maths','O-Level - Grade 9','09:00',40,admin,admin,'ended',iso_now(),iso_now()))
        session=c.execute("SELECT id FROM class_sessions ORDER BY id DESC LIMIT 1").fetchone()['id']
        c.execute('INSERT INTO class_attendance(session_id,student_id,status,marked_by,marked_at) VALUES (?,?,?,?,?)',(session,student,'present',admin,iso_now()))
    owner=TestClient(app); csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1202','password':'ParentStrong123'})
    r=post(owner,f'/admin/my-classes/session/{session}/attendance',{f'attendance_{student}':'absent'})
    assert r.status_code==303
    with connect() as c:
        rows=c.execute("SELECT kind,title FROM notifications WHERE user_id=? AND kind IN ('absence','attendance')",(parent,)).fetchall()
        titles={row['title'] for row in rows}
        assert any(t.startswith('Student absence recorded') or t.startswith('Attendance marked') for t in titles)
    # Second month: perfect attendance triggers one milestone, and repeats do not duplicate.
    sessions=[]
    with connect() as c:
        for day in ('2026-10-05','2026-10-12'):
            c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at,ended_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(schedule,day,'Maths','O-Level - Grade 9','09:00',40,admin,admin,'ended',iso_now(),iso_now()))
            sid=c.execute("SELECT id FROM class_sessions ORDER BY id DESC LIMIT 1").fetchone()['id']
            c.execute('INSERT INTO class_attendance(session_id,student_id,status,marked_by,marked_at) VALUES (?,?,NULL,?,?)',(sid,student,admin,iso_now()))
            sessions.append(sid)
    for sid in sessions:
        post(owner,f'/admin/my-classes/session/{sid}/attendance',{f'attendance_{student}':'present'})
    with connect() as c:
        n=c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='attendance'",(parent,)).fetchone()['n']
        assert n==1, n
        titles=[r['title'] for r in c.execute("SELECT title FROM notifications WHERE user_id=? AND kind='attendance'",(parent,)).fetchall()]
        assert any('Perfect attendance' in t for t in titles)

def test_assessment_remark_assignment_notifications_reach_parents():
    student,parent=_step12_parent_student('A-N1203')
    with connect() as c:
        c.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at)
            VALUES ('A-TEACH12','Notify Teacher',?,'admin','active',1,'O-Level - Grade 9',?)''',(hash_password('TeacherStrong123'),iso_now()))
        teacher=c.execute("SELECT id FROM users WHERE admission_no='A-TEACH12'").fetchone()['id']
        c.execute('INSERT INTO academy_signup_profiles(user_id,profile_json,created_at) VALUES (?,?,?)',(student,'{"subjects":["Maths"]}',iso_now()))
        c.execute('''INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at)
            VALUES ('O-Level - Grade 9','Maths',?,'weekly',0,'09:00',40,?)''',(teacher,iso_now()))
    tutor=TestClient(app); csrf(tutor); post(tutor,'/login',{'admission_no':'A-TEACH12','password':'TeacherStrong123'})
    owner=TestClient(app); csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1203','password':'ParentStrong123'})
    kinds={'assessment':'assessment','feedback':'remark','assignment':'assignment'}
    with connect() as c:
        for kind in kinds:
            c.execute('''INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,outcome,assessment_type,feedback_type,period_start,period_end,participation_type,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(student,teacher,'Maths',kind,f'{kind} record','d','2026-11-01',80,100,'completed','general','general','','','general',iso_now()))
    with connect() as c:
        ids=[r['id'] for r in c.execute("SELECT id FROM student_progress_records WHERE student_id=? ORDER BY id",(student,)).fetchall()]
    for rid,kind in zip(ids,kinds):
        review_progress(owner,rid,{'decision':'approved'})
    with connect() as c:
        rows=c.execute("SELECT kind,title FROM notifications WHERE user_id=? AND kind IN ('assessment','remark','assignment')",(parent,)).fetchall()
        found={row['kind'] for row in rows}
        assert found=={'assessment','remark','assignment'}, found
    page=guardian.get('/parent/notifications')
    for title in ('New assessment result','New teacher remarks','Assignment update'):
        assert title in page.text

def test_announcement_delivery_to_parents():
    student,parent=_step12_parent_student('A-N1204')
    _s10,parent10=_step12_parent_student('A-N1208',class_name='O-Level - Grade 10')
    owner=TestClient(app); csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    assert post(owner,'/admin/announcements/create',{'title':'Holiday notice','body':'Classes closed next Monday.','audience':'all'}).status_code==303
    with connect() as c:
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='announcement'",(parent,)).fetchone()['n']==1
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='announcement'",(parent10,)).fetchone()['n']==1
    # Class-scoped announcements only reach parents of students in that class.
    assert post(owner,'/admin/announcements/create',{'title':'Grade 10 notice','body':'Grade 10 assembly.','audience':'class','class_name':'O-Level - Grade 10'}).status_code==303
    with connect() as c:
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE title LIKE 'Academy announcement: Grade 10%' AND user_id=?",(parent,)).fetchone()['n']==0
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE title LIKE 'Academy announcement: Grade 10%' AND user_id=?",(parent10,)).fetchone()['n']==1

def test_fee_reminder_and_overdue_notifications_are_idempotent():
    student,parent=_step12_parent_student('A-N1205')
    from datetime import date as _date, timedelta as _td
    overdue_date=(_date.today()-_td(days=5)).isoformat(); soon_date=(_date.today()+_td(days=3)).isoformat()
    with connect() as c:
        c.execute('''INSERT INTO fee_methods(name,currency,details,active,created_at) VALUES ('Bank','PKR','{}',1,?)''',(iso_now(),))
        c.execute('''INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,due_date,batch_key,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',(student,'Overdue Tuition','2026-10','d','',50000000,'PKR',overdue_date,'batch-n1205-a',iso_now()))
        c.execute('''INSERT INTO fee_assignments(student_id,title,period,description,installment,amount,currency,due_date,batch_key,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',(student,'Due Soon Tuition','2026-11','d','',50000000,'PKR',soon_date,'batch-n1205-b',iso_now()))
    from app import run_fee_notifications
    with connect() as conn: run_fee_notifications(conn)
    with connect() as c:
        overdue=c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='fee_overdue'",(parent,)).fetchone()['n']
        reminder=c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='fee_reminder'",(parent,)).fetchone()['n']
        assert overdue==1 and reminder==1, (overdue,reminder)
    with connect() as conn: run_fee_notifications(conn)
    with connect() as c:
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='fee_overdue'",(parent,)).fetchone()['n']==1
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='fee_reminder'",(parent,)).fetchone()['n']==1
    # Paying the fee clears future reminders and does not resurrect overdue alerts.
    with connect() as c:
        fee_id=c.execute("SELECT id FROM fee_assignments WHERE batch_key='batch-n1205-b'").fetchone()['id']
        c.execute('''INSERT INTO fee_payments(fee_id,student_id,method_id,method_name,amount,currency,payment_date,reference,notes,receipt,status,submitted_at,submission_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',(fee_id,student,1,'Bank',50000000,'PKR','2026-11-01','ref','n','\x01','approved',iso_now(),'key-n1205'))
    with connect() as conn: run_fee_notifications(conn)
    with connect() as c:
        assert c.execute("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND kind='fee_reminder' AND body LIKE 'Due Soon%'",(parent,)).fetchone()['n']==1

def test_achievement_and_challenge_notifications_reach_parents():
    student,parent=_step12_parent_student('A-N1206')
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        c.execute('''INSERT INTO achievements(name,description,category,points_required,status,created_at)
            VALUES ('Scholar','Top academic points','academic',10,'active',?)''',(iso_now(),))
        ach=c.execute("SELECT id FROM achievements ORDER BY id DESC LIMIT 1").fetchone()['id']
        c.execute('''INSERT INTO challenges(title,description,category,points,status,created_by,created_at)
            VALUES ('Quick Challenge','A test','academic',10,'active',?,?)''',(admin,iso_now()))
        challenge=c.execute("SELECT id FROM challenges ORDER BY id DESC LIMIT 1").fetchone()['id']
        c.execute('INSERT INTO point_transactions(user_id,amount,category,reason,admin_id,created_at) VALUES (?,?,?,?,?,?)',(student,10,'academic','test award',admin,iso_now()))
    with connect() as conn:
        from app import sync_achievements
        sync_achievements(conn,student)
    owner=TestClient(app); csrf(owner); post(owner,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    with connect() as c:
        cp=c.execute('INSERT INTO challenge_participations(challenge_id,user_id,status,submission_text,created_at,updated_at) VALUES (?,?,?,?,?,?)',(challenge,student,'pending','work',iso_now(),iso_now()))
        pid=c.execute('SELECT id FROM challenge_participations ORDER BY id DESC LIMIT 1').fetchone()['id']
    post(owner,f'/admin/submissions/{pid}/review',{'decision':'approved','review_note':'Nice work'})
    with connect() as c:
        rows=c.execute("SELECT kind,title FROM notifications WHERE user_id=? AND kind IN ('achievement','challenge')",(parent,)).fetchall()
        found={row['title'] for row in rows}
        assert 'Achievement unlocked' in found and 'Challenge completed' in found, found
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1206','password':'ParentStrong123'})
    page=guardian.get('/parent/notifications')
    assert 'Achievement unlocked' in page.text and 'Challenge completed' in page.text

def test_dashboard_unread_badges_on_all_three_portals():
    student,parent=_step12_parent_student('A-N1207')
    with connect() as c:
        c.execute("INSERT INTO notifications(user_id,title,body,is_read,kind,student_id,created_at) VALUES (?,?,?,0,'absence',?,?)",(parent,'Absence','x',student,iso_now()))
        c.execute("INSERT INTO notifications(user_id,title,body,is_read,kind,student_id,created_at) VALUES (?,?,?,0,'fee',?,?)",(student,'Fee assigned','x',student,iso_now()))
        admin_id=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        c.execute("INSERT INTO notifications(user_id,title,body,is_read,kind,created_at) VALUES (?,?,?,0,'fee',?)",(admin_id,'Fee receipt submitted','x',iso_now()))
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1207','password':'ParentStrong123'})
    learner=TestClient(app); csrf(learner); post(learner,'/login',{'admission_no':'A-N1207','password':'StudentStrong123'})
    admin=TestClient(app); csrf(admin); post(admin,'/login',{'admission_no':'ADMIN-0001','password':'StrongAdmin123'})
    assert 'notif-badge' in guardian.get('/parent').text
    assert 'notif-badge' in learner.get('/student').text
    assert 'notif-badge' in admin.get('/admin').text
    assert 'notif-badge' in learner.get('/notifications').text


def test_sqlite_notifications_upgrade_preserves_legacy_rows(tmp_path):
    import sqlite3
    from db import SCHEMA
    start=SCHEMA.index('CREATE TABLE IF NOT EXISTS notifications (')
    end=SCHEMA.index("CREATE TABLE IF NOT EXISTS audit_logs",start)
    old_schema=SCHEMA[:start]+SCHEMA[end:]
    for index_line in ('CREATE INDEX IF NOT EXISTS idx_notifications_user_read','CREATE INDEX IF NOT EXISTS idx_notifications_kind','CREATE INDEX IF NOT EXISTS idx_notifications_student'):
        old_schema='\n'.join(line for line in old_schema.splitlines() if not line.startswith(index_line))
    old_notifications='''CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  is_read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);'''
    c=sqlite3.connect(tmp_path/'legacy-notif.db');c.row_factory=sqlite3.Row;c.executescript(old_schema+'\n'+old_notifications)
    c.execute("INSERT INTO users(admission_no,full_name,role,status,created_at) VALUES ('A-NLEG','Legacy','student','active','2024-01-01')")
    uid=c.execute("SELECT id FROM users WHERE admission_no='A-NLEG'").fetchone()['id']
    c.execute("INSERT INTO notifications(user_id,title,body,is_read,created_at) VALUES (?,?,?,0,?)",(uid,'Old notice','Preserved body',iso_now()))
    c.commit()
    # Same upgrade path as init_db(): fresh SCHEMA script plus the ALTER migration.
    from db import _migrate_sqlite_notification_categories
    c.executescript(SCHEMA); _migrate_sqlite_notification_categories(c); _migrate_sqlite_notification_categories(c)
    row=c.execute('SELECT title,body,kind,is_read FROM notifications WHERE user_id=?',(uid,)).fetchone()
    assert row['title']=='Old notice' and row['body']=='Preserved body' and row['kind']=='update' and row['is_read']==0
    assert not c.execute('PRAGMA foreign_key_check').fetchone(); c.close()


def _step13_student(admission_no='A-AN1301',class_name='O-Level - Grade 9'):
    with connect() as c:
        c.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,class_name,created_at)
            VALUES (?,?,?,?,?,?,?,?)''',(admission_no,'Analytics Student',hash_password('StudentStrong123'),'student','active',1,class_name,iso_now()))
        student=c.execute("SELECT id FROM users WHERE admission_no=?",(admission_no,)).fetchone()['id']
        c.execute('''INSERT INTO users(admission_no,full_name,password_hash,role,status,claimed,created_at)
            VALUES (?,'Analytics Guardian',?,'parent','active',1,?)''',('P-'+admission_no[-4:],hash_password('ParentStrong123'),iso_now()))
        parent=c.execute("SELECT id FROM users WHERE admission_no=?",('P-'+admission_no[-4:],)).fetchone()['id']
        c.execute('INSERT INTO parent_student_links(parent_id,student_id,created_at) VALUES (?,?,?)',(parent,student,iso_now()))
    return student,parent

def _step13_progress(c,student,teacher,kind,subject,title,score,score_max,outcome,days_ago):
    from datetime import timedelta as _td
    score=None if score in ('',None) else score
    c.execute('''INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,outcome,status,assessment_type,feedback_type,period_start,period_end,participation_type,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(student,teacher,subject,kind,title,'d',(date.today()-_td(days=days_ago)).isoformat(),score,score_max,outcome,'approved','general','general','','','general',iso_now()))

def test_parent_analytics_periods_metrics_and_scope():
    student,parent=_step13_student()
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        c.execute('''INSERT INTO achievements(name,description,category,points_required,status,created_at)
            VALUES ('Scholar','Top academic points','academic',10,'active',?)''',(iso_now(),))
        c.execute('''INSERT INTO challenges(title,description,category,points,status,created_by,created_at)
            VALUES ('Analytics Challenge','A test','academic',10,'active',?,?)''',(admin,iso_now()))
        c.execute('''INSERT INTO challenges(title,description,category,points,status,created_by,created_at)
            VALUES ('Analytics Challenge 2','Another test','academic',10,'active',?,?)''',(admin,iso_now()))
        challenge=c.execute("SELECT id FROM challenges WHERE title='Analytics Challenge 2'").fetchone()['id']
        done=c.execute("SELECT id FROM challenges WHERE title='Analytics Challenge'").fetchone()['id']
        c.execute('INSERT INTO point_transactions(user_id,amount,category,reason,admin_id,created_at) VALUES (?,?,?,?,?,?)',(student,10,'academic','test',admin,iso_now()))
        c.execute('INSERT INTO challenge_participations(challenge_id,user_id,status,awarded,created_at,updated_at) VALUES (?,?,?,1,?,?)',(done,student,'approved',iso_now(),iso_now()))
        c.execute('INSERT INTO challenge_participations(challenge_id,user_id,status,awarded,created_at,updated_at) VALUES (?,?,?,0,?,?)',(challenge,student,'pending',iso_now(),iso_now()))
        _step13_progress(c,student,admin,'assessment','Maths','Maths Test A',90,100,'',1)
        _step13_progress(c,student,admin,'assessment','Maths','Maths Test B',100,100,'',2)
        _step13_progress(c,student,admin,'assessment','English','English Test',60,100,'',3)
        _step13_progress(c,student,admin,'assignment','Maths','Maths Assignment 1','',0,'completed',1)
        _step13_progress(c,student,admin,'assignment','Maths','Maths Assignment 2','',0,'pending',2)
        _step13_progress(c,student,admin,'participation','Maths','Class participation','',0,'',4)
        c.execute("INSERT INTO class_schedules(grade,subject,teacher_id,recurrence,weekday,start_time,duration_minutes,created_at) VALUES ('O-Level - Grade 9','Maths',?,'weekly',0,'09:00',40,?)",(admin,iso_now()))
        schedule=c.execute("SELECT id FROM class_schedules ORDER BY id DESC LIMIT 1").fetchone()['id']
        from datetime import timedelta as _td
        for days_ago,status in ((1,'present'),(2,'absent')):
            c.execute("INSERT INTO class_sessions(schedule_id,session_date,subject,grade,start_time,duration_minutes,teacher_id,started_by,status,started_at,ended_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(schedule,(date.today()-_td(days=days_ago)).isoformat(),'Maths','O-Level - Grade 9','09:00',40,admin,admin,'ended',iso_now(),iso_now()))
            sid=c.execute("SELECT id FROM class_sessions ORDER BY id DESC LIMIT 1").fetchone()['id']
            c.execute('INSERT INTO class_attendance(session_id,student_id,status,marked_by,marked_at) VALUES (?,?,?,?,?)',(sid,student,status,admin,iso_now()))
        c.execute("INSERT INTO academic_terms(name,start_date,end_date,created_by,created_at) VALUES ('Autumn 2026',?,?,?,?)",((date.today()-_td(days=90)).isoformat(),(date.today()+_td(days=90)).isoformat(),admin,iso_now()))
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1301','password':'ParentStrong123'})
    dash=guardian.get('/parent')
    assert dash.status_code==200 and '/analytics' in dash.text
    week=guardian.get(f'/parent/children/{student}/analytics?period=week')
    assert week.status_code==200 and 'Student analytics' in week.text
    assert '83.3%' in week.text, 'academic average'
    assert '50%' in week.text, 'challenge rate'
    assert 'Scholar' in week.text and 'Unlocked' in week.text, 'achievement'
    month=guardian.get(f'/parent/children/{student}/analytics?period=month')
    assert month.status_code==200 and 'Monthly' in month.text
    term=guardian.get(f'/parent/children/{student}/analytics?period=term')
    assert term.status_code==200 and 'Autumn 2026' in term.text
    default=guardian.get(f'/parent/children/{student}/analytics?period=bogus')
    assert default.status_code==200
    # A parent cannot view analytics for a child they are not linked to.
    other_student,_=_step13_student('A-AN1302')
    assert guardian.get(f'/parent/children/{other_student}/analytics').status_code==404

def test_parent_analytics_strengths_and_improvements():
    student,parent=_step13_student('A-AN1303')
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        _step13_progress(c,student,admin,'assessment','Maths','Strong Maths',95,100,'',2)
        _step13_progress(c,student,admin,'assessment','English','Weak English',40,100,'',2)
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1303','password':'ParentStrong123'})
    page=guardian.get(f'/parent/children/{student}/analytics')
    assert page.status_code==200
    assert 'Maths' in page.text and 'English' in page.text
    assert 'English needs attention' in page.text
    assert 'strong' in page.text

def test_parent_analytics_superseded_records_are_excluded():
    student,parent=_step13_student('A-AN1304')
    with connect() as c:
        admin=c.execute("SELECT id FROM users WHERE admission_no='ADMIN-0001'").fetchone()['id']
        from datetime import timedelta as _td
        c.execute('''INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,outcome,status,assessment_type,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',(student,admin,'Maths','assessment','Old Maths','d',(date.today()-_td(days=5)).isoformat(),50,100,'','approved','general',iso_now()))
        old=c.execute("SELECT id FROM student_progress_records WHERE title='Old Maths'").fetchone()['id']
        c.execute('''INSERT INTO student_progress_records(student_id,teacher_id,subject,kind,title,details,record_date,score,score_max,outcome,status,assessment_type,replaces_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(student,admin,'Maths','assessment','New Maths','d',(date.today()-_td(days=1)).isoformat(),100,100,'','approved','general',old,iso_now()))
    guardian=TestClient(app); csrf(guardian); post(guardian,'/login',{'admission_no':'P-1304','password':'ParentStrong123'})
    page=guardian.get(f'/parent/children/{student}/analytics?period=week')
    assert page.status_code==200
    assert '100.0%' in page.text and '83.3' not in page.text
