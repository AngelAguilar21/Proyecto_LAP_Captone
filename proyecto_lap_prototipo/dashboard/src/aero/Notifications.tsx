import {useEffect,useRef,useState} from 'react';
import type {Session} from './useSession';
import {formatTime,isActive} from './types';
import {planAlerts} from './zoneAlerts';

type Notice={id:string;title:string;body:string};
export default function Notifications({session}:{session:Session}){
 const [alerts,setAlerts]=useState<Notice[]>([]);
 const seen=useRef(new Set<string>());
 useEffect(()=>{seen.current.clear();setAlerts([]);},[session.state.session]);
 useEffect(()=>{
  if(!isActive(session.state.status))return;
  const fresh:Notice[]=[];
  for(const [id,a] of Object.entries(session.state.cameraAnalytics||{})){
   for(const episode of a.occupancy?.episodes||[]){
    const key=`${id}:${episode.id||episode.zone+':'+episode.start}`;
    if(seen.current.has(key))continue;
    seen.current.add(key);
    fresh.push({id:key,title:`Concentración en ${episode.zone}`,body:`${session.config?.cameras.find(c=>c.id===id)?.name||id}: máximo ${episode.peak} personas desde ${formatTime(episode.start)}. Consulta el video para revisar el episodio.`});
   }
  }
  for(const episode of session.config ? planAlerts(session.config,session.state) : []){
   const key=episode.id;
   if(!seen.current.has(key)){seen.current.add(key);fresh.push({id:key,title:`Alerta en ${episode.zone}`,body:`Máximo ${episode.people} personas observadas. Concentración sostenida durante ${Math.floor(episode.duration)} s.`});}
  }
  if(fresh.length)setAlerts(a=>[...a,...fresh].slice(-3));
 },[session.state.cameraAnalytics,session.state.analytics,session.state.t,session.state.status,session.config]);
 useEffect(()=>{if(!alerts.length)return;const id=setTimeout(()=>setAlerts(a=>a.slice(1)),12000);return()=>clearTimeout(id);},[alerts]);
 useEffect(()=>{if(!session.notice)return;const id=setTimeout(()=>session.setNotice(''),6000);return()=>clearTimeout(id);},[session.notice]);
 return <div className="notification-stack" aria-live="polite" aria-relevant="additions">
  {session.notice&&<div className="toast toast-success" role="status"><div><strong>Cambio realizado</strong><p>{session.notice}</p></div><button aria-label="Cerrar confirmación" onClick={()=>session.setNotice('')}>×</button></div>}
  {alerts.map(a=><div className="toast toast-warning" key={a.id}><div><strong>{a.title}</strong><p>{a.body}</p></div><button aria-label={`Cerrar ${a.title}`} onClick={()=>setAlerts(all=>all.filter(v=>v.id!==a.id))}>×</button></div>)}
 </div>;
}
