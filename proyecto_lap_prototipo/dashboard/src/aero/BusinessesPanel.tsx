import { useEffect, useState } from 'react';
import type { useSession } from './useSession';
import type { Business } from './useBusinesses';
import { useBusinesses } from './useBusinesses';
import type { Config,Point } from './types';
import { EMPTY_STATE } from './types';
import MapCanvas from './MapCanvas';
import Icon from './Icon';
import {businessPlaces,loadMapAsset} from './mapAssets';
import type {MapPlace} from './mapAssets';
import './businesses.css';
import BusinessResults from './BusinessResults';
import CameraAccessEditor from './CameraAccessEditor';

type Session=ReturnType<typeof useSession>;
export default function BusinessesPanel({session}:{session:Session}) {
  const config=session.config!;
  const {items,setItems,error,loading}=useBusinesses(session.projects.active||'');
  const [draft,setDraft]=useState<Business|null>(null);
  const [baseline,setBaseline]=useState('');
  const [pending,setPending]=useState<Business|string|null>(null);
  const [deleting,setDeleting]=useState<Business|null>(null);
  const [search,setSearch]=useState('');
  const [showClosed,setShowClosed]=useState(false);
  const [accessEditor,setAccessEditor]=useState(false);
  const [placing,setPlacing]=useState(false);
  const [plan,setPlan]=useState(config.planId||'custom');
  const [cameraId,setCameraId]=useState('');
  const [places,setPlaces]=useState<MapPlace[]>([]);
  const [mapError,setMapError]=useState('');
  const [focus,setFocus]=useState<Point|undefined>();
  const operator=session.auth.rol==='operador';
  const plans=config.plans||{[config.planId||'custom']:config};
  const shownPlan=plans[plan]||config;
  useEffect(()=>{let alive=true;setPlaces([]);setMapError('');if(shownPlan.mapAsset)void loadMapAsset(shownPlan.mapAsset).then(data=>{if(alive)setPlaces(businessPlaces(data,shownPlan.mapAsset!));}).catch(()=>{if(alive)setMapError('No se pudo cargar la lista de locales del mapa. Puedes usar una ubicación propia.');});return()=>{alive=false;};},[shownPlan.mapAsset]);
  const mapConfig:Config={...config,...shownPlan,planId:plan,cameras:config.cameras,workArea:[]};
  const cameras=config.cameras.filter(c=>(c.planId||config.planId||'custom')===plan);
  const camera=cameras.find(c=>c.id===cameraId);
  const doors=(camera?.countLines||[]).map(l=>({camaraId:camera!.id,lineaId:l.id,label:l.name}));
  const normalize=(value:string)=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().trim();
  const filtered=items.filter(b=>b.ubicacion?.planId===plan&&(showClosed||b.estado!=='cerrado')&&normalize(b.nombre).includes(normalize(search)));
  const dirty=!!draft&&JSON.stringify(draft)!==baseline;
  function navigate(target:Business|string){setPending(null);if(typeof target==='string'){setPlan(target);setDraft(null);setPlacing(false);setFocus(undefined);setCameraId('');}else edit(target);}
  function requestNavigate(target:Business|string){if(typeof target!=='string'&&target.id===draft?.id)return;if(dirty){setPending(target);return;}navigate(target);}
  function edit(b:Business){setAccessEditor(false);const next={...b,puertas:[...b.puertas]};setDraft(next);setBaseline(JSON.stringify(next));setPending(null);setFocus(b.ubicacion?.point);setPlan(b.ubicacion?.planId||config.planId||'custom');setCameraId(b.puertas[0]?.camaraId||'');setPlacing(false);setDeleting(null);}
  function create(){setBaseline('');setPending(null);setFocus(undefined);setDraft({id:crypto.randomUUID(),nombre:'',puertas:[],ubicacion:null});setCameraId('');setPlacing(true);setDeleting(null);}
  function selectPlace(p:MapPlace){const existing=items.find(b=>b.referencia?.asset===p.asset&&b.referencia.featureId===p.id);if(existing){if(draft&&!items.some(b=>b.id===draft.id)&&!draft.nombre.trim()&&!draft.puertas.length)edit(existing);else requestNavigate(existing);return;}if(!draft)return;setFocus(p.point);setDraft({...draft,nombre:!draft.nombre||draft.nombre===selectedPlace?.name?p.name:draft.nombre,ubicacion:{planId:plan,point:p.point},referencia:{asset:p.asset,featureId:p.id}});setPlacing(false);}
  const selectedPlace=places.find(p=>p.id===draft?.referencia?.featureId);
  async function save(target:Business|string|null=null){if(!draft)return;await session.action(async()=>{
    if(accessEditor)await session.save(config);
    const response=await session.post('businesses',{...draft,action:'save',projectId:session.projects.active});
    setItems(response.negocios);session.setConfig(response.config);setDraft(null);setPlacing(false);window.dispatchEvent(new Event('aero:businesses'));session.setNotice('Negocio guardado.');if(target)navigate(target);
  });}
  return <div className="businesses-workspace">
    <div className="page-heading"><div><h1>Negocios y accesos</h1><p>Las tiendas del mapa ya están disponibles. Selecciona una tienda para cambiar su nombre o medir sus entradas y salidas.</p></div>{operator&&<button className="primary" onClick={create} disabled={session.busy||!!draft}><Icon name="plus"/>Añadir negocio nuevo</button>}</div>
    {error&&<div role="alert" className="notice warning">{error}</div>}
    <div className="businesses-layout"><section className="aero-panel businesses-list"><div className="businesses-list-head"><h2>Negocios del nivel <span>{filtered.length}</span></h2><label>Buscar negocio<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Nombre del negocio"/></label><label className="business-closed-toggle"><input type="checkbox" checked={showClosed} onChange={e=>setShowClosed(e.target.checked)}/>Mostrar negocios cerrados</label></div>
      {loading?<p className="empty-text">Cargando negocios…</p>:!filtered.length?<p className="empty-text">{items.length?'No hay coincidencias.':'Añade un negocio para vincular sus accesos y analizar sus ventas.'}</p>:<ul>{filtered.map(b=><li key={b.id} className={draft?.id===b.id?'is-selected':''}><button className="business-select" onPointerUp={e=>{if(e.button===0)requestNavigate(b);}} onClick={()=>requestNavigate(b)}><Icon name="pin"/><span><strong>{b.nombre}</strong><small>{b.puertas.length?`${b.puertas.length} ${b.puertas.length===1?'acceso vinculado':'accesos vinculados'}`:'Sin accesos vinculados'}{b.estado==='cerrado'?' · Cerrado':''} · {plans[b.ubicacion?.planId||'']?.floor||'Ubicación pendiente'}</small></span></button>{operator&&b.estado==='cerrado'&&<button disabled={session.busy} onClick={()=>void session.action(async()=>{const r=await session.post('businesses',{action:'reopen',id:b.id,projectId:session.projects.active});setItems(r.negocios);window.dispatchEvent(new Event('aero:businesses'));})}>Reabrir</button>}{operator&&b.estado!=='cerrado'&&<button className="ghost" aria-label={`Cerrar ${b.nombre}`} onClick={()=>setDeleting(b)} disabled={session.busy||!!draft}><Icon name="trash"/></button>}</li>)}</ul>}
      {deleting&&<div className="business-delete" role="alert"><strong>¿Cerrar {deleting.nombre}?</strong><p>Se desactivarán sus accesos. Sus métricas y ventas se conservan para consultar el historial.</p><div><button onClick={()=>setDeleting(null)}>Cancelar</button><button className="danger" disabled={session.busy} onClick={()=>void session.action(async()=>{const r=await session.post('businesses',{action:'delete',id:deleting.id,projectId:session.projects.active});setItems(r.negocios);session.setConfig(r.config);setDeleting(null);window.dispatchEvent(new Event('aero:businesses'));session.setNotice('Negocio cerrado; historial conservado.');})}>Cerrar negocio</button></div></div>}
    </section><section className="aero-panel business-editor">
      <div className="business-editor-head"><div><h2>{draft?(operator?'Configurar negocio':'Detalle del negocio'):'Negocios en el plano'}</h2><p>{draft?'El local identifica el negocio. Sus accesos se miden con las líneas de las cámaras.':'Busca una tienda o selecciona su icono en el mapa. Añade un negocio solo si falta en el plano.'}</p></div><label>Nivel del mapa<select value={plan} onChange={e=>requestNavigate(e.target.value)}>{Object.entries(plans).sort(([a],[b])=>a.localeCompare(b,undefined,{numeric:true})).map(([id,p])=><option key={id} value={id}>{p.floor||id}</option>)}</select></label></div>
      {pending&&<div className="business-switch" role="alert"><strong>Tienes cambios sin guardar.</strong><p>Guárdalos o descártalos para cambiar de selección.</p><div><button onClick={()=>setPending(null)}>Seguir editando</button><button onClick={()=>navigate(pending)}>Descartar y continuar</button><button className="primary" disabled={session.busy||!draft?.nombre.trim()||!draft?.ubicacion} onClick={()=>void save(pending)}>Guardar y continuar</button></div></div>}
      {draft&&<div className="business-save"><span>{draft.ubicacion?'Ubicación definida':'Falta ubicar el negocio'} · {draft.puertas.length} accesos</span><button onClick={()=>{setDraft(null);setPending(null);setPlacing(false);}}>{operator?'Cancelar cambios':'Cerrar detalle'}</button>{operator&&<button className="primary" disabled={session.busy||!draft.nombre.trim()||!draft.ubicacion} onClick={()=>void save()}>Guardar negocio</button>}</div>}
      <div className="business-editor-body">
      {draft&&<div className="business-fields">
        <label>Nombre del negocio<input maxLength={120} value={draft.nombre} disabled={!operator} onChange={e=>setDraft({...draft,nombre:e.target.value})} placeholder="Por ejemplo, Duty Free"/></label><p>{draft.referencia?'Tienda existente: cambia el nombre y pulsa Guardar negocio. El icono del plano se conserva.':'Nuevo negocio: escribe su nombre, coloca su icono en el mapa y pulsa Guardar negocio. Puedes vincular su cámara después.'}</p>

      </div>}
      {draft&&!draft.referencia&&<section className="business-location"><h3>Ubicación del nuevo negocio</h3>
        <p>Selecciona una tienda del mapa para reutilizar su ubicación. Si no aparece, crea una ubicación propia.</p>
        {mapError&&<p role="alert">{mapError}</p>}
        <div className="business-location-controls"><label>Local existente en el mapa<select disabled={!operator||!places.length} value={selectedPlace?.id||''} onChange={e=>{const p=places.find(p=>p.id===e.target.value);if(p)selectPlace(p);}}><option value="">{places.length?'Seleccionar local…':'Este plano no tiene locales disponibles'}</option>{places.sort((a,b)=>a.name.localeCompare(b.name)).map(p=><option key={p.id} value={p.id}>{p.name}{places.filter(q=>q.name===p.name).length>1?` (local ${places.filter(q=>q.name===p.name).findIndex(q=>q.id===p.id)+1})`:''}</option>)}</select></label>
        {operator&&<button className={placing?'selected':''} onClick={()=>{setPlacing(v=>!v);if(draft.referencia)setDraft({...draft,referencia:null});}}><Icon name="pin"/>{placing?'Cancelar ubicación':draft.referencia?'Usar ubicación propia':draft.ubicacion?'Reubicar en el plano':'Crear ubicación propia'}</button>}</div>
        <p className="business-location-status">{placing?'Haz clic para colocar el negocio. Luego arrastra su marcador para ajustar la posición.':draft.referencia?`Vinculado a ${selectedPlace?.name||'un local del mapa'}. Se conserva el icono original.`:draft.ubicacion?'Ubicación propia: arrastra el marcador para ajustarlo. Los cambios se aplican al guardar.':'Puedes elegir el local en la lista o pulsar su icono al acercarte al mapa.'}</p>
      </section>}
      <MapCanvas config={mapConfig} state={EMPTY_STATE} connected={session.connected} configuration selectedCamera={cameraId} onCamera={id=>setCameraId(id)} businessMarkers={[...items.filter(b=>b.id!==draft?.id),...(draft?.ubicacion?[draft]:[])]} editableBusinessId={operator?draft?.id:undefined} onBusinessMove={operator&&draft&&!draft.referencia?p=>setDraft(d=>d?{...d,ubicacion:{planId:plan,point:p}}:d):undefined} onBusinessPoint={placing&&operator?p=>{setDraft(d=>d?{...d,referencia:null,ubicacion:{planId:plan,point:p}}:d);setPlacing(false);}:undefined} onMapPlace={selectPlace} focusLocation={focus}/>
      {draft&&<><section className="business-access-editor"><h3>Accesos que mide este negocio</h3><p>Selecciona la cámara que ve esta puerta. Si ya tiene una línea, márcala debajo. Si falta, dibújala sobre la imagen de la cámara.</p>
        <label>Cámara del acceso<select value={cameraId} onChange={e=>setCameraId(e.target.value)}><option value="">Seleccionar cámara…</option>{cameras.map(c=><option key={c.id} value={c.id}>{c.name||c.id} ({c.countLines?.length||0} líneas)</option>)}</select></label>
        {operator&&camera&&<button className="primary" disabled={!items.some(b=>b.id===draft.id)} onClick={()=>setAccessEditor(v=>!v)}>{accessEditor?'Cerrar editor de puerta':'Dibujar o editar la puerta en esta cámara'}</button>}
        {!items.some(b=>b.id===draft.id)&&<p>Guarda primero el nuevo negocio; después podrás dibujar y vincular su puerta.</p>}
        {accessEditor&&camera&&<CameraAccessEditor key={camera.id} camera={camera} config={config} session={session} defaultBusiness={draft} embedded onChange={next=>{session.setConfig(next);const links=(next.cameras.find(c=>c.id===camera.id)?.countLines||[]).filter(l=>l.place?.id===draft.id).map(l=>({camaraId:camera.id,lineaId:l.id}));setDraft({...draft,puertas:[...draft.puertas.filter(p=>p.camaraId!==camera.id),...links]});}}/>}
        {camera&&<fieldset className="business-doors"><legend>Líneas de {camera.name||camera.id}</legend>{!doors.length&&<p>Esta cámara no tiene líneas. Configúralas primero en Configurar proyecto.</p>}{doors.map(d=>{const checked=draft.puertas.some(p=>p.camaraId===d.camaraId&&p.lineaId===d.lineaId);const owner=items.find(b=>b.id!==draft.id&&b.puertas.some(p=>p.camaraId===d.camaraId&&p.lineaId===d.lineaId));return <label key={d.lineaId}><input type="checkbox" checked={checked} disabled={!operator||!!owner} onChange={()=>setDraft({...draft,puertas:checked?draft.puertas.filter(p=>!(p.camaraId===d.camaraId&&p.lineaId===d.lineaId)):[...draft.puertas,{camaraId:d.camaraId,lineaId:d.lineaId}]})}/><span>{d.label}{owner&&<small>Vinculado a {owner.nombre}</small>}</span></label>;})}</fieldset>}
        <div className="business-linked-accesses"><h4>Accesos vinculados ({draft.puertas.length})</h4>{!draft.puertas.length?<p>El negocio se puede guardar y completar después. Sin accesos no se medirá su tráfico.</p>:draft.puertas.map(d=>{const c=config.cameras.find(c=>c.id===d.camaraId),l=c?.countLines?.find(l=>l.id===d.lineaId);return <div key={d.camaraId+d.lineaId}><span><strong>{c?.name||d.camaraId}</strong><small>{l?.name||'Línea eliminada: retira este vínculo antes de guardar'}</small></span>{operator&&<button aria-label={`Quitar acceso ${l?.name||d.lineaId}`} onClick={()=>setDraft({...draft,puertas:draft.puertas.filter(p=>p!==d)})}>Quitar</button>}</div>;})}</div>
        <aside className="business-measurement-note"><Icon name="chart"/><p>Las entradas y salidas se obtienen de estos accesos. La ubicación del local sirve para encontrarlos en el mapa; no define un radio de detección. Para medir aglomeraciones alrededor del negocio se configura una zona de interés independiente.</p></aside>
      </section></>}
      </div>
    </section></div>
    <BusinessResults/>
  </div>;
}
