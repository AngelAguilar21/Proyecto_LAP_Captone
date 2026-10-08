import PersonPairs from './PersonPairs';
import { useEffect, useRef, useState } from 'react';
import type { Camera, Config, Point } from './types';
import { COLORS, freshCamera, isActive } from './types';
import type { Session } from './useSession';
import MapCanvas from './MapCanvas';
import type { MapTool } from './MapCanvas';
import { CameraEditor, CameraVideo } from './CameraPanel';
import { calibrationMessage } from './calibration';
import './plan-workspace.css';

type Section = 'area' | 'cameras' | 'calibration';
// Dos partes con su propio modo: en A solo se marcan puntos del suelo (homografía); en B solo los pies de la misma persona
// en dos cámaras (relaciona las cámaras y mide su desfase de tiempo). Cambiar de parte cancela lo que quedó a medias.
type Part = 'suelo' | 'personas';
const PARTS: [Part, string][] = [['suelo', 'A · Puntos del suelo'], ['personas', 'B · La misma persona en dos cámaras']];

interface Props {
  session: Session;
  selected: string;
  onSelected: (id: string) => void;
  startTest: () => void;
  section?: Section;
  embedded?: boolean;
}

export default function PlanWorkspace({ session, selected, onSelected, startTest, section: controlled, embedded }: Props) {
  const config = session.config!;
  const disabled = isActive(session.state.status);
  const samePlan = (camera: Camera) => (camera.planId || 'custom') === (config.planId || 'custom');
  const cameras = config.cameras.filter(samePlan);
  const camera = cameras.find(item => item.id === selected);
  const [innerSection, setInnerSection] = useState<Section>('cameras');
  const [part, setPart] = useState<Part>('suelo');
  const section = controlled ?? innerSection;
  const [tool, setTool] = useState<MapTool>(section === 'calibration' ? 'calibrate' : 'select');
  const [area, setArea] = useState<Point[]>(config.workArea || []);
  const [areaEditing, setAreaEditing] = useState(!config.workArea?.length && !config.mapAsset);
  const [template, setTemplate] = useState(true);
  const [pending, setPending] = useState<Point | null>(null);
  const [scaleDistance, setScaleDistance] = useState(1);
  const validation = camera ? session.calibrationFor(camera) : undefined;
  const check = validation?.status === 'valid' ? validation.diagnostics : undefined;
  const [sourceOpen, setSourceOpen] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  const update = (patch: Partial<Config>) => session.setConfig({ ...config, ...patch });
  const patchCamera = (patch: Partial<Camera>) => {
    if (!camera) return;
    update({ cameras: config.cameras.map(item => item.id === camera.id ? { ...item, ...patch } : item) });
  };

  useEffect(() => {
    if (sourceOpen) dialog.current?.showModal(); else dialog.current?.close();
  }, [sourceOpen]);
  useEffect(() => {
    setArea(config.workArea || []);
    setAreaEditing(!config.workArea?.length && !config.mapAsset);
    setPending(null);
  }, [config.planId]);
  useEffect(() => {
    setTool(controlled === 'calibration' ? 'calibrate' : 'select');
    setPending(null);
  }, [controlled, selected]);

  function chooseSection(next: Section) {
    setInnerSection(next);
    setTool(next === 'calibration' ? 'calibrate' : 'select');
    setPending(null);
  }

  function changeArea(points: Point[]) {
    setArea(points);
    if (points.length >= 3) update({ workArea: points, mapConfigured: true });
  }

  function confirmArea() {
    if (area.length < 3) return;
    const next = { ...config, workArea: area, mapConfigured: true };
    void session.action(async () => {
      await session.save(next);
      setAreaEditing(false);
      setTool('select');
      session.setNotice('Límite del plano guardado.');
    });
  }

  function clearArea() {
    const plans = { ...config.plans };
    if (config.planId && plans[config.planId]) plans[config.planId] = { ...plans[config.planId], workArea: undefined };
    update({ workArea: undefined, plans });
    setArea([]);
    setAreaEditing(false);
    setTool('select');
  }

  function importFile(selectedFile: File) {
    void session.action(async () => {
      const imported = await session.post(`import-plan?name=${encodeURIComponent(selectedFile.name)}&width=${config.width}&page=0`, selectedFile, true);
      const next = {
        background: imported.background,
        planLines: [],
        planView: 'image' as const,
        width: imported.width,
        height: imported.height,
        planName: selectedFile.name,
        mapConfigured: true,
        workArea: undefined,
        zones: [],
        cameras: config.cameras.map(item => !samePlan(item) ? item : ({
          ...item,
          x: Math.min(item.x, imported.width),
          y: Math.min(item.y, imported.height),
          pairs: [],
        })),
        importWarnings: imported.warnings,
      };
      update(next);
      setArea([]);
      setAreaEditing(false);
      setTemplate(true);
      session.setNotice('Plano importado. Ahora ubica las cámaras y calibra sus referencias.');
    });
  }

  function addCamera() {
    const next = freshCamera();
    next.name = `Cámara ${config.cameras.length + 1}`;
    next.planId = config.planId;
    next.x = config.width / 2;
    next.y = config.height / 2;
    update({ cameras: [...config.cameras, next] });
    onSelected(next.id);
  }

  const referenceDistance = camera && camera.pairs.length >= 2
    ? Math.hypot(camera.pairs[1][2] - camera.pairs[0][2], camera.pairs[1][3] - camera.pairs[0][3])
    : 0;

  function applyScale() {
    if (!camera || config.mapAsset || !referenceDistance || !Number.isFinite(scaleDistance) || scaleDistance <= 0) return;
    const factor = scaleDistance / referenceDistance;
    const point = (value: Point): Point => [value[0] * factor, value[1] * factor];
    update({
      unit: 'meters',
      width: config.width * factor,
      height: config.height * factor,
      workArea: config.workArea?.map(point),
      radius: config.radius * factor,
      matchDistance: config.matchDistance * factor,
      zones: config.zones.map(zone => ({ ...zone, points: zone.points.map(point) })),
      cameras: config.cameras.map(item => !samePlan(item) ? item : ({
        ...item,
        x: item.x * factor,
        y: item.y * factor,
        pairs: item.pairs.map(pair => [pair[0], pair[1], pair[2] * factor, pair[3] * factor]),
      })),
    });
    setArea(area.map(point));
  }

  function validateCalibration() {
    if (!camera) return;
    void session.action(async () => {
      await session.validateCalibration(camera.id);
      await session.save();
      session.setNotice('Geometría de la homografía validada y guardada. La precisión física requiere comprobación independiente.');
    });
  }

  function savePlan() {
    void session.action(async () => {
      const next = areaEditing && area.length >= 3 ? { ...config, workArea: area, mapConfigured: true } : config;
      await session.save(next);
      setAreaEditing(false);
      session.setNotice('Plano guardado.');
    });
  }

  const unit = config.unit === 'meters' ? 'm' : 'u';
  const tools: [MapTool, string][] = section === 'area'
    ? [['trace', 'Dibujar con puntos'], ['line', 'Dibujar con líneas'], ['erase', 'Borrar líneas'], ['work-rect', 'Límite rectangular'], ['work-poly', 'Límite libre'], ['work-edit', 'Ajustar límite']]
    : section === 'calibration'
      ? [['camera', 'Mover cámara'], ['calibrate', 'Punto del suelo']]
      : [['camera', 'Colocar cámara']];

  return <section className="plan-workspace">
    <dialog ref={dialog} className="camera-source-dialog" onCancel={() => setSourceOpen(false)}>
      <div className="panel-heading"><h2>{camera?.name} · Fuente y zona útil</h2><button onClick={() => setSourceOpen(false)}>Cerrar</button></div>
      {sourceOpen && <CameraEditor camera={camera} config={config} session={session} onChange={session.setConfig} />}
    </dialog>

    {!embedded && <header className="cad-head"><div><span className="eyebrow">EDITOR DEL ESPACIO</span><h2>{config.floor || 'Plano principal'}</h2></div><button className="primary" disabled={disabled || session.busy} onClick={savePlan}>Guardar plano</button></header>}
    {!embedded && <nav className="cad-tabs">{([['cameras', '1 · Cámaras'], ['calibration', '2 · Homografía'], ['area', 'Plano']] as const).map(([id, label]) => <button key={id} className={section === id ? 'selected' : ''} onClick={() => chooseSection(id)}>{label}</button>)}</nav>}

    {section === 'calibration' && <nav className="cad-parts" role="tablist" aria-label="Partes de la homografía">
      {PARTS.map(([id, label]) => <button key={id} role="tab" aria-selected={part === id} className={part === id ? 'selected' : ''}
        onClick={() => { setPart(id); setPending(null); setTool(id === 'suelo' ? 'calibrate' : 'select'); }}>{label}{id === 'personas' && cameras.length > 1 ? ' (necesario)' : ''}</button>)}
    </nav>}

    {section === 'calibration' && part === 'suelo' && <div className="calibration-guide"><div><strong>Video oblicuo y plano aéreo</strong><p>Modo activo: <b>{tool === 'camera' ? 'Mover cámara' : 'Punto del suelo'}</b>. La foto de la cámara puede estar inclinada y el plano siempre se ve desde arriba: no intentes que ambas imágenes se parezcan. Marca exactamente el mismo punto físico del suelo en las dos vistas (esquina de baldosa, junta, columna apoyada o cruce visible), usando la base de los pies para personas. Usa al menos 4 referencias; recomendamos 6–8 distribuidas por toda el área visible. La homografía corrige la perspectiva solo dentro de la zona útil calibrada. Si otra cámara ya marcó puntos, aparecen como círculos punteados: elige los mismos para alinear ambas vistas.</p></div>{pending && <button onClick={() => setPending(null)}>Cancelar punto</button>}</div>}
    {disabled && <div className="notice compact">Finaliza la sesión para editar la geometría.</div>}

    {!(section === 'calibration' && part !== 'suelo') && <div className={`cad-body ${section === 'calibration' ? 'with-video' : ''}`}>
      <div className="cad-canvas">
        <div className="cad-tools">
          {tools.map(([id, label]) => <button key={id} disabled={disabled} className={tool === id ? 'on' : ''} onClick={() => { setTool(id); setPending(null); if (id.startsWith('work')) setAreaEditing(true); }}>{label}</button>)}
          {section === 'area' && areaEditing && <><button className="primary" disabled={disabled || area.length < 3 || session.busy} onClick={confirmArea}>Guardar límite</button><button disabled={disabled || !area.length} onClick={() => setArea(area.slice(0, -1))}>Deshacer</button></>}
          {section === 'calibration' && <span className="cad-action-hint">{tool === 'camera' ? 'Arrastra la cámara en el plano. En este modo no se crean puntos.' : pending ? 'Ahora marca el mismo punto en el plano.' : 'Selecciona primero un punto del suelo en el video.'}</span>}
        </div>
        <MapCanvas
          key={config.planId || 'custom'} config={config} state={session.state} connected={session.connected}
          configuration editable={!disabled} selectedCamera={selected} onCamera={onSelected} onChange={session.setConfig}
          tool={tool} onTool={setTool} template={template} areaDraft={area} onAreaDraft={changeArea} areaEditing={areaEditing}
          calibrationFootprint={check?.projectedBoundary}
          onCalibrationPoint={point => {
            if (!pending || !camera) return;
            patchCamera({ pairs: [...camera.pairs, [...pending, ...point]] });
            setPending(null);
          }}
        />
        <footer className="cad-status"><span>{section === 'calibration' ? `${camera?.pairs.length || 0} referencias del suelo (opcionales; 4 o más para calibrar)` : config.workArea?.length ? `${config.workArea.length} puntos del límite` : config.planLines?.length ? `${config.planLines.length} líneas del plano` : 'Plano completo'}</span><span>Rueda: zoom · Arrastra: desplazar</span></footer>
      </div>

      <aside className="cad-inspector">
        {section === 'area' ? <>
          <span className="cad-step-badge">PLANO</span><h3>Base del espacio</h3>
          <p>{config.mapAsset ? 'Este nivel ya tiene escala. El límite de trabajo es opcional.' : config.background ? 'La plantilla está lista. Define un límite solo para excluir el exterior.' : 'Importa una imagen o PDF del plano.'}</p>
          <label className="check"><input type="checkbox" checked={template} onChange={event => setTemplate(event.target.checked)} /> Mostrar plantilla</label>
          <button disabled={disabled || !!config.mapAsset || session.busy} onClick={() => file.current?.click()}>Importar plano</button>
          <input hidden ref={file} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,.dxf,.dwg" onChange={event => { const selectedFile = event.target.files?.[0]; event.target.value = ''; if (selectedFile) importFile(selectedFile); }} />
          <button disabled={disabled} onClick={() => { setAreaEditing(true); setArea(config.workArea || []); setTool(config.workArea?.length ? 'work-edit' : 'work-poly'); }}>{config.workArea?.length ? 'Ajustar límite' : 'Dibujar límite libre'}</button>
          {config.workArea?.length && <button className="danger ghost" disabled={disabled || session.busy} onClick={clearArea}>Usar plano completo</button>}
          <small>Sin plano importado, dibújalo: «Dibujar con puntos» traza un contorno punto a punto y «Dibujar con líneas» pone segmentos sueltos. Se dibuja sobre fondo oscuro con líneas blancas. Shift mantiene el ángulo recto.</small>
          <small>La zona útil de cada video es la que excluye espejos y áreas externas.</small>
        </> : <>
          {section === 'cameras' && <button disabled={disabled} onClick={addCamera}>+ Agregar cámara</button>}
          <label>Cámara<select value={selected} onChange={event => { onSelected(event.target.value); setPending(null); }}>{cameras.map(item => <option value={item.id} key={item.id}>{item.name || item.id}</option>)}</select></label>
          {camera && section === 'cameras' && <><button onClick={() => setSourceOpen(true)}>Editar fuente y zona útil</button><label>Nombre<input disabled={disabled} value={camera.name || camera.id} onChange={event => patchCamera({ name: event.target.value })} /></label><label className="check"><input disabled={disabled} type="checkbox" checked={camera.active !== false} onChange={event => patchCamera({ active: event.target.checked })} /> Cámara activa</label></>}
          {camera && section === 'calibration' && <>
            <CameraVideo camera={camera} state={session.state} connected={session.connected} mode={disabled ? undefined : 'calibration'} pending={pending} zonePoints={camera.detectionZone} pairPoints={camera.pairs.map(pair => [pair[0], pair[1]])} onPairChange={disabled ? undefined : (index, point) => { patchCamera({ pairs: camera.pairs.map((value, item) => item === index ? [point[0], point[1], value[2], value[3]] : value) }); }} onPoint={point => { setPending(point); setTool('calibrate'); }} />
            <button disabled={disabled} onClick={startTest}>Actualizar imagen</button>
            <label>Altura de la cámara (m)<input disabled={disabled} type="number" min="1.8" step="0.1" value={camera.height ?? 2} onChange={event => patchCamera({ height: +event.target.value })} /></label>
            <div className="cad-nodes">{camera.pairs.map((pair, index) => <div key={index}><i style={{ background: COLORS[index % COLORS.length] }} />Referencia {index + 1}<span>X {pair[2].toFixed(2)} · Y {pair[3].toFixed(2)}{check?.pointErrors?.[index] != null ? ` · error ${check.pointErrors[index].toFixed(2)} ${unit}${check.outlierIndices?.includes(index + 1) ? ' (descartada)' : ''}` : ''}</span><button disabled={disabled} title={`Eliminar referencia ${index + 1}`} onClick={() => { patchCamera({ pairs: camera.pairs.filter((_, item) => item !== index) }); }}>×</button></div>)}</div>
            {!config.mapAsset && camera.pairs.length >= 2 && <><label>Distancia real entre 1 y 2 (m)<input disabled={disabled} type="number" min="0.001" step="0.1" value={scaleDistance} onChange={event => setScaleDistance(+event.target.value)} /></label><button disabled={disabled || !referenceDistance} onClick={applyScale}>Aplicar escala</button></>}
            <button className="primary" disabled={disabled || camera.pairs.length < 4 || session.busy} onClick={validateCalibration}>Validar homografía</button>
            {check && <p role="status" className={check.warning ? 'notice warning' : 'notice'}><strong>{check.warning ? 'Revisa las referencias' : 'Homografía validada'}</strong><span>{check.warning || `Error medio: ${check.rmse.toFixed(3)} ${unit}.`}{check.inlierCount != null && ` · ${check.inlierCount}/${camera.pairs.length} referencias consistentes`}{check.validationPoints ? ` · validación cruzada: ${check.validationError?.toFixed(3)} ${unit}` : ''} · La huella naranja muestra dónde cae toda la imagen sobre el plano.</span></p>}
            <p role="status" className={validation?.status === "invalid" ? "notice warning" : "notice"}>{calibrationMessage(camera,validation)}</p>
          </>}
        </>}
      </aside>
    </div>}
    {section === 'calibration' && part === 'personas' && <PersonPairs session={session} config={config} selected={selected} disabled={disabled} />}
  </section>;
}
