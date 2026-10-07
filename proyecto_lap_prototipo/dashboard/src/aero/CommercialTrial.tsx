import {useEffect, useRef, useState} from 'react';
import type {Session} from './useSession';
import './commercial-trial.css';

type Observation = {id:string;name:string;session:string;date:string;hour:number;entries:number;exits:number;coverage:number};
type Run = {id:string;created:string;businesses:Observation[];cameraNames?:string[];duration?:number;sourceLabel?:string;statusLabel?:string};
type Result = Omit<Observation,'id'|'name'> & {id:string;businessId:string;businessName:string;filename:string;created:string;days:number;nextDays:number;rate:number|null;estimate:number|null;nextTarget:string;expectedEntries:number|null;nextRate:number|null;forecast:number|null;historicalConversion:number|null;historyTransactions:number;historyEntries:number};
const money=(value:number|null)=>value==null?'Falta historial':new Intl.NumberFormat('es-PE',{style:'currency',currency:'PEN'}).format(value);
const hour=(n:number)=>`${String(n).padStart(2,'0')}:00–${String((n+1)%24).padStart(2,'0')}:00`;

const dateTime=(value:string)=>new Date(value).toLocaleString('es-PE',{timeZone:'America/Lima',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const duration=(seconds:number)=>{const total=Math.round(seconds);return total<60?`${total} s`:`${Math.floor(total/60)} min${total%60?` ${total%60} s`:''}`;};
const runLabel=(run:Run)=>`${run.cameraNames?.join(', ')||run.businesses.map(b=>b.name).join(', ')} · ${dateTime(run.created)} · ${duration(run.duration??Math.max(...run.businesses.map(b=>b.coverage),0))}`;

export default function CommercialTrial({session}:{session:Session}) {
  const resultRef=useRef<HTMLElement>(null);
  const [fileVersion,setFileVersion]=useState(0);
  const [runs,setRuns]=useState<Run[]>([]);
  const [saved,setSaved]=useState<Result[]>([]);
  const [sid,setSid]=useState('');
  const [bid,setBid]=useState('');
  const [file,setFile]=useState<File|null>(null);
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const [refresh,setRefresh]=useState(0);
  const [busy,setBusy]=useState(false);
  const headers={'X-LAP-Session':localStorage.getItem('aero.session')||''};
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);setError('');setFile(null);setResult(null);
    fetch('/api/commercial/trial',{headers,signal:controller.signal}).then(async response=>{
      const data=await response.json();if(!response.ok)throw Error(data.error);
      setRuns(data.sessions);setSaved(data.saved);setSid(data.sessions[0]?.id||'');setBid(data.sessions[0]?.businesses[0]?.id||'');
    }).catch(e=>{if(!controller.signal.aborted)setError(String(e.message));}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[session.projects.active,refresh]);
  const run=runs.find(r=>r.id===sid);
  const observed=run?.businesses.find(b=>b.id===bid);
  const resultRun=runs.find(r=>r.id===result?.session);
  function showSaved(item:Result){
    const savedRun=runs.find(r=>r.id===item.session);
    if(savedRun){setSid(savedRun.id);setBid(item.businessId);}
    setFile(null);setFileVersion(n=>n+1);setResult(item);setError('');
    requestAnimationFrame(()=>resultRef.current?.scrollIntoView({behavior:'smooth',block:'start'}));
  }
  function reset(){setFile(null);setResult(null);setError('');}
  async function example(){
    setError('');
    try{
      const response=await fetch(`/api/commercial/trial-template?session=${encodeURIComponent(sid)}&business=${encodeURIComponent(bid)}`,{headers});
      if(!response.ok)throw Error((await response.json()).error);
      const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=`Ejemplo_${observed?.name.replace(/[^a-z0-9]/gi,'_')}_SINTETICO.csv`;a.click();URL.revokeObjectURL(url);
    }catch(e){setError(e instanceof Error?e.message:'No se pudo descargar.');}
  }
  async function calculate(){
    if(!file||!observed)return;
    setBusy(true);setError('');setResult(null);
    try{
      const encoded=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('No se pudo leer el archivo.'));reader.readAsDataURL(file);});
      const response=await session.post('commercial/trial',{projectId:session.projects.active,session:sid,businessId:bid,filename:file.name,file:encoded});
      setResult(response);setSaved(previous=>[response,...previous].slice(0,20));
    }catch(e){setError(e instanceof Error?e.message:'No se pudo calcular.');}
    finally{setBusy(false);}
  }
  return <section className="commerce-trial" aria-label="Prueba comercial con Excel">
    <header><h2>Prueba una tienda con tu Excel</h2><p>Combina las entradas de un video con un histórico de ejemplo. Cada cálculo se guarda como ensayo y no cambia tus ventas registradas.</p></header>
    <div className="trial-steps">
      <section><h3>1. Elige el video y la tienda</h3>
        <label htmlFor="trial-session">Monitoreo de prueba finalizado</label><select id="trial-session" disabled={loading||busy} value={sid} onChange={e=>{setSid(e.target.value);setBid(runs.find(r=>r.id===e.target.value)?.businesses[0]?.id||'');reset();}}>
          {!runs.length&&<option value="">{loading?'Cargando…':'Todavía no hay videos con accesos medidos'}</option>}
          {runs.map(r=><option key={r.id} value={r.id}>{runLabel(r)}</option>)}
        </select>
        {run&&<div className="trial-run-context"><strong>{run.sourceLabel||'Monitoreo guardado'} · {run.statusLabel||'Finalizado'}</strong><p>Cámaras: {run.cameraNames?.join(', ')||'Ver detalle del monitoreo'}.</p><p>Tiendas con accesos medidos: {run.businesses.map(b=>b.name).join(', ')}.</p><small>Fecha del análisis en Lima. Debajo se indica la fecha y hora asignada al video para cruzar las ventas.</small></div>}
        <label htmlFor="trial-business">Tienda vinculada a una línea</label><select id="trial-business" value={bid} disabled={busy||!run} onChange={e=>{setBid(e.target.value);reset();}}>
          {!run&&<option value="">Selecciona un monitoreo</option>}{run?.businesses.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        {observed&&<p className="trial-observation"><strong>{observed.entries} {observed.entries===1?'entrada':'entradas'} y {observed.exits} {observed.exits===1?'salida':'salidas'}</strong><br/>{observed.coverage.toFixed(1)} s observados · {observed.date} · {hour(observed.hour)} Lima</p>}
        <button onClick={()=>setRefresh(n=>n+1)} disabled={busy}>Actualizar lista de monitoreos</button>
        {!runs.length&&!loading&&<p>En Vista general activa Prueba con videos, selecciona cámaras con líneas vinculadas a negocios y termina un análisis.</p>}
      </section>
      <section><h3>2. Carga el histórico de esa tienda</h3>
        <p>Usa uno de los Excel por tienda o descarga un ejemplo compatible con el video elegido. El ejemplo contiene ocho fechas anteriores y datos ficticios.</p>
        <button disabled={!observed||busy} onClick={()=>void example()}>Descargar ejemplo para esta tienda (CSV)</button>
        <label htmlFor="trial-file">Archivo Excel (.xlsx) o CSV</label><input key={sid+bid+refresh+fileVersion} id="trial-file" type="file" accept=".xlsx,.csv" disabled={busy||!observed} onChange={e=>{const selected=e.target.files?.[0]||null;setResult(null);setError('');if(selected&&selected.size>2000000){setFile(null);setError('El archivo supera 2 MB.');}else setFile(selected);}}/>
        <small>CSV se abre en Excel. No necesitas convertir un .xlsx. Su hoja de datos debe llamarse Historico.</small>
      </section>
    </div>
    <div className="trial-calculate"><div><h3>3. Calcula y guarda el ensayo</h3><p>{file?`${file.name} · ${observed?.name}`:'Selecciona el archivo para habilitar el cálculo.'}</p></div><button className="primary" disabled={!file||!observed||busy||session.auth.rol!=='operador'} onClick={()=>void calculate()}>{busy?'Calculando…':'Calcular y guardar ensayo'}</button></div>
    {error&&<p className="trial-error" role="alert">{error}</p>}
    {result&&<section ref={resultRef} className="trial-result" aria-label="Resultado del ensayo"><header><h2>{result.businessName}: resultado guardado</h2><p>{resultRun?runLabel(resultRun):`Video del ${result.date}, ${hour(result.hour)}`}.</p><p>Histórico utilizado: {result.filename}. Ensayo calculado el {dateTime(result.created)}.</p></header>
      <div className="trial-metrics">
        <article><h3>Entradas del video</h3><strong>{result.entries}</strong><p>{result.coverage.toFixed(1)} segundos observados. Son cruces de la línea, no compradores únicos.</p></article>
        <article><h3>Valor estimado del tramo</h3><strong>{money(result.estimate)}</strong><p>{result.rate==null?'Faltan al menos tres fechas anteriores del mismo día de semana y hora con 55 minutos cubiertos.':`${result.entries} entradas × ${money(result.rate)} por entrada histórica (aprox.). Referencia: ${result.days} días.`}</p><small>No se amplía el video a una hora completa.</small></article>
        <article><h3>Pronóstico de la siguiente hora</h3><strong>{money(result.forecast)}</strong><p>{result.expectedEntries==null?'Falta historial comparable de la siguiente hora.':`${result.expectedEntries} entradas esperadas × ${money(result.nextRate)} por entrada (aprox.). Referencia: ${result.nextDays} días.`}</p><small>{result.nextTarget.slice(0,10)} · {result.nextTarget.slice(11,16)} Lima. Sirve para planificar, no confirma ventas.</small></article>
      </div>
      <p className="trial-notice">Resultado de ensayo. Si cargas el archivo de ejemplo, las estimaciones dependen de datos ficticios.</p>
      <details><summary>Conversión: qué significa en esta prueba</summary><p><strong>Conversión histórica: {result.historicalConversion==null?'sin referencia suficiente':`${result.historicalConversion}%`}.</strong> {result.historyTransactions} transacciones ÷ {result.historyEntries} entradas históricas × 100. Resume cuántas transacciones hubo por cada 100 entradas en las fechas comparables.</p><p>No es la conversión de las personas de este video. Para calcularla se necesitan las transacciones de esa misma hora y al menos 55 minutos de tráfico. La cámara no detecta pagos.</p></details>
      <details className="trial-trace"><summary>Referencia del registro</summary><p>Monitoreo: {result.session}. Ensayo: {result.id}.</p></details>
    </section>}
    {saved.length>0&&<details className="trial-history"><summary>Ensayos guardados ({saved.length})</summary><ul>{saved.map(r=><li key={r.id}><span><strong>{r.businessName}</strong><small>Calculado el {dateTime(r.created)} · {r.filename}<br/>{runs.find(run=>run.id===r.session)?runLabel(runs.find(run=>run.id===r.session)!):`Video del ${r.date}, ${hour(r.hour)}`} </small></span><button disabled={busy} onClick={()=>showSaved(r)}>Ver resultado</button></li>)}</ul></details>}
  </section>;
}
