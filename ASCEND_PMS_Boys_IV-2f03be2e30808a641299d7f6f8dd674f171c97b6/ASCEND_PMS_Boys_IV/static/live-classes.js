/* The external video service is loaded only after an explicit Start or Join. */
(function(){
  let current=null, pending=null, pollTimer=null;
  const inClass=()=>Boolean(current || pending);
  function workspace(){return document.getElementById('liveClassWorkspace')}
  function resetLayout(){
    document.body.classList.remove('classroom-expanded','live-fullscreen-active');
    const w=workspace(); if(!w)return;
    w.classList.remove('is-fullscreen');
    const expand=w.querySelector('[data-live-action="expand"]'), full=w.querySelector('[data-live-action="fullscreen"]');
    if(expand){expand.setAttribute('aria-pressed','false');expand.textContent='Expand layout'}
    if(full){full.setAttribute('aria-pressed','false');full.textContent='Full screen'}
  }
  function close(){
    if(pending){pending.abort();pending=null}
    if(pollTimer){clearInterval(pollTimer);pollTimer=null}
    current=null;resetLayout();
    const w=workspace();if(w){w.hidden=true;w.querySelector('#liveVideoFrame')?.replaceChildren()}
  }
  function confirmLeave(){
    if(!inClass())return true;
    if(!window.confirm('Leave the live classroom? You can rejoin while the session is active.'))return false;
    close();return true;
  }
  function classAlert(text){
    const page=document.getElementById('main-content');if(!page)return;
    const alert=document.createElement('div');alert.className='toast danger';alert.setAttribute('role','alert');alert.textContent=text;page.prepend(alert);
  }
  async function verifySession(id){
    try{
      const response=await fetch(`/my-classes/live/${id}/status`,{credentials:'same-origin',cache:'no-store'});
      if(!current || current.id!==id)return;
      if(response.status===403 || response.status===404 || response.redirected || !response.headers.get('content-type')?.includes('application/json')){
        close();classAlert('This class has ended or your access has expired.');return;
      }
      if(!response.ok)throw Error('status unavailable');
      const state=workspace()?.querySelector('#liveClassState');if(state)state.textContent='Classroom open';
    }catch(e){
      if(current && current.id===id){const state=workspace()?.querySelector('#liveClassState');if(state)state.textContent='Connection interrupted. The class may still be active.'}
    }
  }
  async function open(id){
    id=Number(id);if(!Number.isSafeInteger(id) || id<1)return;
    if(current && current.id===id){workspace()?.scrollIntoView({behavior:'smooth',block:'start'});return}
    if(inClass() && !confirmLeave())return;
    const w=workspace(), csrf=w?.querySelector('#liveClassCsrf')?.value;
    if(!w || !csrf){classAlert('Could not open the classroom. Refresh and try again.');return}
    w.hidden=false;w.querySelector('#liveClassState').textContent='Connecting to the classroom…';
    w.scrollIntoView({behavior:'smooth',block:'start'});
    const abort=new AbortController();pending=abort;
    try{
      const body=new FormData();body.append('csrf_token',csrf);
      const response=await fetch(`/my-classes/live/${id}/room`,{method:'POST',body,credentials:'same-origin',cache:'no-store',signal:abort.signal});
      if(!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json'))throw Error('unavailable');
      const data=await response.json();
      if(pending!==abort)return;
      if(!/^DeltaAcademy[a-f0-9]{48}$/.test(data.room))throw Error('invalid room');
      const config=[
        'config.prejoinPageEnabled=false','config.prejoinConfig.enabled=false',
        'interfaceConfig.SHOW_JITSI_WATERMARK=false','interfaceConfig.SHOW_BRAND_WATERMARK=false',
        'interfaceConfig.JITSI_WATERMARK_LINK=','interfaceConfig.DEFAULT_BACKGROUND=%27%231a1a1a%27',
        'config.disableDeepLinking=true'
      ];
      if(data.student)config.push('config.startWithAudioMuted=true','config.startWithVideoMuted=true');
      const iframe=document.createElement('iframe');
      iframe.title=`Live class: ${data.subject}`;iframe.allow='camera; microphone; fullscreen; display-capture; autoplay';
      iframe.setAttribute('allowfullscreen','');iframe.referrerPolicy='no-referrer';iframe.loading='lazy';
      iframe.src=`https://meet.jit.si/${data.room}#${config.join('&')}`;
      w.querySelector('#liveClassTitle').textContent=`${data.subject} · Live classroom`;
      w.querySelector('#liveVideoFrame').replaceChildren(iframe);
      w.querySelector('#liveClassState').textContent='Classroom open';
      current={id};pending=null;pollTimer=setInterval(()=>verifySession(id),30000);
    }catch(err){
      if(err.name==='AbortError')return;
      if(pending===abort){pending=null;w.hidden=true;classAlert('Could not open this live class. Check that it is still active and try again.')}
    }
  }
  document.addEventListener('click',event=>{
    const join=event.target.closest('[data-live-join]');
    if(join){event.preventDefault();open(join.dataset.liveJoin);return}
    const button=event.target.closest('[data-live-action]');if(!button)return;
    const w=workspace();if(!w)return;
    if(button.dataset.liveAction==='leave'){if(window.confirm('Leave this classroom? The class will remain live for others.'))close()}
    if(button.dataset.liveAction==='fullscreen'){
      const enabled=w.classList.toggle('is-fullscreen');document.body.classList.toggle('live-fullscreen-active',enabled);
      button.setAttribute('aria-pressed',String(enabled));button.textContent=enabled?'Exit full screen':'Full screen';
    }
    if(button.dataset.liveAction==='expand'){
      const enabled=document.body.classList.toggle('classroom-expanded');
      button.setAttribute('aria-pressed',String(enabled));button.textContent=enabled?'Restore layout':'Expand layout';
    }
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape' && workspace()?.classList.contains('is-fullscreen'))workspace().querySelector('[data-live-action="fullscreen"]').click();
  });
  window.addEventListener('beforeunload',event=>{if(inClass()){event.preventDefault();event.returnValue=''}});
  window.LiveClass={open,close,inClass,confirmLeave};
})();
