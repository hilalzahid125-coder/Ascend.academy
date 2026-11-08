# ASCEND v1.4 runtime patch
# Loaded after the v1.3 route fragments so the production loader can stay compact.
APP_VERSION = '1.4.0'

def render(request: Request, name: str, context=None, status_code=200):
    context = context or {}
    csrf = request.cookies.get('pms_csrf') or new_token(24)
    user = current_user(request)
    context.update({'request':request,'settings':settings(),'user':user,
                    'msg':request.query_params.get('msg'),'kind':request.query_params.get('kind','success'),
                    'csrf_token':csrf,
                    'is_super_admin':is_super_admin(user),
                    'admin_permissions':_admin_permissions(user),
                    'staff_permission_labels':STAFF_PERMISSION_LABELS,
                    'app_version':APP_VERSION,'academy_grades':ACADEMY_GRADES})
    response = templates.TemplateResponse(request=request, name=name, context=context, status_code=status_code)
    if not request.cookies.get('pms_csrf'):
        set_app_cookie(response,'pms_csrf',csrf)
    return response


def _v14_remove_route(path, method='GET'):
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r,'path',None)==path and method in (getattr(r,'methods',set()) or set()))]

_v14_remove_route('/student','GET')
@app.get('/student', response_class=HTMLResponse)
def student_dashboard(request: Request):
    u=require_user(request,'student')
    with connect() as conn:
        profile=academy_profile_from_row(conn.execute('SELECT profile_json FROM academy_signup_profiles WHERE user_id=?',(u['id'],)).fetchone())
        points=total_points(conn,u['id'])
        rank=conn.execute('''SELECT 1+COUNT(*) rank FROM (
                                SELECT u2.id,u2.full_name,COALESCE(SUM(p.amount),0) total
                                FROM users u2 LEFT JOIN point_transactions p ON p.user_id=u2.id
                                WHERE u2.role='student' AND u2.status='active'
                                GROUP BY u2.id
                             ) x WHERE x.total > ? OR (x.total = ? AND (x.full_name < ? OR (x.full_name = ? AND x.id < ?)))''',(points,points,u['full_name'],u['full_name'],u['id'])).fetchone()['rank']
        leaders=conn.execute('''SELECT u2.id,u2.full_name,u2.admission_no,u2.class_name,u2.section_name,u2.profile_picture_path,
                                       COALESCE(SUM(p.amount),0) points
                                FROM users u2 LEFT JOIN point_transactions p ON p.user_id=u2.id
                                WHERE u2.role='student' AND u2.status='active'
                                GROUP BY u2.id ORDER BY points DESC,u2.full_name ASC,u2.id ASC LIMIT 3''').fetchall()
        challenges=conn.execute('''SELECT c.*, cp.status participation_status FROM challenges c
                                   LEFT JOIN challenge_participations cp ON cp.challenge_id=c.id AND cp.user_id=?
                                   WHERE c.status IN ('active','scheduled')
                                   AND (c.eligibility_class IS NULL OR c.eligibility_class='' OR c.eligibility_class=?)
                                   AND (c.eligibility_section IS NULL OR c.eligibility_section='' OR c.eligibility_section=?)
                                   ORDER BY c.status='active' DESC,c.end_date LIMIT 4''',(u['id'],u['class_name'],u['section_name'])).fetchall()
        sync_achievements(conn,u['id'])
        achievement_rows=conn.execute('''SELECT a.*,sa.unlocked_at FROM achievements a
                                         LEFT JOIN student_achievements sa ON sa.achievement_id=a.id AND sa.user_id=?
                                         WHERE a.status='active' ORDER BY a.points_required,a.name''',(u['id'],)).fetchall()
        achievement_preview=[]
        for row in achievement_rows:
            item=dict(row)
            item['current_points']=total_points(conn,u['id'],None if row['category']=='overall' else row['category'])
            item['remaining']=max(0,row['points_required']-item['current_points'])
            achievement_preview.append(item)
        achievement_preview.sort(key=lambda x:(0 if not x['unlocked_at'] else 1,x['remaining'],x['points_required']))
        achievement_preview=achievement_preview[:3]
        reward_rows=conn.execute('''SELECT r.*,rc.status claim_status FROM rewards r
                                    LEFT JOIN reward_claims rc ON rc.reward_id=r.id AND rc.user_id=?
                                    WHERE r.status='active' ORDER BY r.points_required,r.name''',(u['id'],)).fetchall()
        rewards_preview=[dict(r) for r in reward_rows]
        rewards_preview.sort(key=lambda x:(0 if x['points_required']>=points else 1,abs(x['points_required']-points),x['points_required']))
        rewards_preview=rewards_preview[:3]
        tx=conn.execute('SELECT * FROM point_transactions WHERE user_id=? ORDER BY id DESC LIMIT 5',(u['id'],)).fetchall()
        announcements=conn.execute('''SELECT * FROM announcements WHERE status='published' AND
                                      (audience='all' OR (audience='class' AND class_name=?) OR (audience='section' AND class_name=? AND section_name=?))
                                      ORDER BY id DESC LIMIT 3''',(u['class_name'],u['class_name'],u['section_name'])).fetchall()
        unread=conn.execute('SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0',(u['id'],)).fetchone()['c']
    return render(request,'student_dashboard.html',{
        'points':points,'rank':rank,'academy_profile':profile,'leaders':leaders,'challenges':challenges,
        'achievements_preview':achievement_preview,'rewards_preview':rewards_preview,
        'transactions':tx,'announcements':announcements,'unread_notifications':unread
    })


_v14_remove_route('/admin','GET')
@app.get('/admin', response_class=HTMLResponse)
def admin_dashboard(request: Request):
    a=require_admin(request)
    with connect() as conn:
        stats={
          'students':conn.execute('SELECT COUNT(*) c FROM users WHERE role="student"').fetchone()['c'],
          'active_challenges':conn.execute('SELECT COUNT(*) c FROM challenges WHERE status="active"').fetchone()['c'],
          'pending':conn.execute('SELECT COUNT(*) c FROM challenge_participations WHERE status="pending"').fetchone()['c'],
          'points':conn.execute('SELECT COALESCE(SUM(amount),0) c FROM point_transactions').fetchone()['c'],
        }
        top=conn.execute('''SELECT u.full_name,u.admission_no,u.profile_picture_path,COALESCE(SUM(p.amount),0) points FROM users u
                            LEFT JOIN point_transactions p ON p.user_id=u.id WHERE u.role='student' AND u.status='active'
                            GROUP BY u.id ORDER BY points DESC,u.full_name ASC LIMIT 5''').fetchall()
        logs=conn.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 8').fetchall() if (is_super_admin(a) or 'activity' in _admin_permissions(a)) else []
    return render(request,'admin_dashboard.html',{'stats':stats,'top':top,'logs':logs})


@app.post('/admin/students/{student_id}/delete')
def admin_student_delete(request: Request, student_id:int):
    a=require_admin(request,super_only=True)
    with connect() as conn:
        student=conn.execute('SELECT id,admission_no,full_name,profile_picture_path FROM users WHERE id=? AND role="student"',(student_id,)).fetchone()
        if not student:
            return flash_redirect('/admin/students','Student not found.','error')
        admission_no=student['admission_no']; full_name=student['full_name']; photo_path=student['profile_picture_path']
        conn.execute('DELETE FROM users WHERE id=? AND role="student"',(student_id,))
        audit(conn,a['id'],'student_deleted',f'{admission_no}: {full_name}')
    if photo_path and photo_path.startswith('/uploads/'):
        delete_upload(Path(photo_path).name)
    return flash_redirect('/admin/students',f'Student {admission_no} and linked student data were deleted.')
