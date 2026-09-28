'use strict';
let csrf='';const message=document.querySelector('#admin-message');const login=document.querySelector('#admin-login');const dashboard=document.querySelector('#admin-dashboard');const records=document.querySelector('#records');
const labels={name:'称呼',contact:'联系方式',organization:'高校或机构',entry_type:'参与身份',team_size:'团队人数',project_stage:'项目进度',interest:'兴趣方向',project_summary:'项目简介',partner_type:'合作类型',scope:'合作范围',resources:'可提供资源',expectations:'参与意向'};
async function api(path,data){const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(data)}:{});const result=await response.json();if(!response.ok){if(response.status===401){dashboard.hidden=true;login.hidden=false;records.replaceChildren();}throw Error(result.error||'请求失败');}return result;}
function element(tag,text,cls){const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;}
async function load(){
 const result=await api('/api/admin/submissions?kind='+document.querySelector('#kind').value);records.replaceChildren();document.querySelector('#record-count').textContent=result.records.length+' 条登记';
 if(!result.records.length){records.append(element('p','暂时还没有这类登记。'));return;}
 for(const row of result.records){
  const article=element('article',null,'admin-record');const header=element('header');header.append(element('h3',row.data.name+' · '+(row.kind==='creator'?'参赛意向':'合作意向')),element('p',new Date(row.created_at).toLocaleString('zh-CN')));article.append(header,element('p',row.id,'admin-status'));
  const dl=element('dl');for(const [key,value] of Object.entries(row.data)){if(labels[key]&&value){dl.append(element('dt',labels[key]),element('dd',value));}}article.append(dl);
  const f=element('form',null,'admin-update');const status=element('select');status.setAttribute('aria-label',row.data.name+'的跟进状态');for(const val of ['未联系','沟通中','待跟进','已归档']){const o=element('option',val);o.value=val;o.selected=val===row.status;status.append(o);}
  const notes=element('textarea');notes.value=row.notes;notes.maxLength=2000;notes.rows=2;notes.placeholder='跟进备注';notes.setAttribute('aria-label',row.data.name+'的跟进备注');const save=element('button','保存跟进','button secondary');save.type='submit';const feedback=element('p',null,'admin-status');feedback.setAttribute('role','status');f.append(status,notes,save);article.append(f,feedback);
  f.addEventListener('submit',async e=>{e.preventDefault();save.disabled=true;try{await api('/api/admin/update',{id:row.id,status:status.value,notes:notes.value});feedback.textContent='已保存';}catch(err){feedback.textContent=err.message;}finally{save.disabled=false;}});records.append(article);
 }
}
login.addEventListener('submit',async e=>{e.preventDefault();const b=login.querySelector('button');b.disabled=true;try{const result=await api('/api/admin/login',{password:document.querySelector('#password').value});csrf=result.csrf;document.querySelector('#password').value='';await load();login.hidden=true;dashboard.hidden=false;message.textContent='';}catch(err){message.textContent=err.message;}finally{b.disabled=false;}});
document.querySelector('#kind').addEventListener('change',()=>load().catch(e=>message.textContent=e.message));
document.querySelector('#logout').addEventListener('click',async()=>{try{await api('/api/admin/logout',{});csrf='';records.replaceChildren();dashboard.hidden=true;login.hidden=false;message.textContent='已退出登录';}catch(e){message.textContent=e.message;}});
(async()=>{try{const session=await api('/api/admin/session');csrf=session.csrf;await load();login.hidden=true;dashboard.hidden=false;}catch(e){if(e.message!=='请先登录管理后台。')message.textContent=e.message;}})();
