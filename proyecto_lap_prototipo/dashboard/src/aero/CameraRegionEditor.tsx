import {useRef,useState} from 'react';
import type {Camera,Config,Point} from './types';
import VideoLineEditor from './VideoLineEditor';
import {isActive} from './types';
import type {Session} from './useSession';

export default function CameraRegionEditor({camera,config,session,onChange}:{camera:Camera;config:Config;session:Session;onChange:(c:Config)=>void}){
  const [revision,setRevision]=useState(0),[seconds,setSeconds]=useState(0),[selected,setSelected]=useState<number|null>(null);
  const [loaded,setLoaded]=useState(false);
  const [undo,setUndo]=useState<Point[][]>([]);
  const remember=()=>setUndo(h=>[...h.slice(-19),points.map(p=>[...p] as Point)]);
  const [region,setRegion]=useState('useful'),[zoneName,setZoneName]=useState('Zona comercial');
  const edited=camera.analysisZones?.find(z=>z.id===region);
  const drag=useRef<number|null>(null);
  const points:Point[]=edited?.points||camera.detectionZone||[[0,0],[1,0],[1,1],[0,1]];
  const disabled=isActive(session.state.status)||session.busy;
  const update=(zone:Point[])=>onChange({...config,cameras:config.cameras.map(c=>c.id===camera.id?{...c,...(edited?{analysisZones:c.analysisZones?.map(z=>z.id===edited.id?{...z,points:zone}:z)}:{detectionZone:zone})}:c)});
  const point=(e:React.PointerEvent<SVGSVGElement>):Point=>{const r=e.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];};
  function add(p:Point){
    if(points.length>=50)return;
    let best=0,distance=Infinity;
    points.forEach((a,i)=>{const b=points[(i+1)%points.length],dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));const d=Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);if(d<distance){distance=d;best=i;}});
    if(distance>.035){setSelected(null);return;}
    remember();update([...points.slice(0,best+1),p,...points.slice(best+1)]);setSelected(best+1);
  }
  return <section className="region-editor"><h3>Zona útil de la imagen</h3><p>El video conserva su forma rectangular. Arrastra los puntos para excluir reflejos, otras plantas y áreas que no quieres analizar. Haz clic en un borde para añadir un punto.</p><div className="inline"><label>Área que estás editando<select disabled={disabled} value={region} onChange={e=>{setRegion(e.target.value);setSelected(null);setUndo([]);}}><option value="useful">Zona útil · límite general</option>{camera.analysisZones?.map(z=><option key={z.id} value={z.id}>{z.name}</option>)}</select></label><label>Nombre de nueva zona<input disabled={disabled} maxLength={80} value={zoneName} onChange={e=>setZoneName(e.target.value)}/></label><button disabled={disabled||!zoneName.trim()||(camera.analysisZones?.length||0)>=20} onClick={()=>{const id=crypto.randomUUID();onChange({...config,cameras:config.cameras.map(c=>c.id===camera.id?{...c,analysisZones:[...(c.analysisZones||[]),{id,name:zoneName.trim(),points:points.map(p=>[...p] as Point),threshold:c.crowdThreshold??10,dwell:c.crowdDwell??3}]}:c)});setRegion(id);setSelected(null);}}>Añadir zona y ajustar sus puntos</button>{edited&&<button disabled={disabled} onClick={()=>{onChange({...config,cameras:config.cameras.map(c=>c.id===camera.id?{...c,analysisZones:c.analysisZones?.filter(z=>z.id!==edited.id)}:c)});setRegion('useful');}}>Quitar esta zona</button>}</div><small>Obtener una imagen no guarda tus cambios. Usa Guardar configuración al terminar. Las zonas permiten comparar sectores dentro de una toma. La zona útil sigue excluyendo el exterior para todos los análisis.</small><div className="inline"><label>Segundo del video<input type="number" min="0" step="1" value={seconds} disabled={disabled} onChange={e=>setSeconds(+e.target.value)}/></label><button disabled={disabled||camera.source===''} onClick={()=>void session.action(async()=>{await session.post('camera-preview',{camera:camera.id,seconds,source:camera.source});setRevision(Date.now());setLoaded(true);})}>Obtener imagen del instante</button><button disabled={disabled||camera.source===''} onClick={()=>void session.action(async()=>{await session.post('camera-preview',{camera:camera.id,seconds:0,source:camera.source});setSeconds(0);setRevision(Date.now());setLoaded(true);})}>Ver imagen inicial</button></div>
    <div className="inline"><button disabled={disabled||!undo.length} onClick={()=>{update(undo[undo.length-1]);setUndo(h=>h.slice(0,-1));setSelected(null);}}>Deshacer edición</button><button disabled={disabled||selected===null||points.length<=3} onClick={()=>{remember();update(points.filter((_,i)=>i!==selected));setSelected(null);}}>Quitar punto seleccionado</button><button disabled={disabled} onClick={()=>{remember();update([[0,0],[1,0],[1,1],[0,1]]);}}>{edited?'Ampliar zona a toda la imagen':'Usar toda la imagen'}</button></div>
    {loaded&&<div className="region-image"><img src={`/api/frame?camera=${encodeURIComponent(camera.id)}&v=${revision}`} alt={`Área útil de ${camera.name||camera.id}`}/><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Editar zona útil" onPointerDown={e=>{if(disabled)return;e.preventDefault();e.stopPropagation();const p=point(e);const i=points.findIndex(v=>Math.hypot(v[0]-p[0],v[1]-p[1])<.035);if(i>=0){remember();drag.current=i;setSelected(i);e.currentTarget.setPointerCapture(e.pointerId);}else add(p);}} onPointerMove={e=>{if(disabled||drag.current===null)return;const p=point(e);update(points.map((v,i)=>i===drag.current?p:v));}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}><polygon points={points.map(p=>`${p[0]*100},${p[1]*100}`).join(' ')} fill="#f6b52422" stroke="#ffb300" strokeWidth=".4"/>{points.map((p,i)=><g key={i}><circle cx={p[0]*100} cy={p[1]*100} r="1" fill={i===selected?'#fff':'#ffb300'} stroke="#493600" strokeWidth=".2"/><text x={p[0]*100+1.5} y={p[1]*100} fontSize="2.8" fill="white" stroke="#333" strokeWidth=".08">{i+1}</text></g>)}</svg></div>}
    {loaded&&<VideoLineEditor camera={camera} config={config} onChange={onChange} disabled={disabled} revision={revision}/>}
<small>{points.length} puntos · {session.dirty?'Cambios pendientes de guardar':'Configuración guardada'} · Esta zona se comparte entre seguimiento y conteo.</small>
  </section>;
}
