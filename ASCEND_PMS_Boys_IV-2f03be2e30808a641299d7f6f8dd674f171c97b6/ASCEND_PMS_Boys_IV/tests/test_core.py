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
            assert '#c20a0a' in client.get('/static/style.css').text
            assert '#c20a0a' in client.get('/static/app-logo.svg').text
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
    assert 'Coming soon' in second.get('/my-classes').text
    assert 'Coming soon' not in student.get('/my-classes').text
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
