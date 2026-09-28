import importlib.util,tempfile,threading,json,uuid,urllib.request,urllib.error
from pathlib import Path
spec=importlib.util.spec_from_file_location('site_server',Path.cwd()/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
 s=m.Server(('127.0.0.1',0),Path(tmp));threading.Thread(target=s.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{s.server_port}'
 def req(path,data=None,cookie='',csrf='',origin=None):
  headers={'Origin':origin or base,'Content-Type':'application/json','Cookie':cookie,'X-CSRF-Token':csrf}
  r=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
  try:r=urllib.request.urlopen(r)
  except urllib.error.HTTPError as e:r=e
  return r.status,json.loads(r.read()),r.headers
 d={'kind':'creator','request_id':str(uuid.uuid4()),'consent':True,'name':'QA TEST','contact':'qa@example.invalid','entry_type':'个人'}
 code,result,_=req('/api/submissions',d);assert code==201;ref=result['reference']
 assert req('/api/submissions',d)[1]['reference']==ref
 assert req('/api/submissions',{**d,'name':'changed'})[0]==409
 assert req('/api/submissions',{**d,'consent':False})[0]==400
 assert req('/api/submissions',d,origin='https://other.invalid')[0]==403
 assert req('/api/admin/submissions')[0]==401
 assert req('/private/admin-password.txt')[0]==404
 assert req('/api/admin/login',{'password':'wrong'})[0]==401
 code,auth,h=req('/api/admin/login',{'password':(Path(tmp)/'admin-password.txt').read_text().strip()});assert code==200
 cookie=h['Set-Cookie'].split(';')[0];csrf=auth['csrf']
 assert len(req('/api/admin/submissions',cookie=cookie)[1]['records'])==1
 update={'id':ref,'status':'待跟进','notes':'QA follow up'}
 assert req('/api/admin/update',update,cookie)[0]==403
 assert req('/api/admin/update',update,cookie,csrf)[0]==200
 partner={'kind':'partner','request_id':str(uuid.uuid4()),'consent':True,'name':'QA PARTNER','contact':'qa@example.invalid','organization':'QA','partner_type':'技术与导师','scope':'上海首季合作'}
 assert req('/api/submissions',partner)[0]==201
 assert len(req('/api/admin/submissions?kind=partner',cookie=cookie)[1]['records'])==1
 s.shutdown();s.server_close()
 store=m.Store(Path(tmp)/'intake.sqlite3')
 with store.connect() as c:
  assert c.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]==2
  assert c.execute('SELECT notes FROM submissions WHERE id=?',(ref,)).fetchone()[0]=='QA follow up'
 print('PASS: submission, validation, idempotency, origin, private-file protection, authentication, CSRF, filters, updates, durable storage; temporary test data removed')
