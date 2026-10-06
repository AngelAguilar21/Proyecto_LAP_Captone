import {useEffect,useRef,useState} from 'react';
import type {Camera,Config,Point} from './types';
import {isActive} from './types';
import type {Session} from './useSession';
import Icon from './Icon';

export default function CameraRegionEditor({camera,config,session,onChange}:{camera:Camera;config:Config;session:Session;onChange:(c:Config)=>void}){
  const status=session.state.cameras.find(c=>c.id===camera.id);
  const hasFrame=!!status&&['ready','live','paused','stopped','ended'].includes(status.status);
  const [revision,setRevision]=useState(Date.now());
  const [loaded,setLoaded]=useState(hasFrame);
  const [selected,setSelected]=useState<number|null>(null);
  const [undo,setUndo]=useState<Point[][]>([]);
  const [drawing,setDrawing]=useState(false);
  const [draft,setDraft]=useState<Point[]>([]);
  const drag=useRef<number|null>(null);
  const points:Point[]=camera.detectionZone||[[0,0],[1,0],[1,1],[0,1]];
  const visible=drawing?draft:points;
  const disabled=session.busy;
  useEffect(()=>{if(hasFrame)setLoaded(true);},[hasFrame]);
  const update=(zone:Point[])=>onChange({...config,cameras:config.cameras.map(c=>c.id===camera.id?{...c,detectionZone:zone}:c)});
  const remember=()=>setUndo(history=>[...history.slice(-9),points.map(p=>[...p] as Point)]);
  const point=(e:React.PointerEvent<SVGSVGElement>):Point=>{const r=e.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];};
  function add(p:Point){
    if(points.length>=20)return;
    let best=0,distance=Infinity;
    points.forEach((a,i)=>{const b=points[(i+1)%points.length],dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy||1)));const d=Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);if(d<distance){distance=d;best=i;}});
    if(distance>.04){setSelected(null);return;}
    remember();update([...points.slice(0,best+1),p,...points.slice(best+1)]);setSelected(best+1);
  }
  function useFrame(){
    if(isActive(session.state.status)){setRevision(Date.now());setLoaded(true);return;}
    void session.action(async()=>{await session.post('camera-preview',{camera:camera.id,seconds:0,source:camera.source});setRevision(Date.now());setLoaded(true);});
  }
  function finishDrawing(){
    if(draft.length<3)return;
    remember();update(draft);setDrawing(false);setSelected(null);
  }
  const polygon=visible.map(p=>`${p[0]*100},${p[1]*100}`).join(' ');
  const cutout=visible.length>=3?`M0 0H100V100H0Z M${visible.map(p=>`${p[0]*100} ${p[1]*100}`).join('L')}Z`:'';
  return <section className="region-editor simple-region-editor">
    <div className="region-title"><div><h3>Zona útil</h3><p>Solo el área clara será analizada. Deja espejos, vidrios y pantallas en la parte oscura.</p></div><span className={camera.detectionZone?'pill good':'pill warn'}>{camera.detectionZone?'Definida':'Pendiente'}</span></div>
    <div className="notice compact mirror-note"><Icon name="shield" size={17}/><span>El detector también ve personas reflejadas. Esta máscara evita que entren al conteo.</span></div>
    <div className="region-actions">
      <button disabled={disabled||camera.source===''} onClick={useFrame}><Icon name="camera" size={15}/> Usar imagen actual</button>
      {!drawing?<button className="primary" disabled={disabled||!loaded} onClick={()=>{setDraft([]);setDrawing(true);setSelected(null);}}>Dibujar zona útil</button>:<>
        <button className="primary" disabled={disabled||draft.length<3} onClick={finishDrawing}>Terminar zona</button>
        <button disabled={disabled} onClick={()=>{setDrawing(false);setDraft([]);}}>Cancelar</button>
      </>}
      {!drawing&&<button disabled={disabled||!undo.length} onClick={()=>{update(undo[undo.length-1]);setUndo(history=>history.slice(0,-1));setSelected(null);}}>Deshacer</button>}
      {!drawing&&<button disabled={disabled} onClick={()=>{remember();update([[0,0],[1,0],[1,1],[0,1]]);}}>Usar imagen completa</button>}
    </div>
    {drawing&&<p className="drawing-instruction" role="status">{draft.length<3?'Haz clic alrededor del suelo real. Necesitas al menos tres puntos.':'Puedes añadir más puntos o terminar la zona.'}</p>}
    {loaded?<div className="region-image"><img src={`/api/frame?camera=${encodeURIComponent(camera.id)}&v=${revision}`} alt={`Zona útil de ${camera.name||camera.id}`}/><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Delimitar zona útil" onPointerDown={e=>{if(disabled)return;e.preventDefault();e.stopPropagation();const p=point(e);if(drawing){if(draft.length<20)setDraft(value=>[...value,p]);return;}const i=points.findIndex(v=>Math.hypot(v[0]-p[0],v[1]-p[1])<.035);if(i>=0){remember();drag.current=i;setSelected(i);e.currentTarget.setPointerCapture(e.pointerId);}else add(p);}} onPointerMove={e=>{if(disabled||drawing||drag.current===null)return;const p=point(e);update(points.map((v,i)=>i===drag.current?p:v));}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}>
      {visible.length>=3&&<path d={cutout} fill="#071726aa" fillRule="evenodd"/>}
      {visible.length>=2&&(visible.length>=3?<polygon points={polygon} fill="#20c99720" stroke="#38d39f" strokeWidth=".65"/>:<polyline points={polygon} fill="none" stroke="#38d39f" strokeWidth=".65"/>)}
      {visible.map((p,i)=><circle key={i} cx={p[0]*100} cy={p[1]*100} r="1.15" fill={i===selected?'#fff':'#38d39f'} stroke="#062b22" strokeWidth=".25"/>)}
    </svg></div>:<div className="empty-state compact"><Icon name="camera" size={28}/><strong>Carga una imagen de la cámara</strong><p>Después dibuja el contorno del suelo real.</p></div>}
    <small>{camera.detectionZone?`${points.length} puntos · ${session.dirty?'Pendiente de guardar':'Guardado'}`:'Dibuja la zona antes de continuar.'}</small>
  </section>;
}
