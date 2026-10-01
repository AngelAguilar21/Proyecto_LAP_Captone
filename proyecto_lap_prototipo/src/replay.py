"""Resultados reproducibles: video original y observaciones por tiempo de contenido."""
import json,re,mimetypes,math,hashlib,copy
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import parse_qs
from contextlib import nullcontext
from resource_control import CURRENT, hold_path

class ReplayWriter:
 def __init__(self,root,sid,module,cameras,config,project_id=None):
  self.directory=root/'data'/'replays'/sid
  registry=CURRENT.get()
  self.lease=registry.use(self.directory,write=True) if registry else nullcontext()
  self.lease.__enter__()
  try:
   self.directory.mkdir(parents=True,exist_ok=True)
   self.meta={'session':sid,'module':module,'created':datetime.now(timezone.utc).isoformat(),'status':'running','cameras':cameras,'config':config,'end':0,'projectId':project_id,'evidenceVersion':1,'completion':None}
   self.path=self.directory/'manifest.json'
   self.save()
   self.output=(self.directory/'samples.jsonl').open('wb')
   self.digest=hashlib.sha256();self.sample_count=0;self.byte_count=0;self.last_t=None
  except BaseException:
   self.lease.__exit__(None,None,None)
   raise
 def save(self):
  tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.meta,ensure_ascii=False),encoding='utf-8');tmp.replace(self.path)
 def append(self,sample):
  data=(json.dumps(sample,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
  self.output.write(data);self.output.flush()
  self.digest.update(data);self.sample_count+=1;self.byte_count+=len(data);self.last_t=sample['t'];self.meta['end']=sample['t']
 def finish(self,status):
  try:
   self.output.close();self.meta['status']=status
   # Derived while writing, never reconstructed from a possibly truncated file.
   self.meta['completion']={'version':1,'samples':self.sample_count,'bytes':self.byte_count,
                            'sha256':self.digest.hexdigest(),'lastT':self.last_t,
                            'end':self.meta['end'],'status':status}
   self.save()
  finally:
   self.lease.__exit__(None,None,None)

def directory(root,sid):
 if not re.fullmatch(r'[a-f0-9]{8,32}',sid):raise ValueError('Sesión inválida.')
 return root/'data'/'replays'/sid

def manifest(root,sid):
 return json.loads((directory(root,sid)/'manifest.json').read_text(encoding='utf-8'))

def camera_snapshot(cameras):
 """Engine's replay identity/calibration contract, excluding live credentials."""
 result=[]
 for camera in cameras:
  live=camera.get('stream') or (isinstance(camera.get('source'),str) and '://' in camera['source'])
  result.append({**{key:copy.deepcopy(camera[key]) for key in
                   ('id','name','offset','planId','countLines','pairs','detectionZone') if key in camera},
                 'source':'' if live else camera.get('source'), 'sourceKind':'live' if live else 'recording'})
 return result

def public(meta):
 return {**meta,'cameras':[{**{k:v for k,v in c.items() if k!='source'},'sourceKind':c.get('sourceKind') or ('recording' if isinstance(c.get('source'),str) and '://' not in c['source'] else 'live')} for c in meta['cameras']], 'config':{k:v for k,v in meta.get('config',{}).items() if k not in ('cameras','source')}}

def validate_manifest(meta, sid=None):
 """Validate stored structure without inventing values or rewriting history."""
 if not isinstance(meta,dict):raise ValueError('El manifiesto no es un objeto.')
 if not isinstance(meta.get('session'),str) or not re.fullmatch(r'[a-f0-9]{8,32}',meta['session']):
  raise ValueError('Identidad de sesión inválida.')
 if sid is not None and meta['session']!=sid:raise ValueError('Identidad de sesión incoherente.')
 if not isinstance(meta.get('created'),str):raise ValueError('Fecha de sesión ausente o inválida.')
 try:datetime.fromisoformat(meta['created'])
 except ValueError:raise ValueError('Fecha de sesión inválida.') from None
 if not isinstance(meta.get('config'),dict) or not isinstance(meta.get('cameras'),list) or any(not isinstance(c,dict) for c in meta['cameras']):
  raise ValueError('Configuración histórica inválida.')
 if type(meta.get('end')) not in (int,float) or not math.isfinite(meta['end']) or meta['end']<0:
  raise ValueError('Final de sesión ausente o inválido.')
 if not isinstance(meta.get('module'),str) or not isinstance(meta.get('status'),str):
  raise ValueError('Estado de sesión inválido.')
 for key in ('cameraAnalytics','levelAnalytics'):
  values=meta.get(key,{})
  if not isinstance(values,dict) or any(not isinstance(v,dict) for v in values.values()):
   raise ValueError('Analítica histórica inválida.')
 analytics=[meta.get('reportAnalytics',{})]+list(meta.get('levelAnalytics',{}).values())
 for value in analytics:
  if not isinstance(value,dict) or not isinstance(value.get('zones',[]),list) or any(not isinstance(z,dict) for z in value.get('zones',[])):
   raise ValueError('Zonas históricas inválidas.')
 for value in meta.get('cameraAnalytics',{}).values():
  if not isinstance(value.get('occupancy',{}),dict):raise ValueError('Ocupación histórica inválida.')
 if not isinstance(meta['config'].get('planId','custom'),str):raise ValueError('Plano histórico inválido.')
 return meta


def recover_interrupted(root, on_error=None):
 """Se llama una vez al arrancar el servidor, nunca durante una sesión activa."""
 for path in (root/'data'/'replays').glob('*/manifest.json'):
  try:
   meta=json.loads(path.read_text(encoding='utf-8'))
   validate_manifest(meta,path.parent.name)
   if meta.get('status')!='running':continue
   meta['status']='error'
   for line in (path.parent/'samples.jsonl').read_text(encoding='utf-8').splitlines():
    try:
     sample=json.loads(line)
     t=sample['t']
     if type(t) not in (int,float) or not math.isfinite(t) or t<0:break
     meta['end']=t
    except (ValueError,KeyError,TypeError):break
   tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
  except (OSError,ValueError,KeyError,TypeError):
   if on_error:on_error(path.parent.name)
   continue

def get(handler,url,root):
 q=parse_qs(url.query);sid=q.get('session',[''])[0]
 try:
  with handler.server.engine.lock:
   activo=getattr(handler.server.engine,'project_id',None)
   current=copy.deepcopy(handler.server.engine.config)
  if url.path.endswith('/history'):
   # Cada proyecto ve solo sus propias sesiones: son espacios distintos y
   # mezclarlas haria parecer que un terminal tiene grabaciones de otro.
   rows=[]
   for p in (root/'data'/'replays').glob('*/manifest.json'):
    try:meta=validate_manifest(json.loads(p.read_text(encoding='utf-8')),p.parent.name)
    except (OSError,ValueError):continue
    if activo and meta.get('projectId') not in (activo,None):continue
    rows.append(public(meta))
   return handler.send_data(200,sorted(rows,key=lambda r:r['created'],reverse=True)[:50])
  meta=validate_manifest(manifest(root,sid),sid)
  if activo and meta.get('projectId') not in (activo,None):
   raise ValueError('La sesión no pertenece al proyecto abierto.')
  if url.path.endswith('/data'):
   samples=[]
   for line in (directory(root,sid)/'samples.jsonl').read_text(encoding='utf-8').splitlines():
    try:samples.append(json.loads(line))
    except ValueError:break
   if q.get('projection') == ['current']:
    if not meta.get('projectId') or meta['projectId']!=activo:
     raise ValueError('No se puede reproyectar una sesión sin pertenencia verificable al proyecto abierto.')
    from replay_projection import current_projection
    samples = current_projection(meta, samples, current)
   return handler.send_data(200,{**public(meta),'samples':samples})
  if url.path.endswith('/video'):
   camera=next((c for c in meta['cameras'] if c['id']==q.get('camera',[''])[0]),None)
   if not camera:raise ValueError('Cámara no incluida en esta grabación.')
   source=camera['source']
   if not isinstance(source,str) or '://' in source:raise ValueError('Esta fuente en vivo no tiene video archivado.')
   path=(root/source).resolve()
   hold_path(path)
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


def report_snapshot(root, sid, project_id, *, strict=False):
 """Reconstruye un informe de una sesión guardada, sin reactivar videos."""
 hold_path(directory(root,sid))
 meta=validate_manifest(manifest(root,sid),sid)
 if meta.get('projectId') != project_id:
  raise ValueError('La sesión no pertenece al proyecto abierto.')
 if meta.get('status') == 'running':
  raise ValueError('Finaliza el monitoreo antes de consultar este informe guardado.')
 last={};series=[];digest=hashlib.sha256();size=0;count_samples=0;last_t=None
 verified_format='evidenceVersion' in meta
 with (directory(root,sid)/'samples.jsonl').open('rb') as source:
  for line in source:
   digest.update(line);size+=len(line);count_samples+=1
   try:sample=json.loads(line)
   except ValueError:
    if strict or verified_format:raise
    continue
   if (strict or verified_format) and (not isinstance(sample,dict) or type(sample.get('t')) not in (int,float)
       or not math.isfinite(sample['t']) or sample['t']<0 or not isinstance(sample.get('cameras'),list)
       or any(not isinstance(camera,dict) or not isinstance(camera.get('people'),list)
              or any(not isinstance(person,dict) for person in camera['people']) for camera in sample['cameras'])):
    raise ValueError('La sesión guardada contiene muestras incompletas o inválidas.')
   if (strict or verified_format) and (sample['t']>meta['end'] or (last_t is not None and sample['t']<last_t)):
    raise ValueError('Los tiempos de la evidencia no coinciden con la sesión.')
   last_t=sample['t']
   last=sample
   count=sum(len(c.get('people',[])) for c in sample.get('cameras',[]))
   series.append({'t':sample['t'],'count':count})
   if len(series)>3600:series=series[::2]
 integrity='unknown'
 if verified_format:
  completion=meta.get('completion')
  expected={'version':1,'samples':count_samples,'bytes':size,'sha256':digest.hexdigest(),
            'lastT':last_t,'end':meta['end'],'status':meta['status']}
  if meta['evidenceVersion']!=1 or not isinstance(completion,dict) or completion!=expected:
   raise ValueError('Evidencia incompleta o finalización incoherente; no se puede publicar un informe normal.')
  integrity='verified'
 # Compatibility is explicit: legacy remains readable, without claiming that
 # its completeness is verifiable. This field never rewrites historical files.
 meta={**meta,'evidenceIntegrity':integrity}
 pid=meta.get('config',{}).get('planId','custom')
 analytics=meta.get('reportAnalytics') or meta.get('levelAnalytics',{}).get(pid) or last.get('levels',{}).get(pid) or last.get('analytics') or {'clusters':[],'zones':[],'heat':[],'mappedCount':0}
 state={'session':sid,'status':meta['status'],'mode':'demo' if meta['module']=='demo' else 'p2pnet','t':meta['end'],'planId':pid,'people':[],'cameras':[], 'analytics':analytics,'cameraAnalytics':meta.get('cameraAnalytics') or {c['id']:c.get('analysis') or {} for c in last.get('cameras',[])},'totals':meta.get('totals',{}),'series':series,'testRun':bool(meta.get('config',{}).get('testRun'))}
 config={**meta['config'],'cameras':meta['cameras']}
 return config,state,meta
