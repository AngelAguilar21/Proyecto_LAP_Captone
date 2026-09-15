import {useState} from 'react';
import type {Session} from './useSession';
import {isActive} from './types';
import {CameraVideo} from './CameraPanel';
export default function MultiCameraPanel({session}:{session:Session}){
 const c=session.config!;
 const cameras=c.cameras.filter(v=>(v.planId||'custom')===(c.planId||'custom'));
 const [selected,setSelected]=useState<string[]>([]),[unified,setUnified]=useState(false);
 const busy=isActive(session.state.status)||session.busy;
 return <section className="multi-camera-panel aero-panel"><div className="panel-heading"><h2>Comparar cámaras del espacio</h2><span>{c.floor}</span></div><div className="multi-camera-controls">{cameras.map(v=><label className="check" key={v.id}><input disabled={busy} type="checkbox" checked={selected.includes(v.id)} onChange={e=>setSelected(e.target.checked?[...selected,v.id]:selected.filter(id=>id!==v.id))}/>{v.name||v.id}</label>)}<label className="check"><input disabled={busy} type="checkbox" checked={unified} onChange={e=>setUnified(e.target.checked)}/> Asociar personas en el plano</label><button className="primary" disabled={busy||!selected.length} onClick={()=>void session.action(async()=>{await session.save();await session.post('start',{detector:'yolo',cameraIds:selected,requireUnified:unified});session.setNotice(unified?'Seguimiento sobre plano iniciado.':'Seguimiento por cámara iniciado. Los IDs de cámaras distintas se mantienen separados.');})}>Analizar selección</button><p className="subtle">Sin asociación puedes probar varias cámaras aunque todavía no estén calibradas. Para unir recorridos, verifica suelo común, calibración, zonas útiles y sincronización.</p></div><div className="multi-camera-grid">{cameras.filter(v=>session.state.cameras.some(s=>s.id===v.id)||selected.includes(v.id)).map(v=><article key={v.id}><h3>{v.name||v.id}</h3><CameraVideo camera={v} state={session.state} connected={session.connected}/><p>{session.state.cameras.find(s=>s.id===v.id)?.count??session.state.cameras.find(s=>s.id===v.id)?.lastCount??'—'} personas en la última muestra procesada</p></article>)}</div></section>;
}
