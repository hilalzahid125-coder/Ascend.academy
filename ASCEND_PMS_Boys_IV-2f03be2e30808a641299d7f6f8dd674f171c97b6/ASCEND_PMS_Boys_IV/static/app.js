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
function openStudentEdit(id,name,cls,section,profile={}){document.getElementById('studentEditForm').action=`/admin/students/${id}/edit`;document.getElementById('studentEditName').value=name;const grade=document.getElementById('studentEditClass');if(cls && !Array.from(grade.options).some(o=>o.value===cls)){const opt=new Option(`${cls} (existing)`,cls);opt.dataset.legacy='1';grade.add(opt)}grade.value=cls;document.getElementById('studentEditSection').value=section;for(const [id,key] of [['studentEditGuardian','guardianName'],['studentEditPhone','phone'],['studentEditCountryCode','countryCode'],['studentEditEmail','email'],['studentEditCountry','country'],['studentEditSchool','schoolName']])document.getElementById(id).value=profile[key]||'';document.querySelectorAll('#studentEditForm input[name=subjects]').forEach(box=>box.checked=Array.isArray(profile.subjects)&&profile.subjects.includes(box.value));openModal('editStudent')}
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

// Keep the authenticated application shell in place for page navigation and
// form saves. HTML is always fetched fresh; private pages are never cached.
(function(){
  if(!document.querySelector('.app-shell')) return;
  const pages=new Set(['/student','/my-classes','/challenges','/leaderboards','/achievements','/rewards','/notifications','/profile',
    '/admin','/admin/my-classes','/admin/students','/admin/challenges','/admin/achievements','/admin/rewards','/admin/announcements',
    '/admin/activity','/admin/reports','/admin/admins','/admin/settings','/admin/launch','/admin/account','/about','/privacy']);
  let controller=null, serial=0, saving=false, pendingPop=null;
  function loading(on){
    let bar=document.querySelector('.nav-loading');
    if(on && !bar){bar=document.createElement('div');bar.className='nav-loading';bar.setAttribute('aria-hidden','true');document.body.append(bar)}
    if(!on) bar?.remove();
    const page=document.getElementById('main-content');
    if(page){if(on)page.setAttribute('aria-busy','true');else page.removeAttribute('aria-busy')}
  }
  function notice(message){
    const page=document.getElementById('main-content'); if(!page) return;
    let box=document.getElementById('navigationNotice');
    const container=document.querySelector('.modal.open .modal-card') || page;
    if(!box){box=document.createElement('div');box.id='navigationNotice';box.className='toast danger';box.setAttribute('role','alert');container.prepend(box)}
    else if(!container.contains(box))container.prepend(box);
    box.textContent=message;
  }
  function applyPage(html, url, mode){
    const doc=new DOMParser().parseFromString(html,'text/html');
    const next=doc.getElementById('main-content'), nextNav=doc.querySelector('#sidebar nav');
    const current=document.getElementById('main-content'), nav=document.querySelector('#sidebar nav');
    if(!next || !nextNav || !current || !nav) return false;
    current.replaceChildren(...next.childNodes); nav.innerHTML=nextNav.innerHTML;
    // Settings and profile photo changes can also alter the shared shell.
    const newTop=doc.querySelector('.topbar'), top=document.querySelector('.topbar');
    if(top && newTop) top.replaceWith(newTop);
    const newBrand=doc.querySelector('.school-chip'), brand=document.querySelector('.school-chip');
    if(brand && newBrand) brand.replaceWith(newBrand);
    document.title=doc.title;
    if(mode==='push') history.pushState({ascendNavigation:true},'',url);
    else if(mode==='replace') history.replaceState({ascendNavigation:true},'',url);
    closeSidebar(); window.scrollTo(0,0);
    current.setAttribute('tabindex','-1');current.focus({preventScroll:true});
    return true;
  }
  async function navigate(url, mode='push'){
    if(saving){notice('A change is still being saved. Please wait.');return}
    const sequence=++serial;
    if(controller) controller.abort(); controller=new AbortController();
    loading(true);
    try{
      const response=await fetch(url,{credentials:'same-origin',headers:{'X-Requested-With':'ASCEND-Navigation'},signal:controller.signal,cache:'no-store'});
      if(sequence!==serial)return;
      if(!response.ok || !response.headers.get('content-type')?.includes('text/html')) {location.assign(response.url||url);return}
      const html=await response.text(); if(sequence!==serial)return;
      const finalUrl=response.url||url;
      if(!applyPage(html,finalUrl,mode)) location.assign(finalUrl);
    }catch(err){if(err.name!=='AbortError') location.assign(url)}
    finally{if(sequence===serial)loading(false)}
  }
  document.addEventListener('click',event=>{
    const link=event.target.closest('.app-shell a');
    if(!link || event.defaultPrevented || event.button!==0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.hasAttribute('download') || link.target) return;
    const url=new URL(link.href,location.href);
    if(url.origin!==location.origin || url.hash || !pages.has(url.pathname)) return;
    event.preventDefault(); navigate(url.href);
  });
  document.addEventListener('submit',async event=>{
    const form=event.target;
    if(event.defaultPrevented || !(form instanceof HTMLFormElement) || !form.closest('#main-content') || form.target || form.hasAttribute('data-no-ajax')) return;
    const submitter=event.submitter;
    const method=(submitter?.getAttribute('formmethod') || form.method || 'get').toLowerCase();
    const url=new URL(submitter?.getAttribute('formaction') || form.action || location.href,location.href);
    if(url.origin!==location.origin || !['get','post'].includes(method))return;
    if(method==='get' && !pages.has(url.pathname))return;
    event.preventDefault();
    if(saving){notice('A change is still being saved. Please wait.');return}
    const data=new FormData(form);
    if(submitter && submitter.name) data.append(submitter.name,submitter.value);
    if(method==='get'){
      url.search=new URLSearchParams(Array.from(data,([key,value])=>[key,value instanceof File?value.name:value])).toString();
      navigate(url.href);return;
    }
    // Never automatically retry a POST: it might already have been committed.
    if(controller)controller.abort(); ++serial; saving=true; loading(true);
    const buttons=Array.from(form.querySelectorAll('button:not([type]),button[type=submit],input[type=submit]'));
    const disabled=buttons.map(button=>button.disabled);buttons.forEach(button=>button.disabled=true);
    try{
      const response=await fetch(url.href,{method:'POST',body:data,credentials:'same-origin',headers:{'X-Requested-With':'ASCEND-Navigation'},cache:'no-store'});
      const finalUrl=new URL(response.url||url.href,location.href);
      if(finalUrl.origin!==location.origin || finalUrl.pathname==='/login'){location.assign(finalUrl.href);return}
      if(!response.ok){notice(response.status===403?'Your session or security token may have expired. Refresh and sign in again if needed.':`The change could not be confirmed (HTTP ${response.status}). Check the form and try again.`);return}
      if(!response.headers.get('content-type')?.includes('text/html')){notice('The server responded unexpectedly. Check whether the change was saved before trying again.');return}
      const html=await response.text();
      // Non-redirect POST responses such as the bulk-import result are displayed
      // in place without putting a POST-only URL into browser history.
      const destination=response.redirected ? finalUrl.href : location.href;
      const mode=response.redirected && finalUrl.pathname!==location.pathname ? 'push' : 'replace';
      if(!applyPage(html,destination,mode))notice('The change may have been saved, but the page could not update. Refresh to check.');
    }catch(err){notice('The connection was interrupted. The change may or may not have saved; check before trying again.')}
    finally{
      buttons.forEach((button,i)=>button.disabled=disabled[i]);saving=false;loading(false);
      if(pendingPop){const url=pendingPop;pendingPop=null;navigate(url,'none')}
    }
  });
  window.addEventListener('popstate',()=>{if(saving) pendingPop=location.href;else navigate(location.href,'none')});
})();
