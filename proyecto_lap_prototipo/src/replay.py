"""Resultados reproducibles: video original y observaciones por tiempo de contenido."""
import json,re,mimetypes
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import parse_qs

class ReplayWriter:
 def __init__(self,root,sid,module,cameras,config,project_id=None):
  self.directory=root/'data'/'replays'/sid
  self.directory.mkdir(parents=True,exist_ok=True)
  self.meta={'session':sid,'module':module,'created':datetime.now(timezone.utc).isoformat(),'status':'running','cameras':cameras,'config':config,'end':0,'projectId':project_id}
  self.path=self.directory/'manifest.json'
  self.save()
  self.output=(self.directory/'samples.jsonl').open('w',encoding='utf-8')
 def save(self):
  tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.meta,ensure_ascii=False),encoding='utf-8');tmp.replace(self.path)
 def append(self,sample):
  self.output.write(json.dumps(sample,ensure_ascii=False,allow_nan=False)+'\n');self.output.flush();self.meta['end']=sample['t']
 def finish(self,status):
  self.output.close();self.meta['status']=status;self.save()

def directory(root,sid):
 if not re.fullmatch(r'[a-f0-9]{8,32}',sid):raise ValueError('Sesión inválida.')
 return root/'data'/'replays'/sid

def manifest(root,sid):
 return json.loads((directory(root,sid)/'manifest.json').read_text(encoding='utf-8'))

def public(meta):
 return {**meta,'cameras':[{**{k:v for k,v in c.items() if k!='source'},'sourceKind':'recording' if isinstance(c.get('source'),str) and '://' not in c['source'] else 'live'} for c in meta['cameras']], 'config':{k:v for k,v in meta.get('config',{}).items() if k not in ('cameras','source')}}

def recover_interrupted(root):
 """Se llama una vez al arrancar el servidor, nunca durante una sesión activa."""
 for path in (root/'data'/'replays').glob('*/manifest.json'):
  try:
   meta=json.loads(path.read_text(encoding='utf-8'))
   if meta.get('status')!='running':continue
   meta['status']='error'
   for line in (path.parent/'samples.jsonl').read_text(encoding='utf-8').splitlines():
    try:meta['end']=json.loads(line)['t']
    except (ValueError,KeyError):break
   tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
  except (OSError,ValueError):continue

def get(handler,url,root):
 q=parse_qs(url.query);sid=q.get('session',[''])[0]
 try:
  if url.path.endswith('/history'):
   # Cada proyecto ve solo sus propias sesiones: son espacios distintos y
   # mezclarlas haria parecer que un terminal tiene grabaciones de otro.
   activo=getattr(handler.server.engine,'project_id',None)
   rows=[]
   for p in (root/'data'/'replays').glob('*/manifest.json'):
    try:meta=json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError):continue
    if activo and meta.get('projectId') not in (activo,None):continue
    rows.append(public(meta))
   return handler.send_data(200,sorted(rows,key=lambda r:r['created'],reverse=True)[:50])
  meta=manifest(root,sid)
  if url.path.endswith('/data'):
   samples=[]
   for line in (directory(root,sid)/'samples.jsonl').read_text(encoding='utf-8').splitlines():
    try:samples.append(json.loads(line))
    except ValueError:break
   if q.get('projection') == ['current']:
    import copy
    from replay_projection import current_projection
    with handler.server.engine.lock:
     current = copy.deepcopy(handler.server.engine.config)
    samples = current_projection(meta, samples, current)
   return handler.send_data(200,{**public(meta),'samples':samples})
  if url.path.endswith('/video'):
   camera=next((c for c in meta['cameras'] if c['id']==q.get('camera',[''])[0]),None)
   if not camera:raise ValueError('Cámara no incluida en esta grabación.')
   source=camera['source']
   if not isinstance(source,str) or '://' in source:raise ValueError('Esta fuente en vivo no tiene video archivado.')
   path=(root/source).resolve()
   if not path.is_file():raise ValueError('El video original fue movido o eliminado. Restáuralo para reproducirlo.')
   size=path.stat().st_size;start=0;end=size-1;status=200
   header=handler.headers.get('Range')
   if header:
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
    if not match or not any(match.groups()):return handler.send_data(416,{'error':'Rango inválido.'})
    a,b=match.groups()
    if a:start=int(a);end=min(int(b),end) if b else end
    else:start=max(0,size-int(b))
    if start>end or start>=size:return handler.send_data(416,{'error':'Rango fuera del archivo.'})
    status=206
   handler.send_response(status);handler.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'video/mp4');handler.send_header('Accept-Ranges','bytes');handler.send_header('Content-Length',str(end-start+1));handler.send_header('Cache-Control','private, no-store')
   if status==206:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   handler.end_headers()
   try:
    with path.open('rb') as f:
     f.seek(start);remaining=end-start+1
     while remaining:
      chunk=f.read(min(1024*256,remaining))
      if not chunk:break
      handler.wfile.write(chunk);remaining-=len(chunk)
   except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
   return
  return handler.send_data(404,{'error':'Ruta desconocida.'})
 except (ValueError,OSError) as exc:return handler.send_data(400,{'error':str(exc)})
