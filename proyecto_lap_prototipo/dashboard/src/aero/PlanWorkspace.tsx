import { useRef, useState } from 'react';
import type { Camera, Config, Point } from './types';
import { COLORS, isActive } from './types';
import type { Session } from './useSession';
import MapCanvas from './MapCanvas';
import type { MapTool } from './MapCanvas';
import { CameraVideo } from './CameraPanel';
import './plan-workspace.css';

export default function PlanWorkspace({session,selected,onSelected,startTest}:{session:Session;selected:string;onSelected:(id:string)=>void;startTest:()=>void}) {
  const config=session.config!;
  const camera=config.cameras.find(c=>c.id===selected);
  const disabled=isActive(session.state.status);
  const [section,setSection]=useState<'area'|'cameras'|'calibration'>('area');
  const [tool,setTool]=useState<MapTool>('select');
  const [areaEditing,setAreaEditing]=useState(!config.workArea?.length);
  const [area,setArea]=useState<Point[]>(config.workArea||[]);
  const [template,setTemplate]=useState(false);
  const [pending,setPending]=useState<Point|null>(null);
  const [zone,setZone]=useState<Point[]>([]);
  const [zoneMode,setZoneMode]=useState(false);
  const [copied,setCopied]=useState<Partial<Camera>|null>(null);
  const [scaleDistance,setScaleDistance]=useState(1);
  const [check,setCheck]=useState<{rmse:number;spread:number}|null>(null);
  const file=useRef<HTMLInputElement>(null);
  const update=(patch:Partial<Config>)=>session.setConfig({...config,...patch});
  const patchCamera=(patch:Partial<Camera>)=>update({cameras:config.cameras.map(c=>c.id===selected?{...c,...patch}:c)});
  const save=(value=config)=>void session.action(async()=>{await session.save(value);session.setNotice('Configuración guardada.');});
  function pickSection(value:typeof section){setSection(value);setTool(value==='calibration'?'calibrate':'select');setPending(null);setZoneMode(false);}
  function confirmArea(){
    if(area.length<3)return;
    const next={...config,workArea:area,mapConfigured:true};
    void session.action(async()=>{await session.save(next);session.setConfig(next);setAreaEditing(false);setTool('select');session.setNotice('Área activa guardada. El exterior queda excluido del plano y del análisis.');});
  }
  async function vectorize(background:string){const blob=await (await fetch(background)).blob();return session.post(`plan-lines?width=${config.width}`,blob,true);}
  function importFile(selectedFile:File){void session.action(async()=>{
    const imported=await session.post(`import-plan?name=${encodeURIComponent(selectedFile.name)}&width=${config.width}&page=0`,selectedFile,true);
    const result=await vectorize(imported.background);
    update({background:imported.background,planLines:result.planLines,width:result.width,height:result.height,planName:selectedFile.name,mapConfigured:true,workArea:undefined,zones:[],cameras:config.cameras.map(c=>({...c,x:Math.min(c.x,result.width),y:Math.min(c.y,result.height),pairs:[],coveragePolygon:undefined})),importWarnings:result.warnings});
    setArea([]);setAreaEditing(true);setTemplate(false);setCheck(null);session.setNotice('Plantilla convertida a líneas. Selecciona el área de trabajo y calibra sus referencias.');
  });}
  function calibrate(){if(!camera)return;void session.action(async()=>{const result=await session.post('calibration-check',{pairs:camera.pairs});setCheck(result);session.setNotice('Transformación ajustada con todos los pares. Revisa el error antes de guardar.');});}
  const distance=camera&&camera.pairs.length>=2?Math.hypot(camera.pairs[1][2]-camera.pairs[0][2],camera.pairs[1][3]-camera.pairs[0][3]):0;
  function setScale(){
    if(!distance||!Number.isFinite(scaleDistance)||scaleDistance<=0)return;
    const k=scaleDistance/distance, point=(p:Point):Point=>[p[0]*k,p[1]*k];
    update({unit:'meters',width:config.width*k,height:config.height*k,workArea:config.workArea?.map(point),radius:config.radius*k,matchDistance:config.matchDistance*k,zones:config.zones.map(z=>({...z,points:z.points.map(point)})),cameras:config.cameras.map(c=>({...c,x:c.x*k,y:c.y*k,range:(c.range??3)*k,coverageWidth:(c.coverageWidth??2)*k,coveragePolygon:c.coveragePolygon?.map(point),pairs:c.pairs.map(p=>[p[0],p[1],p[2]*k,p[3]*k])}))});setArea(area.map(point));setCheck(null);
  }
  const unit=config.unit==='meters'?'m':'u';
  return <section className="plan-workspace">
    <header className="cad-head"><div><span className="eyebrow">EDITOR DEL ESPACIO</span><h2>{config.floor||'Plano principal'}</h2></div><div className="inline"><span className="pill">{session.dirty?'Cambios sin guardar':'Guardado'}</span><button className="primary" disabled={disabled||session.busy} onClick={()=>save()}>Guardar plano</button></div></header>
    <nav className="cad-tabs">{([['area','01 · Área de trabajo'],['cameras','02 · Cámaras'],['calibration','03 · Calibración']] as const).map(([id,label])=><button key={id} className={section===id?'selected':''} onClick={()=>pickSection(id)}>{label}</button>)}<label className="check"><input type="checkbox" checked={template} onChange={e=>setTemplate(e.target.checked)}/> Ver plantilla</label></nav>
    {disabled&&<div className="notice compact">Finaliza la sesión para editar geometría. Las vistas siguen disponibles.</div>}
    <div className={`cad-body ${section==='calibration'?'with-video':''}`}>
      <div className="cad-canvas"><div className="cad-tools">
        {(section==='area'?([['work-rect','Rectángulo'],['work-poly','Polígono / puntos'],['work-edit','Ajustar bordes'],['line','Trazar línea'],['erase','Borrar línea']] as const):section==='cameras'?([['camera','Colocar cámara'],['move','Mover'],['coverage','Cobertura libre']] as const):([] as const)).map(([id,label])=><button key={id} title={label} disabled={disabled} className={tool===id?'on':''} onClick={()=>{setTool(id);if(id.startsWith('work'))setAreaEditing(true);}}>{label}</button>)}
        {section==='area'&&areaEditing&&<><button disabled={disabled||area.length<3||session.busy} className="primary" onClick={confirmArea}>Usar esta área</button><button disabled={!area.length||disabled} onClick={()=>setArea(area.slice(0,-1))}>Deshacer punto</button></>}
        {section==='calibration'&&<span>{zoneMode?'Marca el contorno válido en el video':pending?'Ahora selecciona el mismo punto en el plano':'Selecciona un punto del suelo en el video'}</span>}
      </div>
      <MapCanvas config={config} state={session.state} connected={session.connected} editable={!disabled} selectedCamera={selected} onCamera={onSelected} onChange={session.setConfig} tool={tool} onTool={setTool} template={template} areaDraft={area} onAreaDraft={setArea} areaEditing={areaEditing} onCalibrationPoint={p=>{if(!pending||!camera)return;patchCamera({pairs:[...camera.pairs,[...pending,...p]]});setPending(null);setCheck(null);}}/>
      <footer className="cad-status"><span>{(config.planLines||[]).length} líneas · {config.workArea?.length||0} nodos de área</span><span>{config.unit==='meters'?'Escala medida':'Escala relativa'} · Rueda: zoom · Arrastrar: desplazar</span></footer></div>
      <aside className="cad-inspector">
        {section==='area'?<><h3>Área de trabajo</h3><p>{areaEditing?'Selecciona puntos o dos esquinas. Arrastra los nodos para ajustar.':'Área confirmada. El exterior está oculto.'}</p><button disabled={disabled} onClick={()=>{setAreaEditing(true);setArea(config.workArea||[]);setTool('work-edit');}}>Cambiar selección</button><button disabled={disabled||area.length<3||session.busy} onClick={confirmArea}>Guardar zona</button><hr/><h3>Plantilla y trazos</h3><button disabled={disabled||session.busy} onClick={()=>file.current?.click()}>Importar plantilla</button><input hidden ref={file} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,.dxf,.dwg" onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)importFile(f);}}/><button disabled={disabled||!config.background||session.busy} onClick={()=>void session.action(async()=>{const r=await vectorize(config.background);update({planLines:r.planLines});session.setNotice('Líneas regeneradas; las coordenadas y la calibración se conservan.');})}>Regenerar líneas</button><small>La plantilla solo se muestra al activar «Ver plantilla». Revisa los trazos extraídos antes de calibrar.</small><label>Ancho ({unit})<input disabled={disabled||!!config.workArea?.length||config.cameras.some(c=>c.pairs.length>0)} type="number" min="1" value={config.width} onChange={e=>update({width:+e.target.value})}/></label><label>Alto ({unit})<input disabled={disabled||!!config.workArea?.length||config.cameras.some(c=>c.pairs.length>0)} type="number" min="1" value={config.height} onChange={e=>update({height:+e.target.value})}/></label></>:<>
          <label>Cámara<select value={selected} onChange={e=>{onSelected(e.target.value);setPending(null);setZoneMode(false);setCheck(null);}}>{config.cameras.map(c=><option value={c.id} key={c.id}>{c.name||c.id}</option>)}</select></label>
          {camera&&section==='cameras'&&<><div className="cad-camera-list">{config.cameras.map((c,i)=><button key={c.id} className={c.id===selected?'selected':''} onClick={()=>onSelected(c.id)}><i style={{background:c.color||COLORS[i%COLORS.length]}}/>{c.name||c.id}<small>{c.active===false?'Inactiva':`${Math.round(c.heading??90)}°`}</small></button>)}</div><label>Nombre<input disabled={disabled} value={camera.name||camera.id} onChange={e=>patchCamera({name:e.target.value})}/></label><label>Color<input disabled={disabled} type="color" value={camera.color||COLORS[config.cameras.indexOf(camera)%COLORS.length]} onChange={e=>patchCamera({color:e.target.value})}/></label><label className="check"><input disabled={disabled} type="checkbox" checked={camera.active!==false} onChange={e=>patchCamera({active:e.target.checked})}/> Cámara activa</label><label>Forma<select disabled={disabled} value={camera.coverageShape||'cone'} onChange={e=>patchCamera({coverageShape:e.target.value as Camera['coverageShape']})}><option value="cone">Cono</option><option value="rectangle">Rectángulo</option><option value="free">Polígono</option></select></label>
          {([['heading','Dirección (°)',0,360],['fov','Ángulo (°)',5,170],['range',`Alcance (${unit})`,.01,10000],['height','Altura (m)',0,10000]] as const).map(([field,label,min,max])=><label key={field}>{label}<input disabled={disabled} type="number" step="0.1" min={min} max={max} value={Number((camera[field]??(field==='fov'?60:field==='heading'?90:3)).toFixed(2))} onChange={e=>patchCamera({[field]:+e.target.value})}/></label>)}
          {camera.coverageShape==='rectangle'&&<label>Ancho de cobertura ({unit})<input disabled={disabled} type="number" min="0.01" step="0.1" value={camera.coverageWidth??2} onChange={e=>patchCamera({coverageWidth:+e.target.value})}/></label>}
          <label className="check"><input disabled={disabled} type="checkbox" checked={!!camera.restrictCoverage} onChange={e=>patchCamera({restrictCoverage:e.target.checked})}/> Limitar detecciones a esta cobertura</label><small>Requiere calibración del suelo. Marca también la zona útil del video para excluir espejos.</small>
          <button disabled={disabled} onClick={()=>setCopied({heading:camera.heading,fov:camera.fov,range:camera.range,height:camera.height,coverageShape:camera.coverageShape==='free'?'cone':camera.coverageShape,coverageWidth:camera.coverageWidth})}>Copiar parámetros</button><button disabled={disabled||!copied} onClick={()=>copied&&patchCamera(copied)}>Pegar parámetros</button><button disabled={disabled||session.busy} onClick={()=>save()}>Guardar cámara</button></>}
          {camera&&section==='calibration'&&<><CameraVideo camera={camera} state={session.state} connected={session.connected} mode={disabled?undefined:zoneMode?'zone':'calibration'} pending={pending} zonePoints={zoneMode?zone:camera.detectionZone} pairPoints={camera.pairs.map(p=>[p[0],p[1]])} onPoint={p=>{if(zoneMode)setZone([...zone,p]);else {setPending(p);setTool('calibrate');}}}/><button disabled={disabled} onClick={startTest}>Obtener imagen de cámara</button>
          <div className="cad-nodes">{camera.pairs.map((p,i)=><div key={i}><i style={{background:COLORS[i%COLORS.length]}}/>{i+1}<span>X {p[2].toFixed(2)} · Y {p[3].toFixed(2)}</span><button disabled={disabled} title={`Eliminar nodo ${i+1}`} onClick={()=>{patchCamera({pairs:camera.pairs.filter((_,n)=>n!==i)});setCheck(null);}}>×</button></div>)}</div>
          <span>Distancia 1–2: {distance.toFixed(3)} {unit}</span><label>Distancia real 1–2 (m)<input disabled={disabled} type="number" min="0.001" step="0.1" value={scaleDistance} onChange={e=>setScaleDistance(+e.target.value)}/></label><button disabled={disabled||!distance} onClick={setScale}>Aplicar escala medida</button><button disabled={disabled||camera.pairs.length<4||session.busy} onClick={calibrate}>Calibrar plano</button>{check&&<p role="status">Ajuste RMSE: {check.rmse.toFixed(4)} {unit} · distribución: {(check.spread*100).toFixed(1)}% de imagen. Los pares de cuatro puntos no validan precisión por sí solos.</p>}<button disabled={disabled||camera.pairs.length<4||session.busy} onClick={()=>save()}>Guardar calibración</button><hr/><h3>Excluir espejos y exterior</h3><button disabled={disabled} onClick={()=>{setZoneMode(true);setZone(camera.detectionZone||[]);}}>Marcar zona útil en video</button>{zoneMode&&<><span>{zone.length} vértices</span><button disabled={disabled||!zone.length} onClick={()=>setZone(zone.slice(0,-1))}>Deshacer vértice</button><button disabled={disabled||zone.length<3||session.busy} onClick={()=>{const next={...config,cameras:config.cameras.map(c=>c.id===selected?{...c,detectionZone:zone}:c)};void session.action(async()=>{await session.save(next);session.setConfig(next);setZoneMode(false);session.setNotice('Zona útil guardada: los IDs se crean únicamente dentro de ella.');});}}>Guardar zona útil</button></>}</>}
        </>}
      </aside>
    </div>
  </section>;
}
