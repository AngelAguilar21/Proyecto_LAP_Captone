"""Copia local de geometría pública LAP/Living Map; no utiliza claves privadas."""
import json,math,urllib.request,datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import mapbox_vector_tile
from shapely.geometry import shape,mapping
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'dashboard/public/maps/lap'
ZOOM=17
BBOX=(-77.1232,-12.0381,-77.1104,-12.0199)
TEMPLATE='https://prod.cdn.livingmap.com/tiles/lima_airport_two/{z}/{x}/{y}.pbf?lang=es-PE'
def tile(lon,lat):
 return (lon+180)/360*2**ZOOM,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**ZOOM

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 x0,y1=tile(BBOX[0],BBOX[1]);x1,y0=tile(BBOX[2],BBOX[3])
 tasks=[(x,y) for x in range(int(x0),int(x1)+1) for y in range(int(y0),int(y1)+1)]
 meters=40075016.68557849*math.cos(math.radians(-12.029))/2**ZOOM
 groups={}
 def read(pos):
  x,y=pos
  data=urllib.request.urlopen(TEMPLATE.format(z=ZOOM,x=x,y=y),timeout=45).read()
  return x,y,mapbox_vector_tile.decode(data,default_options={'y_coord_down':True}).get('indoor',{})
 def convert(coords,x,y,extent):
  if isinstance(coords[0],(float,int)): return [(x+coords[0]/extent-x0)*meters,(y+coords[1]/extent-y0)*meters]
  return [convert(p,x,y,extent) for p in coords]
 with ThreadPoolExecutor(max_workers=3) as pool:
  for x,y,layer in pool.map(read,tasks):
   for f in layer.get('features',[]):
    p=f['properties'];floor=p.get('floor_id')
    if floor not in (1,2,3,4): continue
    g=f['geometry'];g={**g,'coordinates':convert(g['coordinates'],x,y,layer['extent'])}
    key=(floor,p.get('uid'),g['type'])
    entry=groups.setdefault(key,{'properties':{k:p[k] for k in ['name','class','type','category','is_label_shown','local_rank'] if k in p},'geometries':[]})
    geom=shape(g)
    if not geom.is_valid: geom=geom.buffer(0) if 'Polygon' in g['type'] else geom
    if not geom.is_empty: entry['geometries'].append(geom)
 print('Teselas:',len(tasks),'elementos:',len(groups),flush=True)
 for floor in (1,2,3,4):
  features=[]
  for (level,uid,_),e in groups.items():
   if level!=floor or not e['geometries']: continue
   geom=unary_union(e['geometries'])
   features.append({'id':str(uid),'properties':e['properties'],'geometry':mapping(geom)})
  doc={'floor':floor,'name':f'LAP · Nivel {floor}','width':round((x1-x0)*meters,3),'height':round((y1-y0)*meters,3),'unit':'meters','features':features,'attribution':'© Living Map · Lima Airport Partners','source':'https://map.lima-airport.com/','capturedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'bounds':BBOX,'projection':'Web Mercator local, escala corregida a latitud -12.029; referencia cartográfica, no levantamiento topográfico'}
  doc['viewBounds']=unary_union([shape(f['geometry']) for f in features if f['geometry']['type'] in ('Polygon','MultiPolygon')]).bounds
  (DEST/f'{floor}.json').write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
  print('Nivel',floor,len(features),flush=True)
if __name__=='__main__': main()
