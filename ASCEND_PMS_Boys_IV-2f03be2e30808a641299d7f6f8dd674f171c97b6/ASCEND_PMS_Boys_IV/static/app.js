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
function openStudentEdit(id,name,cls,section,profile={}){document.getElementById('studentEditForm').action=`/admin/students/${id}/edit`;document.getElementById('studentEditName').value=name;const grade=document.getElementById('studentEditClass');if(cls && !Array.from(grade.options).some(o=>o.value===cls)){const opt=new Option(`${cls} (existing)`,cls);opt.dataset.legacy='1';grade.add(opt)}grade.value=cls;document.getElementById('studentEditSection').value=section;for(const [id,key] of [['studentEditGuardian','guardianName'],['studentEditPhone','phone'],['studentEditCountryCode','countryCode'],['studentEditEmail','email'],['studentEditCountry','country'],['studentEditSchool','schoolName']])document.getElementById(id).value=profile[key]||'';openModal('editStudent')}
function openChallengeEdit(id,title,description,category,points,start,end,cls,section){document.getElementById('challengeEditForm').action=`/admin/challenges/${id}/edit`;document.getElementById('challengeEditTitle').value=title;document.getElementById('challengeEditDescription').value=description;document.getElementById('challengeEditCategory').value=category;document.getElementById('challengeEditPoints').value=points;document.getElementById('challengeEditStart').value=start;document.getElementById('challengeEditEnd').value=end;const grade=document.getElementById('challengeEditClass');if(cls && !Array.from(grade.options).some(o=>o.value===cls)){grade.add(new Option(`${cls} (existing)`,cls))}grade.value=cls;document.getElementById('challengeEditSection').value=section;openModal('challengeEditModal')}
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

function openAdminPassword(id,name){document.getElementById('adminPasswordForm').action='/admin/admins/'+id+'/password';document.getElementById('adminPasswordTitle').textContent='Reset password · '+name;openModal('adminPassword')}

// Sidebar GET navigation keeps the shared shell in place. Forms and downloads
// retain ordinary browser navigation, and no private page is cached.
(function(){
  if(!document.querySelector('.app-shell')) return;
  let controller=null, serial=0;
  async function navigate(url, push){
    const sequence=++serial;
    if(controller) controller.abort();
    controller=new AbortController();
    let indicator=document.querySelector('.nav-loading');
    if(!indicator){indicator=document.createElement('div');indicator.className='nav-loading';indicator.setAttribute('aria-hidden','true');document.body.append(indicator)}
    const current=document.getElementById('main-content');
    current?.setAttribute('aria-busy','true');
    try{
      const response=await fetch(url,{credentials:'same-origin',headers:{'X-Requested-With':'ASCEND-Navigation'},signal:controller.signal,cache:'no-store'});
      if(!response.ok || response.redirected || !response.headers.get('content-type')?.includes('text/html')) {location.assign(response.url||url);return}
      const doc=new DOMParser().parseFromString(await response.text(),'text/html');
      const next=doc.getElementById('main-content'), nextNav=doc.querySelector('#sidebar nav');
      if(!next || !nextNav || !current || sequence!==serial) {if(sequence===serial)location.assign(url);return}
      current.replaceChildren(...next.childNodes);
      const nav=document.querySelector('#sidebar nav');
      if(nav) nav.innerHTML=nextNav.innerHTML;
      document.title=doc.title;
      if(push) history.pushState({ascendNavigation:true},'',url);
      closeSidebar();
      window.scrollTo(0,0);
      current.setAttribute('tabindex','-1');current.focus({preventScroll:true});
    }catch(err){if(err.name!=='AbortError') location.assign(url)}
    finally{if(sequence===serial){indicator.remove();current?.removeAttribute('aria-busy')}}
  }
  document.addEventListener('click',event=>{
    const link=event.target.closest('#sidebar nav a');
    if(!link || event.defaultPrevented || event.button!==0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.hasAttribute('download') || link.target) return;
    const url=new URL(link.href,location.href);
    if(url.origin!==location.origin || url.hash) return;
    event.preventDefault();navigate(url.href,true);
  });
  window.addEventListener('popstate',()=>navigate(location.href,false));
})();
