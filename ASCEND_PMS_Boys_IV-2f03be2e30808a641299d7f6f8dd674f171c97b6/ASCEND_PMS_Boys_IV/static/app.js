function setSidebar(open){
  const sidebar=document.getElementById('sidebar');
  const overlay=document.getElementById('sidebarOverlay');
  const trigger=document.querySelector('.menu-btn');
  if(!sidebar)return;
  sidebar.classList.toggle('open',!!open);
  overlay?.classList.toggle('open',!!open);
  document.body.classList.toggle('nav-open',!!open && window.innerWidth<=820);
  trigger?.setAttribute('aria-expanded',open?'true':'false');
  overlay?.setAttribute('aria-hidden',open?'false':'true');
}
function toggleSidebar(){const sidebar=document.getElementById('sidebar');setSidebar(!sidebar?.classList.contains('open'))}
function closeSidebar(){setSidebar(false)}
function openModal(id){document.getElementById(id)?.classList.add('open')}
function closeModal(id){document.getElementById(id)?.classList.remove('open')}
function openPoints(id,name){const f=document.getElementById('pointsForm');f.action=`/admin/students/${id}/points`;document.getElementById('pointsTitle').textContent=`Update points · ${name}`;openModal('pointsModal')}
function filterRows(q,id){q=q.toLowerCase();document.querySelectorAll(`#${id} tbody tr`).forEach(r=>r.style.display=r.textContent.toLowerCase().includes(q)?'':'none')}
document.addEventListener('click',e=>{if(e.target.classList.contains('modal'))e.target.classList.remove('open')});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){document.querySelectorAll('.modal.open').forEach(m=>m.classList.remove('open'));closeSidebar()}});
function openStudentEdit(id,name,cls,section){document.getElementById('studentEditForm').action=`/admin/students/${id}/edit`;document.getElementById('studentEditName').value=name;document.getElementById('studentEditClass').value=cls;document.getElementById('studentEditSection').value=section;openModal('editStudent')}
function openChallengeEdit(id,title,description,category,points,start,end,cls,section){document.getElementById('challengeEditForm').action=`/admin/challenges/${id}/edit`;document.getElementById('challengeEditTitle').value=title;document.getElementById('challengeEditDescription').value=description;document.getElementById('challengeEditCategory').value=category;document.getElementById('challengeEditPoints').value=points;document.getElementById('challengeEditStart').value=start;document.getElementById('challengeEditEnd').value=end;document.getElementById('challengeEditClass').value=cls;document.getElementById('challengeEditSection').value=section;openModal('challengeEditModal')}
function openStudentPhoto(id,name,path){document.getElementById('studentPhotoForm').action=`/admin/students/${id}/photo`;document.getElementById('studentPhotoRemoveForm').action=`/admin/students/${id}/photo/remove`;document.getElementById('studentPhotoTitle').textContent=`Profile picture · ${name}`;document.getElementById('studentPhotoRemoveButton').style.display=path?'inline-flex':'none';openModal('studentPhoto')}

document.querySelectorAll('#sidebar nav a').forEach(a=>a.addEventListener('click',()=>{if(window.innerWidth<=820)closeSidebar()}));
document.getElementById('sidebarOverlay')?.addEventListener('click',closeSidebar);
window.addEventListener('resize',()=>{if(window.innerWidth>820)closeSidebar()});

// Mobile gesture: swipe left on the open drawer to close it. An edge swipe right opens it.
let navTouchStartX=null,navTouchStartY=null,navTouchSource='';
document.addEventListener('touchstart',e=>{
  if(window.innerWidth>820 || e.touches.length!==1)return;
  const t=e.touches[0]; navTouchStartX=t.clientX; navTouchStartY=t.clientY;
  navTouchSource=e.target.closest('#sidebar')?'sidebar':(t.clientX<=24?'edge':'');
},{passive:true});
document.addEventListener('touchend',e=>{
  if(navTouchStartX===null || window.innerWidth>820 || !e.changedTouches.length)return;
  const t=e.changedTouches[0],dx=t.clientX-navTouchStartX,dy=t.clientY-navTouchStartY;
  if(Math.abs(dx)>55 && Math.abs(dx)>Math.abs(dy)*1.25){
    if(navTouchSource==='sidebar' && dx<0)closeSidebar();
    if(navTouchSource==='edge' && dx>0)setSidebar(true);
  }
  navTouchStartX=navTouchStartY=null; navTouchSource='';
},{passive:true});
