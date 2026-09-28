'use strict';
const menu = document.querySelector('.menu-button');
const nav = document.querySelector('#navigation');
function closeMenu(){if(!menu||!nav)return;menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','打开导航');menu.querySelector('span').textContent='＋';nav.classList.remove('open');}
if(menu&&nav){menu.addEventListener('click',()=>{const opened=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(opened));menu.setAttribute('aria-label',opened?'关闭导航':'打开导航');menu.querySelector('span').textContent=opened?'−':'＋';nav.classList.toggle('open',opened);});nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',closeMenu));document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu();});}
const form=document.querySelector('.intake-form');
if(form){
 const kind=form.dataset.formKind;
 let requestId=crypto.randomUUID();
 const feedback=form.querySelector('.form-feedback');
 const teamSize=form.querySelector('[name="team_size"]');
 if(teamSize){teamSize.min='1';teamSize.max='100';teamSize.step='1';}
 const scope=form.querySelector('[name="scope"]');
 if(scope&&new URLSearchParams(location.search).get('scope')==='season')scope.value='上海首季合作';
 form.addEventListener('submit',async event=>{
  event.preventDefault();
  if(!form.reportValidity())return;
  const button=form.querySelector('[type="submit"]');
  if(button.disabled)return;
  const data=Object.fromEntries(new FormData(form));
  data.kind=kind;data.consent=form.querySelector('[name="consent"]').checked;data.request_id=requestId;
  feedback.textContent='正在保存，请稍候…';button.disabled=true;
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),15000);
  try{
   const response=await fetch('/api/submissions',{method:'POST',headers:{'Content-Type':'application/json','X-AIDOL-Request':'intake'},body:JSON.stringify(data),signal:controller.signal});
   const result=await response.json().catch(()=>({error:'服务暂时无法使用，请稍后重试。'}));
   if(!response.ok)throw new Error(result.error||'提交失败，请稍后重试。');
   form.hidden=true;document.querySelector('.form-heading').hidden=true;
   const success=document.querySelector('.success-panel');success.hidden=false;success.querySelector('.submission-reference').textContent='登记编号：'+result.reference;success.focus();
  }catch(error){feedback.textContent=error.name==='AbortError'?'暂未收到保存结果。请保留当前页面并重试，同一次登记不会重复保存。':(error instanceof TypeError?'暂时无法连接服务，请保留填写内容，稍后重试。':error.message);}
  finally{clearTimeout(timeout);button.disabled=false;}
 });
}
