import { useEffect, useRef, useState } from 'react';
import type { Camera, Config, Point } from './types';
import { COLORS, isActive, freshCamera } from './types';
import type { Session } from './useSession';
import MapCanvas from './MapCanvas';
import type { MapTool } from './MapCanvas';
import { CameraVideo } from './CameraPanel';
import {CameraEditor} from './CameraPanel';
import './plan-workspace.css';
import CameraRegionEditor from './CameraRegionEditor';

type Section='area'|'cameras'|'calibration';

export default function PlanWorkspace({session,selected,onSelected,startTest,section:controlled,embedded}:{session:Session;selected:string;onSelected:(id:string)=>void;startTest:()=>void;section?:Section;embedded?:boolean}) {
  const config=session.config!;
  const samePlan=(c:Camera)=>(c.planId||'custom')===(config.planId||'custom');
  const camera=config.cameras.find(c=>c.id===selected&&samePlan(c));
  const disabled=isActive(session.state.status);
  const [innerSection,setSection]=useState<Section>('cameras');
  const section=controlled??innerSection;
  const [tool,setTool]=useState<MapTool>('select');
  const [areaEditing,setAreaEditing]=useState(!config.workArea?.length);
  const [area,setArea]=useState<Point[]>(config.workArea||[]);
  const [template,setTemplate]=useState(true);
  const [pending,setPending]=useState<Point|null>(null);
  const [copied,setCopied]=useState<Partial<Camera>|null>(null);
  const [scaleDistance,setScaleDistance]=useState(1);
  const [check,setCheck]=useState<{rmse:number;spread:number;validationError?:number|null;warning?:string}|null>(null);
  const referencesKey=JSON.stringify(camera?.pairs);
  useEffect(()=>{setCheck(null);},[camera?.id,referencesKey]);
  const [sourceOpen,setSourceOpen]=useState(false);
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(sourceOpen)dialog.current?.showModal();else dialog.current?.close();},[sourceOpen]);
  const file=useRef<HTMLInputElement>(null);
  useEffect(()=>{setArea(config.workArea||[]);setAreaEditing(!config.workArea?.length&&!config.mapAsset);setPending(null);setCheck(null);},[config.planId]);
  useEffect(()=>{if(!config.workArea?.length){setArea([]);if(config.mapAsset){setAreaEditing(false);setTool('select');}}},[JSON.stringify(config.workArea)]);
  const update=(patch:Partial<Config>)=>session.setConfig({...config,...patch});
  const patchCamera=(patch:Partial<Camera>)=>update({cameras:config.cameras.map(c=>c.id===selected?{...c,...patch}:c)});
  const save=(value=config)=>void session.action(async()=>{
    if(section==='area'&&areaEditing){
      if(area.length<3)throw Error('Completa al menos tres puntos del área antes de guardar.');
      value={...value,workArea:area,mapConfigured:true};
    }
    await session.save(value);setAreaEditing(false);session.setNotice('Plano y configuración guardados.');
  });
  function pickSection(value:Section){setSection(value);setTool(value==='calibration'?'calibrate':'select');setPending(null);}
  function changeArea(points:Point[]){setArea(points);if(points.length>=3)update({workArea:points,mapConfigured:true});}
  function clearArea(){
    const plans={...config.plans};
    if(config.planId&&plans[config.planId])plans[config.planId]={...plans[config.planId],workArea:undefined};
    update({workArea:undefined,plans});setArea([]);setAreaEditing(false);setTool('select');
    session.setNotice('Área de trabajo quitada. Guarda la configuración para conservar el cambio. Las cámaras y sus zonas útiles se mantienen.');
  }
  function confirmArea(){
    if(area.length<3)return;
    const next={...config,workArea:area,mapConfigured:true};
    void session.action(async()=>{await session.save(next);session.setConfig(next);setAreaEditing(false);setTool('select');session.setNotice(config.mapAsset?'Área de referencia guardada. El mapa LAP se mantiene completo.':'Área de trabajo guardada. El exterior queda excluido en este plano personalizado.');});
  }
  async function vectorize(background:string){const blob=await (await fetch(background)).blob();return session.post(`plan-lines?width=${config.width}`,blob,true);}
  function importFile(selectedFile:File){void session.action(async()=>{
    const imported=await session.post(`import-plan?name=${encodeURIComponent(selectedFile.name)}&width=${config.width}&page=0`,selectedFile,true);
    const result=await vectorize(imported.background);
    update({background:imported.background,planLines:result.planLines,width:result.width,height:result.height,planName:selectedFile.name,mapConfigured:true,workArea:undefined,zones:[],cameras:config.cameras.map(c=>!samePlan(c)?c:({...c,x:Math.min(c.x,result.width),y:Math.min(c.y,result.height),pairs:[],coveragePolygon:undefined})),importWarnings:result.warnings});
    setArea([]);setAreaEditing(true);setTemplate(false);setCheck(null);session.setNotice('Plantilla convertida a líneas. Selecciona el área de trabajo y calibra sus referencias.');
  });}
  function calibrate(){if(!camera)return;void session.action(async()=>{const result=await session.post('calibration-check',{pairs:camera.pairs});await session.save();setCheck(result);session.setNotice('Referencias validadas y guardadas. Ya puedes iniciar el monitoreo; revisa su precisión con puntos adicionales.');});}
  const distance=camera&&camera.pairs.length>=2?Math.hypot(camera.pairs[1][2]-camera.pairs[0][2],camera.pairs[1][3]-camera.pairs[0][3]):0;
  function setScale(){
    if(config.mapAsset||!distance||!Number.isFinite(scaleDistance)||scaleDistance<=0)return;
    const k=scaleDistance/distance, point=(p:Point):Point=>[p[0]*k,p[1]*k];
    update({unit:'meters',width:config.width*k,height:config.height*k,workArea:config.workArea?.map(point),radius:config.radius*k,matchDistance:config.matchDistance*k,zones:config.zones.map(z=>({...z,points:z.points.map(point)})),cameras:config.cameras.map(c=>!samePlan(c)?c:({...c,x:c.x*k,y:c.y*k,range:(c.range??3)*k,coverageWidth:(c.coverageWidth??2)*k,coveragePolygon:c.coveragePolygon?.map(point),pairs:c.pairs.map(p=>[p[0],p[1],p[2]*k,p[3]*k])}))});setArea(area.map(point));setCheck(null);
  }
  const unit=config.unit==='meters'?'m':'u';
  useEffect(()=>{if(controlled){setTool(controlled==='calibration'?'calibrate':'select');setPending(null);}},[controlled]);
  return <section className="plan-workspace">
    <dialog ref={dialog} className="camera-source-dialog" onCancel={()=>setSourceOpen(false)}><div className="panel-heading"><h2>{camera?.name} · Fuente y área de análisis</h2><div className="inline"><span>{session.dirty?'Cambios sin guardar':'Guardado'}</span><button className="primary" disabled={disabled||session.busy||!session.dirty} onClick={()=>void session.action(async()=>{await session.save();session.setNotice('Configuración guardada.');})}>Guardar configuración</button><button onClick={()=>setSourceOpen(false)}>Cerrar editor</button></div></div>{session.busy&&<p role="status">Guardando u obteniendo imagen…</p>}{session.error&&<p role="alert" className="notice error">{session.error}</p>}{session.notice&&<p role="status" className="notice">{session.notice}</p>}{sourceOpen&&<CameraEditor camera={camera} config={config} session={session} onChange={session.setConfig}/>}</dialog>
    {!embedded&&<header className="cad-head"><div><span className="eyebrow">EDITOR DEL ESPACIO</span><h2>{config.floor||'Plano principal'}</h2></div><div className="inline"><span className="pill">{session.dirty?'Cambios sin guardar':'Guardado'}</span><button className="primary" disabled={disabled||session.busy} onClick={()=>save()}>Guardar plano</button></div></header>}
    {embedded
      ? <nav className="cad-tabs"><label className="check"><input type="checkbox" checked={template} onChange={e=>setTemplate(e.target.checked)}/> Ver plantilla de fondo</label></nav>
      : <nav className="cad-tabs">{([['cameras','1 · Ubicación y cámara'],['calibration','2 · Referencias del suelo'],['area','Área de trabajo (opcional)']] as const).map(([id,label])=><button key={id} className={section===id?'selected':''} onClick={()=>pickSection(id)}>{label}</button>)}<label className="check"><input type="checkbox" checked={template} onChange={e=>setTemplate(e.target.checked)}/> Ver plantilla</label></nav>}
    <p className="cad-help" hidden={section==='area'}>Arrastra el icono para mover la cámara. Arrastra el punto frontal para girar y cambiar alcance; los cuadrados ajustan ancho y longitud. El rectángulo es cobertura orientativa, no calibración.</p>
    {section==='calibration'&&<div className="notice"><strong>¿Para qué sirven las referencias?</strong><p>Relacionan posiciones del suelo del video con el plano. 1. Marca una esquina o cruce de baldosas en el suelo del video. 2. Marca ese mismo lugar en el mapa. 3. Repite con al menos cuatro puntos repartidos y pulsa «Validar y guardar referencias». No marques cabezas ni esquinas arbitrarias del encuadre. Arrastra una referencia para corregirla; selecciónala para eliminarla. Con cinco o más puntos también se comprueba cada referencia dejándola fuera del ajuste.</p>{pending&&<button onClick={()=>setPending(null)}>Cancelar punto pendiente</button>}</div>}
    {disabled&&<div className="notice compact">Finaliza la sesión para editar geometría. Las vistas siguen disponibles.</div>}
    <div className={`cad-body ${section==='calibration'?'with-video':''}`}>
      <div className="cad-canvas"><div className="cad-tools">
        {(section==='area'?([['work-rect','Rectángulo'],['work-poly','Polígono / puntos'],['work-edit','Ajustar bordes'],['line','Trazar línea'],['erase','Borrar línea']] as const):section==='cameras'?([['camera','Colocar cámara'],['move','Mover'],['coverage','Cobertura libre']] as const):([] as const)).map(([id,label])=><button key={id} title={label} disabled={disabled} className={tool===id?'on':''} onClick={()=>{setTool(id);if(id.startsWith('work'))setAreaEditing(true);}}>{label}</button>)}
        {section==='area'&&areaEditing&&<><button disabled={disabled||area.length<3||session.busy} className="primary" onClick={confirmArea}>Usar esta área</button><button disabled={!area.length||disabled} onClick={()=>setArea(area.slice(0,-1))}>Deshacer punto</button></>}
        {section==='calibration'&&<span>{pending?'Ahora selecciona el mismo punto en el plano':'Selecciona un punto del suelo en el video'}</span>}
      </div>
      <MapCanvas key={config.planId||'custom'} config={config} state={session.state} connected={session.connected} configuration editable={!disabled} selectedCamera={selected} onCamera={onSelected} onChange={session.setConfig} tool={tool} onTool={setTool} template={template} areaDraft={area} onAreaDraft={changeArea} areaEditing={areaEditing} onCalibrationPoint={p=>{if(!pending||!camera)return;patchCamera({pairs:[...camera.pairs,[...pending,...p]]});setPending(null);setCheck(null);}}/>
      <footer className="cad-status"><span>{(config.planLines||[]).length} líneas · {config.workArea?.length||0} nodos de área</span><span>{config.mapAsset?'Escala cartográfica de referencia':config.unit==='meters'?'Escala medida':'Escala relativa'} · Rueda: zoom · Arrastrar: desplazar</span></footer></div>
      <aside className="cad-inspector">
        {section==='area'?<><h3>Área de trabajo</h3><p>{config.mapAsset?'En LAP esta selección es una referencia opcional de trabajo: no recorta el mapa ni limita las detecciones. Para analizar una parte del video, configura la zona útil de la cámara.':areaEditing?'Selecciona puntos o dos esquinas. Esta área limita el plano personalizado y su análisis.':config.workArea?.length?'Área activa en este plano personalizado. Puedes quitarla para recuperar el plano completo.':'Sin área de trabajo: se utiliza el plano completo.'}</p><button disabled={disabled} onClick={()=>{setAreaEditing(true);setArea(config.workArea||[]);setTool('work-edit');}}>Cambiar selección</button><button disabled={disabled||area.length<3||session.busy} onClick={confirmArea}>Guardar zona</button><button disabled={disabled||session.busy||(!area.length&&!config.workArea?.length)} onClick={clearArea}>Quitar área de trabajo</button><small>Quita solo esta selección; conserva las cámaras, la calibración y las zonas de interés.</small><hr/><h3>Plantilla y trazos</h3><button disabled={disabled||!!config.mapAsset||session.busy} onClick={()=>file.current?.click()}>Importar plantilla</button><input hidden ref={file} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,.dxf,.dwg" onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)importFile(f);}}/><button disabled={disabled||!config.background||session.busy} onClick={()=>void session.action(async()=>{const r=await vectorize(config.background);update({planLines:r.planLines});session.setNotice('Líneas regeneradas; las coordenadas y la calibración se conservan.');})}>Regenerar líneas</button><button disabled={disabled||session.busy||(!config.background&&!(config.planLines||[]).length)} className="danger ghost" onClick={()=>{if(!confirm('Se quitará el plano importado de este proyecto (imagen y líneas). Las cámaras, zonas y calibración se conservan.'))return;update({background:'',planLines:[],planName:undefined});session.setNotice('Plano importado quitado. Puedes importar otro o dibujarlo con las figuras.');}}>Quitar plano importado</button><small>La plantilla solo se muestra al activar «Ver plantilla». Revisa los trazos extraídos antes de calibrar.</small><label>Ancho ({unit})<input disabled={disabled||!!config.mapAsset||!!config.workArea?.length||config.cameras.some(c=>c.pairs.length>0)} type="number" min="1" value={config.width} onChange={e=>update({width:+e.target.value})}/></label><label>Alto ({unit})<input disabled={disabled||!!config.mapAsset||!!config.workArea?.length||config.cameras.some(c=>c.pairs.length>0)} type="number" min="1" value={config.height} onChange={e=>update({height:+e.target.value})}/></label></>:<>
          <button disabled={disabled} onClick={()=>{const c=freshCamera();c.name=`Cámara ${config.cameras.length+1}`;c.planId=config.planId;c.x=config.width/2;c.y=config.height/2;c.range=12;c.coverageWidth=10;update({cameras:[...config.cameras,c]});onSelected(c.id);setSection('cameras');}}>+ Agregar cámara en este nivel</button><label>Cámara<select value={selected} onChange={e=>{onSelected(e.target.value);setPending(null);setCheck(null);}}>{config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom')).map(c=><option value={c.id} key={c.id}>{c.name||c.id}</option>)}</select></label>
          {camera&&section==='cameras'&&<><button onClick={()=>setSourceOpen(true)}>Editar fuente, zona útil y accesos</button><div className="cad-camera-list">{config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom')).map((c,i)=><button key={c.id} className={c.id===selected?'selected':''} onClick={()=>onSelected(c.id)}><i style={{background:c.color||COLORS[i%COLORS.length]}}/>{c.name||c.id}<small>{c.active===false?'Inactiva':`${Math.round(c.heading??90)}°`}</small></button>)}</div><label>Nombre<input disabled={disabled} value={camera.name||camera.id} onChange={e=>patchCamera({name:e.target.value})}/></label><label>Color<input disabled={disabled} type="color" value={camera.color||COLORS[config.cameras.indexOf(camera)%COLORS.length]} onChange={e=>patchCamera({color:e.target.value})}/></label><label className="check"><input disabled={disabled} type="checkbox" checked={camera.active!==false} onChange={e=>patchCamera({active:e.target.checked})}/> Cámara activa</label><label>Cobertura orientativa sobre el suelo<select disabled={disabled} value={camera.coverageShape||'cone'} onChange={e=>patchCamera({coverageShape:e.target.value as Camera['coverageShape']})}><option value="cone">Sector de visión (orientativo)</option><option value="rectangle">Rectángulo</option><option value="free">Polígono</option></select></label>
          {([['heading','Dirección (°)',0,360],['fov','Ángulo (°)',5,170],['range',`Alcance (${unit})`,.01,10000],['height','Altura (m)',0,10000]] as const).filter(([field])=>field!=='fov'||camera.coverageShape==='cone').map(([field,label,min,max])=><label key={field}>{label}<input disabled={disabled} type="number" step={field==='heading'?5:1} min={min} max={max} value={Number((camera[field]??(field==='fov'?60:field==='heading'?90:3)).toFixed(2))} onChange={e=>patchCamera({[field]:+e.target.value})}/></label>)}
          {camera.coverageShape==='rectangle'&&<label>Ancho de cobertura ({unit})<input disabled={disabled} type="number" min="0.01" step="0.1" value={Number((camera.coverageWidth??2).toFixed(2))} onChange={e=>patchCamera({coverageWidth:+e.target.value})}/></label>}
          <label className="check"><input disabled={disabled} type="checkbox" checked={!!camera.restrictCoverage} onChange={e=>patchCamera({restrictCoverage:e.target.checked})}/> Limitar detecciones a esta cobertura</label><small>Requiere calibración del suelo. Marca también la zona útil del video para excluir espejos.</small>
          <button disabled={disabled} onClick={()=>setCopied({heading:camera.heading,fov:camera.fov,range:camera.range,height:camera.height,coverageShape:camera.coverageShape==='free'?'cone':camera.coverageShape,coverageWidth:camera.coverageWidth})}>Copiar parámetros</button><button disabled={disabled||!copied} onClick={()=>copied&&patchCamera(copied)}>Pegar parámetros</button></>}
          {camera&&section==='calibration'&&<><CameraVideo camera={camera} state={session.state} connected={session.connected} mode={disabled?undefined:'calibration'} pending={pending} zonePoints={camera.detectionZone} pairPoints={camera.pairs.map(p=>[p[0],p[1]])} onPairChange={disabled?undefined:(i,p)=>{patchCamera({pairs:camera.pairs.map((v,j)=>i===j?[p[0],p[1],v[2],v[3]]:v)});setCheck(null);}} onPoint={p=>{setPending(p);setTool('calibrate');}}/><button disabled={disabled} onClick={startTest}>Ver imagen inicial para calibrar</button>
          <div className="cad-nodes">{camera.pairs.map((p,i)=><div key={i}><i style={{background:COLORS[i%COLORS.length]}}/>{i+1}<span>X {p[2].toFixed(2)} · Y {p[3].toFixed(2)}</span><button disabled={disabled} title={`Eliminar nodo ${i+1}`} onClick={()=>{patchCamera({pairs:camera.pairs.filter((_,n)=>n!==i)});setCheck(null);}}>×</button></div>)}</div>
          {!config.mapAsset&&<><span>Distancia 1–2: {distance.toFixed(3)} {unit}</span><label>Distancia real 1–2 (m)<input disabled={disabled} type="number" min="0.001" step="0.1" value={scaleDistance} onChange={e=>setScaleDistance(+e.target.value)}/></label><button disabled={disabled||!!config.mapAsset||!distance} onClick={setScale}>Aplicar escala medida</button></>}<button disabled={disabled||camera.pairs.length<4||session.busy} onClick={calibrate}>Validar y guardar referencias</button>{check&&<p role="status">Ajuste RMSE: {check.rmse.toFixed(4)} {unit} · distribución: {(check.spread*100).toFixed(1)}% de imagen. {check.validationError!=null?`Comprobación fuera del ajuste: ${check.validationError.toFixed(3)} ${unit}. `:'Cuatro pares no validan precisión por sí solos. '}{check.warning}</p>}<details><summary>Editar zona útil de esta cámara</summary><CameraRegionEditor key={camera.id} camera={camera} config={config} session={session} onChange={session.setConfig}/></details></>}
        </>}
      </aside>
    </div>
  </section>;
}
