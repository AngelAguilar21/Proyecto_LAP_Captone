"""Complementa los lugares a zoom 19 sin cambiar el origen ni las geometrías del plano."""
import json, math, urllib.request, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import mapbox_vector_tile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'dashboard/public/maps/lap'
Z=19

def main():
 docs={n:json.loads((DEST/f'{n}.json').read_text(encoding='utf-8')) for n in range(1,5)}
 lon,_,_,lat=docs[3]['bounds']
 x0=(lon+180)/360*2**Z
 y0=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**Z
 meters=40075016.68557849*math.cos(math.radians(-12.029))/2**Z
 boxes=[d['viewBounds'] for d in docs.values()]
 tasks=[(x,y) for x in range(int(x0+min(b[0] for b in boxes)/meters),int(x0+max(b[2] for b in boxes)/meters)+1) for y in range(int(y0+min(b[1] for b in boxes)/meters),int(y0+max(b[3] for b in boxes)/meters)+1)]
 cache=ROOT/'data/map-detail-cache';cache.mkdir(parents=True,exist_ok=True)
 def read(pos):
  x,y=pos;p=cache/f'{Z}-{x}-{y}.pbf'
  if not p.exists():p.write_bytes(urllib.request.urlopen(f'https://prod.cdn.livingmap.com/tiles/lima_airport_two/{Z}/{x}/{y}.pbf?lang=es-PE',timeout=30).read())
  return x,y,mapbox_vector_tile.decode(p.read_bytes(),default_options={'y_coord_down':True}).get('indoor',{})
 additions={n:[] for n in docs};seen={n:{str(f['id']) for f in d['features'] if f['geometry']['type']=='Point'} for n,d in docs.items()}
 with ThreadPoolExecutor(max_workers=4) as pool:
  for i,(x,y,layer) in enumerate(pool.map(read,tasks)):
   for f in layer.get('features',[]):
    props=f['properties'];n=props.get('floor_id');g=f['geometry'];uid=str(props.get('uid',f.get('id')))
    if n not in docs or not props.get('name') or g['type']!='Point' or uid in seen[n]:continue
    seen[n].add(uid);px,py=g['coordinates'];extent=layer['extent']
    additions[n].append({'id':uid,'properties':{k:props[k] for k in ['name','class','type','category','is_label_shown','local_rank'] if k in props},'geometry':{'type':'Point','coordinates':[(x+px/extent-x0)*meters,(y+py/extent-y0)*meters]}})
   if i%20==0:print(f'{i+1}/{len(tasks)} teselas',flush=True)
 backup=ROOT/'data/maps-before-detail';backup.mkdir(exist_ok=True)
 for n,d in docs.items():
  target=DEST/f'{n}.json'
  if not (backup/target.name).exists():shutil.copy2(target,backup/target.name)
  d['features'].extend(additions[n]);d['detailZoom']=Z
  target.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
  print('Nivel',n,'lugares añadidos',len(additions[n]),flush=True)
if __name__=='__main__':main()
