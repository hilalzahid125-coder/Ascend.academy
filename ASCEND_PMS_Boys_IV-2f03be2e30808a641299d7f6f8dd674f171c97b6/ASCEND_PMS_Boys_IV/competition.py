from security import iso_now

ACHIEVEMENTS = [
    ('First Step','Earn your first 100 points in ASCEND.','overall',100),
    ('Academic Momentum','Earn 250 Academic points.','academic',250),
    ('Sports Momentum','Earn 250 Sports points.','sports',250),
    ('Character Leader','Earn 250 Character points.','character',250),
    ('Activity Contributor','Earn 250 Activity points.','activity',250),
    ('Rising Star','Reach 500 total points.','overall',500),
    ('High Achiever','Reach 1,000 total points.','overall',1000),
    ('ASCEND Elite','Reach 2,000 total points.','overall',2000),
]

# These are intentionally DRAFTS. An admin should edit dates/eligibility before publishing.
CHALLENGE_TEMPLATES = [
    ('Weekly Quiz Challenge','Take part in a school-approved weekly quiz and submit the required result or evidence.','academic',100),
    ('Reading Goal','Complete the assigned reading goal and submit a short reflection or teacher confirmation.','academic',75),
    ('Science Problem-Solving','Complete the assigned science problem-solving activity.','academic',100),
    ('Inter-Class Sports Participation','Represent your class in a school sports activity or competition.','sports',100),
    ('Fitness & Teamwork Challenge','Complete the approved fitness or teamwork activity.','sports',75),
    ('Campus Care & Cleanliness','Take part in a school-approved cleanliness or campus-care activity.','character',75),
    ('Respect & Responsibility','Complete a teacher-approved responsibility or positive-character challenge.','character',50),
    ('School Activity Participation','Participate meaningfully in an approved school activity or event.','activity',75),
    ('Creative Showcase','Submit an approved creative, speaking, art, technology or project showcase.','activity',100),
]

REWARDS = [
    ('Recognition Certificate','A configurable school recognition milestone for sustained participation.',500,'inactive'),
    ('Excellence Recognition','A configurable higher-level recognition milestone.',1000,'inactive'),
]


def install_starter_structure(conn, admin_id):
    added={'achievements':0,'challenges':0,'rewards':0}
    for name,desc,cat,pts in ACHIEVEMENTS:
        if not conn.execute('SELECT 1 FROM achievements WHERE name=?',(name,)).fetchone():
            conn.execute('INSERT INTO achievements(name,description,category,points_required,status,created_at) VALUES (?,?,?,? ,"active",?)',(name,desc,cat,pts,iso_now()))
            added['achievements']+=1
    for title,desc,cat,pts in CHALLENGE_TEMPLATES:
        if not conn.execute('SELECT 1 FROM challenges WHERE title=?',(title,)).fetchone():
            conn.execute('''INSERT INTO challenges(title,description,category,points,status,created_by,created_at)
                            VALUES (?,?,?,?,'draft',?,?)''',(title,desc,cat,pts,admin_id,iso_now()))
            added['challenges']+=1
    for name,desc,pts,status in REWARDS:
        if not conn.execute('SELECT 1 FROM rewards WHERE name=?',(name,)).fetchone():
            conn.execute('INSERT INTO rewards(name,description,points_required,status,created_at) VALUES (?,?,?,?,?)',(name,desc,pts,status,iso_now()))
            added['rewards']+=1
    conn.execute("INSERT INTO settings(key,value) VALUES ('competition_structure_version','1') ON CONFLICT(key) DO UPDATE SET value='1'")
    return added

DEMO_ADMISSIONS = ['A-6738','A-6741','A-6810','A-6882','A-6901','A-6920']
DEMO_CHALLENGES = ['Math Sprint','Inter-Class Football','Clean & Green Campus','Reading Week']
DEMO_ACHIEVEMENTS = ['First Century','Academic Spark','Sports Starter','Rising Performer']
DEMO_REWARDS = ['Achievement Certificate','Principal Recognition']


def demo_counts(conn):
    qmarks=lambda xs: ','.join('?' for _ in xs)
    return {
        'students': conn.execute(f'SELECT COUNT(*) c FROM users WHERE admission_no IN ({qmarks(DEMO_ADMISSIONS)})',DEMO_ADMISSIONS).fetchone()['c'],
        'challenges': conn.execute(f'SELECT COUNT(*) c FROM challenges WHERE title IN ({qmarks(DEMO_CHALLENGES)})',DEMO_CHALLENGES).fetchone()['c'],
        'achievements': conn.execute(f'SELECT COUNT(*) c FROM achievements WHERE name IN ({qmarks(DEMO_ACHIEVEMENTS)})',DEMO_ACHIEVEMENTS).fetchone()['c'],
        'rewards': conn.execute(f'SELECT COUNT(*) c FROM rewards WHERE name IN ({qmarks(DEMO_REWARDS)})',DEMO_REWARDS).fetchone()['c'],
        'announcements': conn.execute("SELECT COUNT(*) c FROM announcements WHERE title='Welcome to ASCEND' AND body LIKE 'Challenges, leaderboards and rewards are now live.%'").fetchone()['c'],
    }


def purge_known_demo_content(conn):
    qmarks=lambda xs: ','.join('?' for _ in xs)
    counts=demo_counts(conn)
    conn.execute(f'DELETE FROM users WHERE role="student" AND admission_no IN ({qmarks(DEMO_ADMISSIONS)})',DEMO_ADMISSIONS)
    demo_challenge_ids=[r['id'] for r in conn.execute(f'SELECT id FROM challenges WHERE title IN ({qmarks(DEMO_CHALLENGES)})',DEMO_CHALLENGES).fetchall()]
    if demo_challenge_ids:
        marks=','.join('?' for _ in demo_challenge_ids)
        conn.execute(f'DELETE FROM point_transactions WHERE challenge_id IN ({marks})',demo_challenge_ids)
        conn.execute(f'DELETE FROM challenges WHERE id IN ({marks})',demo_challenge_ids)
    conn.execute(f'DELETE FROM achievements WHERE name IN ({qmarks(DEMO_ACHIEVEMENTS)})',DEMO_ACHIEVEMENTS)
    conn.execute(f'DELETE FROM rewards WHERE name IN ({qmarks(DEMO_REWARDS)})',DEMO_REWARDS)
    conn.execute("DELETE FROM announcements WHERE title='Welcome to ASCEND' AND body LIKE 'Challenges, leaderboards and rewards are now live.%'")
    return counts
