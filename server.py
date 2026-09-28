"""Local A'IDOL preview and durable intake backend. Standard library only."""
import argparse, csv, hashlib, io, json, mimetypes, os, secrets, sqlite3, threading, time, uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
ROOT=Path(__file__).resolve().parent
STATUSES={'未联系','沟通中','待跟进','已归档'}
COMMON={'name':200,'contact':150,'organization':200}
CREATOR={**COMMON,'entry_type':30,'team_size':3,'project_stage':50,'interest':200,'project_summary':2000}
PARTNER={**COMMON,'partner_type':50,'scope':50,'resources':2000,'expectations':2000}
LABELS={'name':'称呼','contact':'联系方式','organization':'高校或机构','entry_type':'参与身份','team_size':'团队人数','project_stage':'项目进度','interest':'兴趣方向','project_summary':'项目简介','partner_type':'合作类型','scope':'合作范围','resources':'可提供资源','expectations':'参与意向'}
PUBLIC={'/team.html':'team.html','/':'index.html','/index.html':'index.html','/season-01.html':'season-01.html','/join.html':'join.html','/partner.html':'partner.html','/admin.html':'admin.html','/style.css':'style.css','/app.js':'app.js','/admin.js':'admin.js'}
PUBLIC.update({'/zh/':'zh/index.html', **{'/zh/'+name:'zh/'+name for name in ('index.html','join.html','partner.html','team.html','season-01.html')}})
ASSETS={'aidol-rounded-logo.png','peinan-li-smile.png','hero.png','aidol-wordmark.png','aidol-hackathon-variety-poster.png','founder-photo.jpg','founder-02-studio.png'}
def now():return datetime.now(timezone.utc).isoformat()
class Store:
 def __init__(self,path):
  self.path=path;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  with self.connect() as c:c.execute('CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT \'\', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
  os.chmod(path,0o600)
 def connect(self):
  c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;return c
class Server(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,addr,data_dir):
  super().__init__(addr,Handler);self.store=Store(data_dir/'intake.sqlite3');self.lock=threading.Lock();self.sessions={};self.limits=defaultdict(deque)
  key=data_dir/'admin-password.txt'
  if not key.exists():
   fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(24)+'\n')
  os.chmod(key,0o600);self.password_hash=hashlib.sha256(key.read_text().strip().encode()).digest()
 def limited(self,ip,action,limit,seconds):
  with self.lock:
   q=self.limits[(ip,action)];t=time.time()
   while q and q[0]<t-seconds:q.popleft()
   if len(q)>=limit:return True
   q.append(t);return False
class Handler(BaseHTTPRequestHandler):
 server_version='AIDOL'
 def log_message(self,fmt,*args):pass # Do not log submitted PII or credentials.
 def headers_common(self):
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','same-origin');self.send_header('X-Frame-Options','DENY');self.send_header('Cache-Control','no-store')
  self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
 def send(self,status,obj,extra=None):
  raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.headers_common();self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)))
  for k,v in (extra or {}).items():self.send_header(k,v)
  self.end_headers();self.wfile.write(raw)
 def valid_host(self):
  # Loopback-only preview: reject DNS rebinding and unexpected Host headers.
  return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
 def same_origin(self):
  return self.valid_host() and self.headers.get('Origin')=='http://'+self.headers.get('Host','') and self.headers.get('Content-Type','').split(';')[0]=='application/json'
 def body(self):
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ValueError('请求格式错误。')
  if n<=0 or n>20000:raise ValueError('提交内容过大或为空。')
  try:d=json.loads(self.rfile.read(n))
  except (ValueError,UnicodeError):raise ValueError('请求格式错误。')
  if not isinstance(d,dict):raise ValueError('请求格式错误。')
  return d
 def session(self):
  try:
   cookie=SimpleCookie(self.headers.get('Cookie',''));value=cookie['aidol_admin'].value
  except (KeyError,ValueError):return None
  key=hashlib.sha256(value.encode()).hexdigest()
  with self.server.lock:
   row=self.server.sessions.get(key)
   if row and row['expires']>time.time():return key,row
   self.server.sessions.pop(key,None)
  return None
 def do_GET(self):
  if not self.valid_host():return self.send(403,{'error':'访问来源无效。'})
  path=urlparse(self.path).path
  if path=='/api/health':return self.send(200,{'status':'ok','storage':'sqlite'})
  if path.startswith('/api/admin/'):
   session=self.session()
   if not session:return self.send(401,{'error':'请先登录管理后台。'})
   if path=='/api/admin/session':return self.send(200,{'csrf':session[1]['csrf']})
   if path=='/api/admin/submissions':
    kind=parse_qs(urlparse(self.path).query).get('kind',['all'])[0]
    if kind not in {'all','creator','partner'}:return self.send(400,{'error':'筛选条件无效。'})
    with self.server.store.connect() as c:
     rows=c.execute('SELECT * FROM submissions'+(' WHERE kind=?' if kind!='all' else '')+' ORDER BY created_at DESC',(kind,) if kind!='all' else ()).fetchall()
    return self.send(200,{'records':[{**{k:r[k] for k in ['id','kind','status','notes','created_at','updated_at']},'data':json.loads(r['payload'])} for r in rows]})
   return self.send(404,{'error':'未找到接口。'})
  filename=PUBLIC.get(path)
  if path.startswith('/assets/') and path[8:] in ASSETS:filename='assets/'+path[8:]
  if not filename:return self.send(404,{'error':'页面不存在。'})
  try:raw=(ROOT/filename).read_bytes()
  except FileNotFoundError:return self.send(404,{'error':'页面不存在。'})
  self.send_response(200);self.headers_common();self.send_header('Content-Type',(mimetypes.guess_type(filename)[0] or 'application/octet-stream')+('; charset=utf-8' if filename.endswith(('.html','.css','.js')) else ''));self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  if not self.same_origin():return self.send(403,{'error':'请从本站页面提交。'})
  path=urlparse(self.path).path
  try:d=self.body()
  except ValueError as e:return self.send(400,{'error':str(e)})
  if path=='/api/admin/login':
   if self.server.limited(self.client_address[0],'login',10,300):return self.send(429,{'error':'尝试次数较多，请 5 分钟后重试。'})
   password=d.get('password','')
   if not isinstance(password,str) or not secrets.compare_digest(hashlib.sha256(password.encode()).digest(),self.server.password_hash):return self.send(401,{'error':'管理口令不正确。'})
   token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
   with self.server.lock:
    self.server.sessions={k:v for k,v in self.server.sessions.items() if v['expires']>time.time()}
    self.server.sessions[hashlib.sha256(token.encode()).hexdigest()]={'expires':time.time()+8*3600,'csrf':csrf}
   return self.send(200,{'csrf':csrf},{'Set-Cookie':f'aidol_admin={token}; Path=/api/admin; HttpOnly; SameSite=Strict; Max-Age=28800'})
  if path.startswith('/api/admin/'):
   session=self.session()
   if not session:return self.send(401,{'error':'请先登录管理后台。'})
   if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),session[1]['csrf']):return self.send(403,{'error':'会话校验失败，请重新登录。'})
   if path=='/api/admin/logout':
    with self.server.lock:self.server.sessions.pop(session[0],None)
    return self.send(200,{'ok':True},{'Set-Cookie':'aidol_admin=; Path=/api/admin; HttpOnly; SameSite=Strict; Max-Age=0'})
   if path=='/api/admin/update':
    if d.get('status') not in STATUSES or not isinstance(d.get('notes',''),str) or len(d.get('notes',''))>2000 or not isinstance(d.get('id'),str):return self.send(400,{'error':'跟进信息格式不正确。'})
    with self.server.store.connect() as c:
     cur=c.execute('UPDATE submissions SET status=?,notes=?,updated_at=? WHERE id=?',(d['status'],d.get('notes',''),now(),d['id']))
    return self.send(200 if cur.rowcount else 404,{'ok':True} if cur.rowcount else {'error':'记录不存在。'})
   return self.send(404,{'error':'未找到接口。'})
  if path!='/api/submissions':return self.send(404,{'error':'未找到接口。'})
  if self.server.limited(self.client_address[0],'submit',20,3600):return self.send(429,{'error':'提交较频繁，请稍后再试。'})
  if d.get('website'):return self.send(400,{'error':'提交未通过校验。'})
  try:
   kind=d.get('kind');fields=CREATOR if kind=='creator' else PARTNER if kind=='partner' else None
   if not fields or d.get('consent') is not True:raise ValueError('请选择登记类型并同意联系授权。')
   request_id=str(uuid.UUID(d.get('request_id','')))
   values={}
   for key,maxlen in fields.items():
    v=d.get(key,'')
    if not isinstance(v,str) or len(v)>maxlen:raise ValueError('部分字段格式不正确或超出长度，请检查。')
    values[key]=v.strip()
   if any(not values[k] for k in ['name','contact']):raise ValueError('请填写称呼和联系方式。')
   if len(values['contact'])<3:raise ValueError('请填写可用于联系的邮箱、手机号或微信号。')
   if kind=='creator':
    if values['entry_type'] not in {'个人','已有团队'}:raise ValueError('请选择参与身份。')
    if values['team_size'] and (not values['team_size'].isdigit() or not 1<=int(values['team_size'])<=100):raise ValueError('团队人数须为 1–100 的整数。')
    if values['project_stage'] not in {'','尚未确定','想法阶段','已有原型','可演示作品'}:raise ValueError('请选择项目进度。')
   else:
    if not values['organization']:raise ValueError('请填写机构名称。')
    if values['partner_type'] not in {'高校与实验室','品牌与赞助','场地与活动支持','硬件与设备','技术与导师','内容与传播','企业人才与场景','产业与投资','其他合作'}:raise ValueError('请选择合作类型。')
    if values['scope'] not in {'上海首季合作','长期品牌合作','两者均有意向','希望进一步交流'}:raise ValueError('请选择合作范围。')
   values['consent_version']='2026-09-28-v2'
  except (ValueError,TypeError,AttributeError) as e:return self.send(400,{'error':str(e) if isinstance(e,ValueError) and str(e) not in {'badly formed hexadecimal UUID string'} else '提交格式不正确，请刷新后重试。'})
  reference='AI-'+uuid.uuid4().hex[:12].upper();timestamp=now();payload=json.dumps(values,ensure_ascii=False,sort_keys=True)
  with self.server.store.connect() as c:
   c.execute('INSERT OR IGNORE INTO submissions(id,request_id,kind,payload,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(reference,request_id,kind,payload,'未联系',timestamp,timestamp))
   row=c.execute('SELECT id,kind,payload FROM submissions WHERE request_id=?',(request_id,)).fetchone()
  if row['kind']!=kind or row['payload']!=payload:return self.send(409,{'error':'该次登记内容已保存。如需修改，请在后续联系中提出。'})
  return self.send(201,{'reference':row['id']})
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8768);parser.add_argument('--data-dir',type=Path,default=ROOT/'private');args=parser.parse_args()
 server=Server(('127.0.0.1',args.port),args.data_dir.resolve())
 print(f'AIDOL ready at http://127.0.0.1:{args.port}/',flush=True)
 print(f'Admin: /admin.html | local password file: {args.data_dir.resolve()/"admin-password.txt"}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
