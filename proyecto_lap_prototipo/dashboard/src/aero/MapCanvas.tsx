import {loadMapAsset} from './mapAssets';
import type {MapPlace} from './mapAssets';
import { useEffect, useId, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import type { Config, Person, Point, SessionState, Zone } from './types';
import { COLORS } from './types';
import Icon from './Icon';
import VectorFloor from './VectorFloor';
import { clusterPeople, detailLevel, lodFlags, magnification, placeLabels } from './lod';
import { defaultPlanView, planLayers } from './planLayers';
import { ajustarPunto, deshacerTrazo, esHerramientaDeTrazo, planoOscuro, segmentoNormalizado } from './trazo';
import { useBusinesses } from './useBusinesses';
import type { Business } from './useBusinesses';

const DETALLE: Record<string,{label:string;hint:string}> = {
  general:  {label:'Vista general', hint:'Personas agrupadas y zonas en conjunto. Acércate para separar individuos.'},
  zonas:    {label:'Zonas',         hint:'Zonas y cámaras con su nombre. Acércate para ver personas de a una.'},
  personas: {label:'Personas',      hint:'Individuos separados con sus recorridos.'},
  detalle:  {label:'Detalle',       hint:'Identificadores, dirección estimada y conteos por cámara.'},
};

export type MapTool = 'select' | 'camera' | 'polygon' | 'rectangle' | 'circle' | 'move' | 'calibrate' | 'work-rect' | 'work-poly' | 'work-edit' | 'line' | 'trace' | 'erase';
interface Props {
  config: Config; state: SessionState; connected: boolean; editable?: boolean; configuration?:boolean; compact?: boolean;
  selectedCamera: string; onCamera: (id: string) => void; selectedPerson?: string; onPerson?: (p: Person) => void;
  onChange?: (config: Config) => void; tool?: MapTool; onTool?: (tool: MapTool) => void;
  areaDraft?: Point[]; onAreaDraft?: (p:Point[])=>void; areaEditing?: boolean; template?: boolean;
  viewMode?:'tracks'|'heat';
  peopleFirst?:boolean;
  zonesOnly?:boolean;
  zoneMode?:'all'|'business';
  focusArea?:{x:number;y:number;size:number};
  focusLocation?:Point;
  onCalibrationPoint?: (point: Point) => void;
  calibrationFootprint?: Point[];
  businessMarkers?: Business[];
  onBusinessPoint?: (point: Point) => void;
  onMapPlace?: (place:MapPlace)=>void;
  onZoneSelect?: (zone: Zone) => void;
  editableBusinessId?:string;
  onBusinessMove?:(point:Point)=>void;
  orientation?: 'horizontal' | 'vertical';
  onOrientation?: (orientation: 'horizontal' | 'vertical') => void;
}
const kinds: Record<string, string> = { roi: '#0789e9', queue: '#e2a037', restricted: '#d65d63', room: '#839cac', wall: '#c1ced6', door: '#a67c52', corridor: '#5c8096', commercial: '#8a5fd1' };

export default function MapCanvas({ config, state, connected, editable, configuration=false, zonesOnly=false, zoneMode='all', compact, focusArea, focusLocation, selectedCamera, onCamera, selectedPerson, onPerson, onChange, tool = 'select', onTool, onCalibrationPoint, calibrationFootprint, areaDraft=[], onAreaDraft, areaEditing=false, template, viewMode, peopleFirst=false, businessMarkers, onBusinessPoint, onMapPlace, onZoneSelect, editableBusinessId, onBusinessMove, orientation: controlledOrientation, onOrientation }: Props) {
  const businesses=useBusinesses(config.airport||'');
  const registeredBusinesses=businessMarkers??businesses.items;
  const businessDrag=useRef<string|null>(null);
  const isSetup=configuration||editable;
  const world=useRef<SVGGElement>(null);
  const [localOrientation,setLocalOrientation]=useState<'horizontal' | 'vertical'>(config.orientation || 'horizontal');
  const orientation=controlledOrientation ?? localOrientation;
  const bearing=config.mapAsset
    ? (orientation==='horizontal'?-64:26)
    : (orientation==='vertical'?90:0);
  useEffect(()=>{if(controlledOrientation===undefined)setLocalOrientation(config.orientation || 'horizontal');},[config.orientation,controlledOrientation]);
  function changeOrientation(next: 'horizontal' | 'vertical') {
    if(controlledOrientation===undefined)setLocalOrientation(next);
    onOrientation?.(next);
    if(onChange && !controlledOrientation) onChange({...config,orientation:next});
  }
  const svg = useRef<SVGSVGElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  // Fondo del plano: preferencia de visualización del operador, no del proyecto.
  const [darkPlan,setDarkPlan]=useState(()=>{try{return localStorage.getItem('aero.plan.background')!=='light';}catch{return true;}});
  // Dibujar el plano (puntos o líneas) o verlo como líneas se hace siempre sobre fondo oscuro con líneas blancas.
  const oscuro=planoOscuro(darkPlan,tool,config.planView,(config.planLines||[]).length);
  const paper=oscuro
    ? {base:'#0b0f14',lines:'#ffffff',grid:'#527488',gridOpacity:.22,label:'#dceaf4',halo:'#0b0f14'}
    : {base:'#ffffff',lines:'#1d2a36',grid:'#9fb3c2',gridOpacity:.3,label:'#254355',halo:'#ffffff'};
  function switchPlanBackground(){setDarkPlan(value=>{const next=!value;try{localStorage.setItem('aero.plan.background',next?'dark':'light');}catch{/* modo privado */}return next;});}
  const [viewport,setViewport]=useState({width:900,height:570});
  useEffect(()=>{const element=svg.current;if(!element)return;const resize=()=>setViewport({width:element.clientWidth||900,height:element.clientHeight||570});const observer=new ResizeObserver(resize);observer.observe(element);resize();return()=>observer.disconnect();},[]);
  const pattern = useId().replace(/:/g, '');
  const [draft, setDraft] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point|null>(null);
  useEffect(()=>{if(!esHerramientaDeTrazo(tool))return;const salir=(e:globalThis.KeyboardEvent)=>{if(e.key==='Escape'){setDraft([]);setCursor(null);}};window.addEventListener('keydown',salir);return()=>window.removeEventListener('keydown',salir);},[tool]);
  const [name, setName] = useState(zoneMode==='business'?'Nuevo negocio':'Nueva zona ROI');
  const [kind, setKind] = useState<NonNullable<Zone['kind']>>(zoneMode==='business'?'commercial':'roi');
  useEffect(()=>{if(zoneMode==='business'){setName('Nuevo negocio');setKind('commercial');}},[zoneMode]);
  const [layers, setLayers] = useState({ accesses: true, metrics: false, cameras: true, labels: true, trajectories: true, heat: true, prediction: false, flow: false, zones: true });
  useEffect(()=>{if(viewMode&&!isSetup)setLayers(p=>({...p,heat:viewMode==='heat',trajectories:viewMode==='tracks',flow:false}));},[viewMode,isSetup]);
  const [editingZone,setEditingZone]=useState<number|null>(null);
  const [vertex,setVertex]=useState<number|null>(null);
  const vertexDrag=useRef<{zone:number;index:number}|null>(null);
  const pairDrag=useRef<number|null>(null);
  const [selectedPair,setSelectedPair]=useState<number|null>(null);
  const [showLayers, setShowLayers] = useState(false);
  const drag = useRef<{ type: 'camera' | 'zone' | 'aim' | 'work' | 'fov' | 'width' | 'corner'; id: string | number; origin: Point; snapshot: Config } | null>(null);
  const panDrag = useRef<{ startX: number; startY: number; vb0: { x: number; y: number; w: number; h: number } } | null>(null);
  const moved = useRef(false);
  const [vb, setVb] = useState({ x: 0, y: 0, w: config.width, h: config.height });
  useEffect(() => { setVb({ x: 0, y: 0, w: config.width, h: config.height }); }, [config.width, config.height]);
  const [mapPoints,setMapPoints]=useState<number[][]>([]);
  const [mapBounds,setMapBounds]=useState<{x:number;y:number;w:number;h:number}|null>(null);
  const [imageBounds,setImageBounds]=useState<{x:number;y:number;w:number;h:number}|null>(null);
  useEffect(()=>{let alive=true;setMapBounds(null);setMapPoints([]);if(config.mapAsset)void loadMapAsset(config.mapAsset).then(m=>{if(alive&&m.viewBounds){const [x,y,x2,y2]=m.viewBounds;const b={x:x-20,y:y-20,w:x2-x+40,h:y2-y+40};setMapPoints(m.features.filter((f:any)=>['Polygon','MultiPolygon'].includes(f.geometry.type)).flatMap((f:any)=>f.geometry.type==='Polygon'?f.geometry.coordinates.flat():f.geometry.coordinates.flat(2)).filter((p:number[])=>p[0]>=x&&p[0]<=x2&&p[1]>=y&&p[1]<=y2));setMapBounds(b);}}).catch(()=>{});return()=>{alive=false;};},[config.mapAsset]);
  useEffect(()=>{let alive=true;setImageBounds(null);if(!config.background)return()=>{alive=false;};const image=new Image();image.onload=()=>{if(!alive||!image.naturalWidth||!image.naturalHeight)return;const imageRatio=image.naturalWidth/image.naturalHeight,planRatio=config.width/config.height;if(imageRatio>planRatio){const h=config.width/imageRatio;setImageBounds({x:0,y:(config.height-h)/2,w:config.width,h});}else{const w=config.height*imageRatio;setImageBounds({x:(config.width-w)/2,y:0,w,h:config.height});}};image.src=config.background;return()=>{alive=false;};},[config.background,config.width,config.height]);
  const bounded = !config.mapAsset && !!config.workArea?.length && !areaEditing;
  const fit = () => {

    const base=bounded?config.workArea!:mapPoints.length?mapPoints:mapBounds?[[mapBounds.x,mapBounds.y],[mapBounds.x+mapBounds.w,mapBounds.y],[mapBounds.x+mapBounds.w,mapBounds.y+mapBounds.h],[mapBounds.x,mapBounds.y+mapBounds.h]]:imageBounds?[[imageBounds.x,imageBounds.y],[imageBounds.x+imageBounds.w,imageBounds.y],[imageBounds.x+imageBounds.w,imageBounds.y+imageBounds.h],[imageBounds.x,imageBounds.y+imageBounds.h]]:[[0,0],[config.width,0],[config.width,config.height],[0,config.height]];
    const theta=bearing*Math.PI/180,cx=config.width/2,cy=config.height/2;
    const a=base.map(p=>[cx+(p[0]-cx)*Math.cos(theta)-(p[1]-cy)*Math.sin(theta),cy+(p[0]-cx)*Math.sin(theta)+(p[1]-cy)*Math.cos(theta)]);
    const x=Math.min(...a.map(p=>p[0])), y=Math.min(...a.map(p=>p[1]));
    let w=Math.max(.01,Math.max(...a.map(p=>p[0]))-x),h=Math.max(.01,Math.max(...a.map(p=>p[1]))-y);
    let fx=x,fy=y;
    const viewportRatio=Math.max(.1,viewport.width/Math.max(1,viewport.height));
    if(isSetup){
      const pad=Math.max(w,h)*.025;fx-=pad;fy-=pad;w+=pad*2;h+=pad*2;
      if(w/h>viewportRatio){const next=w/viewportRatio;fy-=(next-h)/2;h=next;}
      else{const next=h*viewportRatio;fx-=(next-w)/2;w=next;}
    }else if(w/h>viewportRatio){const next=h*viewportRatio;fx+=(w-next)/2;w=next;}
    else{const next=w/viewportRatio;fy+=(h-next)/2;h=next;}
    return {x:fx,y:fy,w,h};
  };
  useEffect(()=>{setVb(fit());},[mapBounds,mapPoints,imageBounds,bearing,viewport.width,viewport.height]);
  useEffect(()=>{if(!focusArea)return;const b=bearing*Math.PI/180,cx=config.width/2,cy=config.height/2,x=focusArea.x+focusArea.size/2,y=focusArea.y+focusArea.size/2,rx=cx+(x-cx)*Math.cos(b)-(y-cy)*Math.sin(b),ry=cy+(x-cx)*Math.sin(b)+(y-cy)*Math.cos(b),w=Math.max(focusArea.size*8,20),h=w*viewport.height/viewport.width;setVb({x:rx-w/2,y:ry-h/2,w,h});},[focusArea,mapPoints,bearing]);
  const areaKey=JSON.stringify(config.workArea);
  useEffect(()=>{if(!areaEditing)setVb(fit());},[areaKey]);
  useEffect(()=>{setVb(fit());},[areaEditing]);
  useEffect(()=>{if(!focusLocation)return;const angle=bearing*Math.PI/180,cx=config.width/2,cy=config.height/2,dx=focusLocation[0]-cx,dy=focusLocation[1]-cy,w=Math.max(12,config.width*.06),h=w*viewport.height/viewport.width;setVb({x:cx+dx*Math.cos(angle)-dy*Math.sin(angle)-w/2,y:cy+dx*Math.sin(angle)+dy*Math.cos(angle)-h/2,w,h});},[focusLocation,mapPoints]);
  useEffect(()=>{setDraft([]);},[tool,selectedCamera]);
  const floorCameras=config.cameras.filter(c=>(c.planId||'custom')===(config.planId||'custom'));
  const matchingPlan=(state.planId||'custom')===(config.planId||'custom');
  const active = !isSetup && matchingPlan && connected && (['running', 'paused'].includes(state.status) || (['ended','stopped'].includes(state.status) && state.people.some(p=>p.point)));
  const people = active ? Array.from(new Map(state.people.filter(p => p.point && !p.duplicate).map(p => [p.id, p] as const)).values()) : [];
  const scale = Math.max(vb.w/viewport.width,vb.h/viewport.height);

  // Imagen o líneas: la decisión vive en planLayers.ts, donde se puede comprobar.
  const planView = config.planView || defaultPlanView(!!config.background, (config.planLines||[]).length);
  const capasPlano = planLayers({isSetup:!!isSetup, template:!!template, planView,
    hasBackground:!!config.background, lineCount:(config.planLines||[]).length, hasMapAsset:!!config.mapAsset});
  // Mientras se dibuja, la imagen importada solo se ve si se pidió la plantilla: encima de una imagen clara las líneas blancas no se leen.
  const capas = editable&&esHerramientaDeTrazo(tool)&&!template ? {...capasPlano,image:false} : capasPlano;

  // Zoom semántico. En configuración no se aplica: quien edita necesita ver todo
  // lo que está tocando, aunque quede apretado.
  const [autoDetail,setAutoDetail]=useState(true);
  const semantic = !isSetup && autoDetail && !peopleFirst;
  const mag = magnification(config.width, vb.w);
  const level = detailLevel(mag);
  const lod = lodFlags(level);
  // El zoom solo puede quitar capas, nunca encender una que el operador apagó.
  const show = (key: keyof typeof layers, auto = true) => layers[key] && (!semantic || auto);

  // Agrupar por cercanía en pantalla. En detalle fino el radio es chico, así que
  // casi todos quedan solos; de lejos se juntan y no se satura el plano.
  const groups = clusterPeople(
    people.map(p => ({ id: p.id, point: p.point as [number,number], uncertain: p.association==='uncertain', person: p })),
    peopleFirst ? 0 : (semantic || !lod.individuals ? scale : 0),
    lod.clusterPx,
  );
  const singles = groups.filter(g => g.count === 1);
  const personLabels = show('labels', peopleFirst || lod.personLabels)
    ? placeLabels(singles.map(g => ({ key: g.key, point: g.point, width: peopleFirst ? 44 : 58, height: peopleFirst ? 10 : 13,
        priority: g.key === selectedPerson ? 1e6 : g.members[0].person.history?.length || 0 })), scale, peopleFirst ? 300 : 120)
    : [];
  const labelOffset = new Map(personLabels.map(l => [l.key, l] as const));

  /** Al tocar un grupo se encuadra su contenido: así se baja del conjunto a la persona. */
  function zoomToGroup(g: typeof groups[number]) {
    const xs = g.members.map(m => m.point[0]), ys = g.members.map(m => m.point[1]);
    const pad = Math.max(lod.clusterPx * scale * 2, vb.w * .04);
    const x = Math.min(...xs) - pad, y = Math.min(...ys) - pad;
    const w = Math.max(Math.max(...xs) - Math.min(...xs) + pad * 2, vb.w * .18);
    setVb({ x, y, w, h: Math.max(Math.max(...ys) - Math.min(...ys) + pad * 2, w * viewport.height / viewport.width) });
  }
  function point(e: PointerEvent): Point {
    const matrix = world.current?.getScreenCTM();
    if (!matrix) return [0, 0];
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse());
    return [Math.max(0, Math.min(config.width, p.x)), Math.max(0, Math.min(config.height, p.y))];
  }
  function beginPan(e: PointerEvent<SVGSVGElement>) {
    if (businessDrag.current || drag.current || vertexDrag.current || pairDrag.current!==null) return;
    moved.current=false;
    panDrag.current = { startX: e.clientX, startY: e.clientY, vb0: vb };
    svg.current?.setPointerCapture(e.pointerId);
  }
  function handleWheel(e: globalThis.WheelEvent) {
    e.preventDefault();
    const matrix = svg.current?.getScreenCTM();
    if (!matrix) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse());
    const factor = e.deltaY < 0 ? 0.88 : 1 / 0.88;
    setVb(v => {
      const w = Math.min(config.width * 6, Math.max(config.width / 150, v.w * factor));
      const h = w * (v.h / v.w);
      return { x: p.x - (p.x - v.x) * (w / v.w), y: p.y - (p.y - v.y) * (h / v.h), w, h };
    });
  }
  const wheelHandler=useRef(handleWheel);wheelHandler.current=handleWheel;
  useEffect(()=>{const el=svg.current;if(!el)return;const handler=(event:globalThis.WheelEvent)=>{event.preventDefault();event.stopPropagation();wheelHandler.current(event);};el.addEventListener('wheel',handler,{passive:false});return()=>el.removeEventListener('wheel',handler);},[]);
  function handlePointerMove(e: PointerEvent<SVGSVGElement>) {
    if(editable&&esHerramientaDeTrazo(tool)&&draft.length)setCursor(ajustarPunto(point(e),draft[0],config.planLines||[],config.width,config.height,scale*10,e.shiftKey));
    if(businessDrag.current&&onBusinessMove){moved.current=true;onBusinessMove(point(e));return;}
    if(vertexDrag.current&&onChange){const d=vertexDrag.current,p=point(e);moved.current=true;onChange({...config,zones:config.zones.map((z,i)=>i===d.zone?{...z,shape:'polygon',points:z.points.map((v,j)=>j===d.index?p:v)}:z)});return;}
    if(pairDrag.current!==null&&onChange){const index=pairDrag.current,p=point(e);moved.current=true;onChange({...config,cameras:config.cameras.map(c=>c.id===selectedCamera?{...c,pairs:c.pairs.map((v,i)=>i===index?[v[0],v[1],...p]:v)}:c)});return;}
    if (panDrag.current) {
      if(Math.hypot(e.clientX-panDrag.current.startX,e.clientY-panDrag.current.startY)>3)moved.current=true;
      const rect = svg.current?.getBoundingClientRect();
      if (!rect || !rect.width || !rect.height) return;
      const { startX, startY, vb0 } = panDrag.current;
      const dx = (e.clientX - startX) * Math.max(vb0.w / rect.width,vb0.h / rect.height);
      const dy = (e.clientY - startY) * Math.max(vb0.w / rect.width,vb0.h / rect.height);
      setVb({ x: vb0.x - dx, y: vb0.y - dy, w: vb0.w, h: vb0.h });
      return;
    }
    move(e);
  }
  function finish(points: Point[], shape: Zone['shape']) {
    if (!onChange || points.length < 3 || !name.trim()) return;
    onChange({ ...config, zones: [...config.zones, { id: crypto.randomUUID(), name: name.trim(), kind, shape, points, source:'operator', ...(zoneMode==='business'?{business:{category:'other' as const}}:{}) }] });
    setDraft([]); onTool?.('select');
  }
  function click(e: PointerEvent<SVGSVGElement>) {
    if(onBusinessPoint&&!moved.current){onBusinessPoint(point(e));return;}
    if (!editable || moved.current) { moved.current = false; return; }
    const p = point(e);
    if (tool === 'work-poly') { onAreaDraft?.([...areaDraft,p]); return; }
    if (tool === 'work-rect') {
      if (!draft.length) {setDraft([p]);return;}
      onAreaDraft?.([draft[0],[p[0],draft[0][1]],p,[draft[0][0],p[1]]]);setDraft([]);return;
    }
    if (tool === 'line' || tool === 'trace') {
      // Imán a los extremos ya dibujados; con Shift, ángulo recto. En «puntos» cada clic continúa desde el anterior.
      const lineas = config.planLines || [];
      const q = ajustarPunto(p, draft[0] || null, lineas, config.width, config.height, scale * 10, e.shiftKey);
      if (!draft.length) { setDraft([q]); return; }
      const segmento = segmentoNormalizado(draft[0], q, config.width, config.height, lineas.length);
      if (!segmento) return;
      onChange?.({...config, planView: 'lines', mapConfigured: true, planLines: [...lineas, segmento]});
      setDraft(tool === 'trace' ? [q] : []);
      return;
    }
    if (tool === 'camera' && floorCameras.some(c=>c.id===selectedCamera)) onChange?.({ ...config, cameras: config.cameras.map(c => c.id === selectedCamera ? { ...c, x: p[0], y: p[1], pairs:c.pairs.map(q=>[q[0],q[1],q[2]+p[0]-c.x,q[3]+p[1]-c.y]) } : c) });
    else if (tool === 'calibrate') onCalibrationPoint?.(snapToSharedPoint(p));
    else if (tool === 'polygon') setDraft(v => [...v, p]);
    else if (tool === 'rectangle' || tool === 'circle') {
      if (!draft.length) setDraft([p]);
      else if (tool === 'rectangle') {
        const a=draft[0],theta=bearing*Math.PI/180,c=Math.cos(theta),s=Math.sin(theta),dx=(p[0]-a[0])*c-(p[1]-a[1])*s,dy=(p[0]-a[0])*s+(p[1]-a[1])*c;
        finish([a,[a[0]+dx*c,a[1]-dx*s],p,[a[0]+dy*s,a[1]+dy*c]],'rectangle');
      }
      else {
        const center = draft[0];
        const radius = Math.min(Math.hypot(p[0]-center[0], p[1]-center[1]), center[0], center[1], config.width-center[0], config.height-center[1]);
        if (radius > .001) finish(Array.from({ length: 36 }, (_, i) => [center[0] + Math.cos(i * Math.PI / 18) * radius, center[1] + Math.sin(i * Math.PI / 18) * radius]), 'circle');
      }
    }
  }
  function beginDrag(e: PointerEvent, type: 'camera' | 'zone' | 'work', id: string | number) {
    if (!editable || (zonesOnly&&type!=='zone') || (type==='zone' && tool!=='move')) return;
    e.preventDefault();e.stopPropagation(); panDrag.current=null;moved.current = false;
    if(type==='camera')onCamera(String(id));
    drag.current = { type, id, origin: point(e), snapshot: config };
    svg.current?.setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (!drag.current || !onChange) return;
    const p = point(e), d = drag.current;
    const dx = p[0]-d.origin[0], dy = p[1]-d.origin[1];
    if (Math.abs(dx)+Math.abs(dy) < scale * 1.5) return;
    moved.current = true;
    if (d.type === 'work') {onAreaDraft?.(areaDraft.map((v,i)=>i===d.id?p:v));return;}
    if (d.type === 'camera') onChange({ ...config, cameras: d.snapshot.cameras.map(c => c.id === d.id ? { ...c, x: Math.max(0, Math.min(config.width, c.x+dx)), y: Math.max(0, Math.min(config.height, c.y+dy)), pairs: c.pairs.map(p=>[p[0],p[1],p[2]+dx,p[3]+dy]) } : c) });
    else {
      const zone = d.snapshot.zones[d.id as number];
      const tx = Math.max(-Math.min(...zone.points.map(v => v[0])), Math.min(dx, config.width-Math.max(...zone.points.map(v => v[0]))));
      const ty = Math.max(-Math.min(...zone.points.map(v => v[1])), Math.min(dy, config.height-Math.max(...zone.points.map(v => v[1]))));
      onChange({ ...config, zones: d.snapshot.zones.map((z, i) => i === d.id ? { ...z, points: z.points.map(v => [v[0]+tx, v[1]+ty] as Point) } : z) });
    }
  }
  const chooseTool = (next: MapTool) => { setDraft([]); onTool?.(next); };
  const selected = config.cameras.find(c => c.id === selectedCamera);
  // Puntos de calibración que ya marcaron las otras cámaras del mismo plano: sirven de guía
  // para marcar en el plano exactamente los mismos puntos del suelo en cada cámara.
  const sharedPairs = config.cameras
    .filter(c => c.id !== selectedCamera && (c.planId || 'custom') === (selected?.planId || 'custom'))
    .flatMap(c => c.pairs.map((q, i) => ({ camera: c, index: i, point: [q[2], q[3]] as Point })));
  const snapToSharedPoint = (p: Point): Point => {
    let best: Point | null = null, reach = scale * 12;
    for (const s of sharedPairs) {
      const d = Math.hypot(s.point[0] - p[0], s.point[1] - p[1]);
      if (d < reach) { reach = d; best = s.point; }
    }
    return best ? [best[0], best[1]] : p;
  };
  useEffect(()=>{setEditingZone(null);setVertex(null);setSelectedPair(null);},[config.planId,selectedCamera]);
  return <div className={`aero-map ${compact ? 'compact' : ''}`}>
    <div className="map-toolbar"><div className="inline map-identity"><Icon name="map" size={15}/><span>{config.floor || 'Plano principal'}</span></div><div className="inline map-controls">{editable && <>{!zonesOnly&&<button title="Colocar cámara seleccionada" className={tool === 'camera' ? 'on' : ''} onClick={() => chooseTool('camera')}><Icon name="camera" size={14}/><span>Cámara</span></button>}<button className={tool === 'polygon' ? 'on' : ''} onClick={() => chooseTool('polygon')}>Polígono</button><button className={tool === 'rectangle' ? 'on' : ''} onClick={() => chooseTool('rectangle')}>Rectángulo</button><button className={tool === 'circle' ? 'on' : ''} onClick={() => chooseTool('circle')}>Círculo</button><button className={tool === 'move' ? 'on' : ''} onClick={() => chooseTool('move')}>Mover</button></>}<button title="Acercar plano" onClick={()=>setVb(v=>({...v,x:v.x+v.w*.1,y:v.y+v.h*.1,w:v.w*.8,h:v.h*.8}))}>+</button><button title="Alejar plano" onClick={()=>setVb(v=>({...v,x:v.x-v.w*.125,y:v.y-v.h*.125,w:v.w*1.25,h:v.h*1.25}))}>−</button><button title="Ajustar el plano a la vista" onClick={()=>setVb(fit())}>Ajustar</button><button disabled={oscuro&&!darkPlan} title={oscuro&&!darkPlan?'El dibujo del plano usa fondo oscuro con líneas blancas':darkPlan?'Usar fondo claro':'Usar fondo oscuro'} onClick={switchPlanBackground}>{oscuro?'Fondo claro':'Fondo oscuro'}</button><button title="Pantalla completa" onClick={()=>{if(document.fullscreenElement)void document.exitFullscreen();else void stage.current?.requestFullscreen().catch(()=>{});}}><Icon name="expand" size={14}/></button>{(config.mapAsset||config.background)&&<div className="map-orientation" role="group" aria-label="Orientación del mapa">{(['horizontal','vertical'] as const).map(value=><button key={value} aria-label={value==='horizontal'?'Orientar horizontal':'Orientar vertical'} title={value==='horizontal'?'Vista horizontal':'Vista vertical'} aria-pressed={orientation===value} className={orientation===value?'on':''} onClick={()=>changeOrientation(value)}>{value==='horizontal'?'↔':'↕'}<span>{value==='horizontal'?'Horizontal':'Vertical'}</span></button>)}</div>}{selected&&<button title="Centrar cámara seleccionada" aria-label="Centrar cámara seleccionada" onClick={()=>{const x=selected.x,y=selected.y,b=bearing*Math.PI/180,cx=config.width/2,cy=config.height/2,rx=cx+(x-cx)*Math.cos(b)-(y-cy)*Math.sin(b),ry=cy+(x-cx)*Math.sin(b)+(y-cy)*Math.cos(b),w=Math.max(config.width,config.height)*.3,h=w*viewport.height/viewport.width;setVb({x:rx-w/2,y:ry-h/2,w,h});}}><Icon name="camera" size={15}/></button>}<button title="Restablecer zoom y posición" onClick={() => setVb(fit())}><Icon name="expand" size={15}/></button><button className="map-layers-toggle" title="Mostrar capas del plano" aria-expanded={showLayers} aria-controls={`${pattern}-layers`} onClick={() => setShowLayers(!showLayers)}><Icon name="layers" size={16}/><span>Capas</span></button></div></div>
    {editable && ['polygon', 'rectangle', 'circle'].includes(tool) && <div className="drawing-options"><input aria-label={zoneMode==='business'?'Nombre del negocio':'Nombre del área'} value={name} onChange={e => setName(e.target.value)} maxLength={80}/>{zoneMode==='business'?<span className="drawing-kind">Huella de negocio existente</span>:<select aria-label="Tipo de área" value={kind} onChange={e => setKind(e.target.value as NonNullable<Zone['kind']>)}>{Object.entries({ roi: 'Zona ROI', queue: 'Cola', restricted: 'Restringida', room: 'Sala', wall: 'Muro', door: 'Puerta', corridor: 'Pasillo', commercial: 'Comercio' }).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select>}<span>{tool === 'polygon' ? `${draft.length} vértices` : draft.length ? 'Marca el segundo punto' : tool === 'circle' ? 'Marca el centro y el radio' : 'Marca dos esquinas'}</span>{tool === 'polygon' && <button disabled={draft.length < 3} onClick={() => finish(draft, 'polygon')}>Cerrar área</button>}<button onClick={() => setDraft(p => p.slice(0, -1))}>Deshacer</button><button onClick={() => chooseTool('select')}>Cancelar</button></div>}
    {editable&&esHerramientaDeTrazo(tool)&&<div className="drawing-options"><strong>{tool==='erase'?'Borrar líneas':tool==='trace'?'Dibujar con puntos':'Dibujar con líneas'}</strong><span>{tool==='erase'?'Toca una línea para borrarla.':tool==='trace'?'Cada clic añade un punto y lo une con el anterior. Shift: ángulo recto. Esc o «Terminar trazo» para cortar.':'Dos clics hacen una línea. Shift: ángulo recto.'} · {(config.planLines||[]).length} líneas</span><button disabled={!(config.planLines||[]).length} onClick={()=>{const r=deshacerTrazo(config.planLines||[],config.width,config.height);onChange?.({...config,planLines:r.lineas});setDraft(tool==='trace'&&draft.length&&r.inicio?[r.inicio]:[]);setCursor(null);}}>Deshacer</button>{tool!=='erase'&&<button disabled={!draft.length} onClick={()=>{setDraft([]);setCursor(null);}}>Terminar trazo</button>}<button className="danger ghost" disabled={!(config.planLines||[]).length} onClick={()=>{if(window.confirm('¿Borrar todas las líneas dibujadas del plano?')){onChange?.({...config,planLines:[]});setDraft([]);setCursor(null);}}}>Borrar todo</button></div>}
    {editable&&editingZone!==null&&config.zones[editingZone]&&['select','move'].includes(tool)&&<div className="drawing-options"><strong>{config.zones[editingZone].name}</strong><span>Arrastra los puntos. Selecciona uno para añadir o quitar vértices.</span><button disabled={vertex===null} onClick={()=>{const z=config.zones[editingZone],i=vertex!,a=z.points[i],b=z.points[(i+1)%z.points.length];onChange?.({...config,zones:config.zones.map((v,j)=>j===editingZone?{...v,shape:'polygon',points:[...v.points.slice(0,i+1),[(a[0]+b[0])/2,(a[1]+b[1])/2] as Point,...v.points.slice(i+1)]}:v)});setVertex(i+1);}}>Añadir punto</button><button disabled={vertex===null||config.zones[editingZone].points.length<=3} onClick={()=>{onChange?.({...config,zones:config.zones.map((v,j)=>j===editingZone?{...v,shape:'polygon',points:v.points.filter((_,i)=>i!==vertex)}:v)});setVertex(null);}}>Quitar punto</button><button onClick={()=>{setEditingZone(null);setVertex(null);}}>Terminar edición</button></div>}
    {editable&&tool==='calibrate'&&selectedPair!==null&&selected?.pairs[selectedPair]&&<div className="drawing-options"><span>Referencia {selectedPair+1} · arrastra el punto del mapa para corregirlo</span><button onClick={()=>{onChange?.({...config,cameras:config.cameras.map(c=>c.id===selectedCamera?{...c,pairs:c.pairs.filter((_,i)=>i!==selectedPair)}:c)});setSelectedPair(null);}}>Eliminar referencia {selectedPair+1}</button></div>}
    {editable && tool === 'calibrate' && <div className="map-hint">Calibración: marca la correspondencia del punto del video sobre este plano.{sharedPairs.length>0&&' Los círculos punteados son puntos que ya marcaron otras cámaras: haz clic cerca de uno para usar exactamente el mismo punto.'}</div>}
    <div className="map-stage" ref={stage}><svg ref={svg} viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} onPointerDown={beginPan} onPointerUp={e => { const wasDrag = !!businessDrag.current || !!drag.current || !!vertexDrag.current || pairDrag.current!==null, wasPan = !!panDrag.current; businessDrag.current=null;drag.current = null; vertexDrag.current=null;pairDrag.current=null;panDrag.current = null; if (!wasDrag && (!wasPan || !moved.current)) click(e); }} onPointerMove={handlePointerMove} onPointerCancel={() => { businessDrag.current=null;drag.current = null;vertexDrag.current=null;pairDrag.current=null;panDrag.current = null; }} aria-label={editable ? 'Editor interactivo del plano' : 'Plano vivo de personas'} role="img"><g ref={world} transform={`rotate(${bearing} ${config.width/2} ${config.height/2})`}><defs><pattern id={pattern} width={config.width / 30} height={config.height / 20} patternUnits="userSpaceOnUse"><path d={`M ${config.width/30} 0 H0 V${config.height/20}`} fill="none" stroke={paper.grid} strokeWidth={scale*.6}/></pattern><radialGradient id={`${pattern}-heat`}><stop offset="0" stopColor="#f64545" stopOpacity=".85"/><stop offset=".3" stopColor="#ffa632" stopOpacity=".65"/><stop offset=".6" stopColor="#f6df49" stopOpacity=".4"/><stop offset="1" stopColor="#59d680" stopOpacity="0"/></radialGradient></defs><defs><clipPath id={`${pattern}-area`}><polygon points={(config.workArea||[]).map(p=>p.join(',')).join(' ')}/></clipPath></defs><g clipPath={bounded?`url(#${pattern}-area)`:undefined}><rect width={config.width} height={config.height} fill={paper.base}/>{config.mapAsset&&<VectorFloor names={Object.fromEntries(registeredBusinesses.filter(b=>b.referencia?.asset===config.mapAsset).map(b=>[b.referencia!.featureId,b.nombre]))} asset={config.mapAsset} scale={scale} bearing={bearing} onPlace={onMapPlace}/>}{/* La importación fija el alto según el aspecto real de la imagen, así que
    normalmente calza exacto. Con «meet» en vez de «none», si alguien cambia las
    medidas a mano el plano se ve entero y sin deformar en lugar de estirarse. */}
{/* En el editor, «Ver plantilla» sirve para mirar la foto DETRÁS de los trazos.
    Si no hay trazos no hay nada que tapar, así que ocultarla dejaba el lienzo en
    negro justo después de importar el plano. */}
{capas.image && <image href={config.background} width={config.width} height={config.height} preserveAspectRatio="xMidYMid meet" opacity={capas.imageOpacity}/>}<rect width={config.width} height={config.height} fill={`url(#${pattern})`} opacity={config.mapAsset?0:paper.gridOpacity}/>
      {/* El mapa del LAP ya es el dibujo del piso: las líneas de un plano propio
          encima no representan lo mismo y se leen como dos planos superpuestos. */}
      {/* En el editor las líneas se ven siempre: ahí la imagen está oculta salvo
          «Ver plantilla» y los trazos son la geometría con la que se trabaja. */}
      {capas.lines&&<g stroke={paper.lines} strokeWidth={scale*1.4}>{(config.planLines||[]).map((l,i)=><line key={i} x1={l[0]*config.width} y1={l[1]*config.height} x2={l[2]*config.width} y2={l[3]*config.height} style={tool==='erase'?{cursor:'crosshair',strokeWidth:scale*6}:undefined} onPointerUp={e=>{if(editable&&tool==='erase'){e.stopPropagation();onChange?.({...config,planLines:config.planLines!.filter((_,n)=>n!==i)});}}}/>)}</g>}
      {state.mode === 'demo' && !config.background && !config.zones.length && <g opacity=".6">{[[.06,.08,.26,.26,'Accesos'],[.38,.08,.23,.26,'Check-in'],[.69,.08,.25,.26,'Seguridad'],[.06,.67,.25,.25,'Sala de espera'],[.39,.67,.22,.25,'Servicios'],[.69,.67,.25,.25,'Comercios']].map((r, i) => <g key={i}><rect x={Number(r[0])*config.width} y={Number(r[1])*config.height} width={Number(r[2])*config.width} height={Number(r[3])*config.height} fill="#536a7944" stroke="#92aab7" strokeWidth={scale*2}/><text x={(Number(r[0])+Number(r[2])/2)*config.width} y={(Number(r[1])+Number(r[3])/2)*config.height} fill="#bdd3e1" fontSize={scale*12} textAnchor="middle">{r[4]}</text></g>)}</g>}
      {layers.zones && config.zones.map((z, i) => <g key={z.id || i} onPointerDown={e => {if(onZoneSelect&&z.kind==='commercial'&&tool==='select'){e.stopPropagation();onZoneSelect(z);return;}if(editable&&['select','move'].includes(tool)){setEditingZone(i);setVertex(null);beginDrag(e,'zone',i);}}} className={tool === 'move' ? 'move-target' : ''}><polygon points={z.points.map(p => p.join(',')).join(' ')} fill={z.color || kinds[z.kind || 'roi']} fillOpacity={isSetup?.03:z.kind === 'wall' ? .6 : .13} stroke={z.color || kinds[z.kind || 'roi']} strokeWidth={scale*1.7} strokeDasharray={z.kind === 'roi' ? `${scale*5} ${scale*4}` : undefined}/>{show('labels', lod.zoneLabels) && <text x={z.points.reduce((n,p)=>n+p[0],0)/z.points.length} y={z.points.reduce((n,p)=>n+p[1],0)/z.points.length} textAnchor="middle" fill={paper.label} stroke={paper.halo} strokeWidth={scale*3} paintOrder="stroke" fontSize={scale*12}>{z.name}</text>}</g>)}
      {editable&&editingZone!==null&&config.zones[editingZone]&&['select','move'].includes(tool)&&config.zones[editingZone].points.map((p,i)=><circle key={'vertex-'+i} cx={p[0]} cy={p[1]} r={scale*6} fill={vertex===i?'#d18100':'white'} stroke="#126494" strokeWidth={scale*2} style={{cursor:'grab'}} onPointerDown={e=>{e.stopPropagation();e.preventDefault();panDrag.current=null;vertexDrag.current={zone:editingZone,index:i};setVertex(i);svg.current?.setPointerCapture(e.pointerId);}}><title>Vértice {i+1}: arrastra para mover</title></circle>)}
      {(!isSetup || (zonesOnly&&zoneMode==='business')) && matchingPlan && layers.heat && state.analytics.heat.map((cell, i) => <rect key={i} x={cell.x} y={cell.y} width={cell.size} height={cell.size} fill="#a72195" opacity={Math.min(.7,.12+cell.seconds/Math.max(1,...state.analytics.heat.map(c=>c.seconds))*.58)}><title>Presencia acumulada: {cell.seconds.toFixed(1)} personas·segundo · pico simultáneo {cell.peak}. No son visitantes únicos.</title></rect>)}
      {!isSetup&&matchingPlan&&layers.flow&&(state.analytics.flowVectors||[]).filter(v=>v.samples>=2).sort((a,b)=>b.samples-a.samples).filter((v,i,all)=>all.findIndex(other=>other.x===v.x&&other.y===v.y)===i).map((v,i)=>{const length=Math.max(scale*9,v.size*.6),x=v.x+v.dx*length,y=v.y+v.dy*length;return <path key={`flow-${i}`} d={`M${v.x},${v.y}L${x},${y}M${x-v.dx*scale*4+v.dy*scale*3},${y-v.dy*scale*4-v.dx*scale*3}L${x},${y}L${x-v.dx*scale*4-v.dy*scale*3},${y-v.dy*scale*4+v.dx*scale*3}`} fill="none" stroke="#1679a5" strokeWidth={scale*1.5} opacity=".7"><title>Dirección observada · {v.samples} desplazamientos muestreados</title></path>;})}
      {/* Solo de quienes se ven de a uno: el recorrido de alguien dentro de un grupo
          saldría de un punto que no es el suyo. */}
      {show('trajectories', peopleFirst || lod.trajectories) && singles.map(({members:[m]}) => m.person).map(p => <polyline key={p.id} points={p.history.map(h => `${h[0]},${h[1]}`).join(' ')} fill="none" stroke={p.association === 'uncertain' ? '#ffae42' : '#21aaff'} opacity={selectedPerson === p.id ? 1 : .45} strokeWidth={scale*(selectedPerson === p.id ? 2.4 : peopleFirst ? .85 : 1.1)}/>)}
      {active && state.analytics.clusters.map((c,i) => <g key={i}><circle cx={c.center[0]} cy={c.center[1]} r={c.radius} fill={c.alert ? '#ef444420' : '#fda84a13'} stroke={c.alert ? '#ff5e66' : '#f2c268'} strokeWidth={scale*1.7} strokeDasharray={`${scale*5} ${scale*4}`}/><text x={c.center[0]} y={c.center[1]-c.radius+scale*15} textAnchor="middle" fill={c.alert ? '#ffbdba' : '#ffe2a8'} fontSize={scale*12}>{c.count} personas · {c.duration.toFixed(0)}s</text></g>)}
      {focusArea&&<rect x={focusArea.x} y={focusArea.y} width={focusArea.size} height={focusArea.size} fill="none" stroke="#101d30" strokeWidth={scale*3} strokeDasharray={`${scale*4} ${scale*2}`}/>}
      {layers.cameras && floorCameras.map((c, i) => <g key={c.id} transform={`translate(${c.x},${c.y}) rotate(${-bearing})`} className="map-camera" style={{userSelect:'none',opacity:c.active===false?.45:1}} onPointerDown={e => beginDrag(e,'camera',c.id)} onPointerUp={e => {e.stopPropagation();drag.current=null;panDrag.current=null;onCamera(c.id);}}><circle r={scale*14} fill={!isSetup&&state.cameraAnalytics?.[c.id]?.occupancy?.zones?.some((z:any)=>z.alert)?'#c5353f':!isSetup&&(state.cameraAnalytics?.[c.id]?.occupancy?.count||0)>=(c.crowdThreshold??10)?'#bd790d':selectedCamera===c.id?'#096cbd':'#132b3e'} stroke={c.color || COLORS[i%COLORS.length]} strokeWidth={scale*1.7}/><path d={`M${-scale*7},${-scale*4} h${scale*8} v${scale*8} h${-scale*8}z M${scale*2},0 l${scale*5},${-scale*4}v${scale*8}z`} fill="#c2e5f8"/>{show('labels', lod.cameraLabels) && <text y={scale*29} fill={paper.label} fontSize={scale*11} textAnchor="middle" fontWeight="600">{c.name||c.id}</text>}</g>)}
      {(businessMarkers||(!isSetup&&layers.accesses))&&registeredBusinesses.filter(b=>!b.referencia&&b.estado!=='cerrado'&&b.ubicacion?.planId===config.planId&&(!!businessMarkers||b.puertas.length>0)).map(b=><g key={'business-'+b.id} transform={`translate(${b.ubicacion!.point[0]},${b.ubicacion!.point[1]}) rotate(${-bearing})`} role={b.id===editableBusinessId&&!b.referencia?'button':undefined} tabIndex={b.id===editableBusinessId&&!b.referencia?0:undefined} aria-label={b.id===editableBusinessId&&!b.referencia?`Mover ubicación de ${b.nombre}`:undefined} onKeyDown={e=>{if(b.id!==editableBusinessId||b.referencia||!onBusinessMove)return;const delta:Record<string,Point>={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};const d=delta[e.key];if(!d)return;e.preventDefault();const a=bearing*Math.PI/180,step=scale*(e.shiftKey?10:2),p=b.ubicacion!.point;onBusinessMove([Math.max(0,Math.min(config.width,p[0]+(d[0]*Math.cos(a)+d[1]*Math.sin(a))*step)),Math.max(0,Math.min(config.height,p[1]+(-d[0]*Math.sin(a)+d[1]*Math.cos(a))*step))]);}} style={{touchAction:'none',userSelect:'none',cursor:b.id===editableBusinessId&&!b.referencia?'grab':undefined}} onPointerDown={e=>{if(b.id===editableBusinessId&&!b.referencia&&onBusinessMove){e.preventDefault();e.stopPropagation();panDrag.current=null;businessDrag.current=b.id;moved.current=false;svg.current?.setPointerCapture(e.pointerId);}}}>{b.referencia?<><circle r={scale*14} fill="none" stroke="#147c80" strokeWidth={scale*2.5}/><title>{b.nombre}: negocio vinculado a este local del mapa</title></>:<><circle r={scale*12} fill="#147c80" stroke="white" strokeWidth={scale*1.5}/><path d={`M${-scale*5} ${scale*5}V${-scale*2}H${scale*5}V${scale*5}M${-scale*7} ${-scale*2}L${-scale*5} ${-scale*6}H${scale*5}L${scale*7} ${-scale*2}`} stroke="white" fill="none" strokeWidth={scale*1.4}/><text y={scale*27} fontSize={scale*11} fill={paper.label} stroke={paper.halo} strokeWidth={scale*3} paintOrder="stroke" textAnchor="middle">{b.nombre}</text><title>{b.nombre}: {b.puertas.length} accesos vinculados. La ubicación representa el negocio, no su puerta.</title></>}</g>)}
      {editable && tool==='calibrate' && selected?.pairs.map((p,i) => <g key={i} onPointerDown={e=>{e.stopPropagation();e.preventDefault();panDrag.current=null;pairDrag.current=i;setSelectedPair(i);svg.current?.setPointerCapture(e.pointerId);}}><circle cx={p[2]} cy={p[3]} r={scale*5.5} fill={COLORS[i%COLORS.length]} stroke="#031018" strokeWidth={scale*.8}/><text x={p[2]+scale*9} y={p[3]-scale*3} fontSize={scale*12} fontWeight="600" fill={COLORS[i%COLORS.length]}>{i+1}</text></g>)}
      {editable && tool==='calibrate' && calibrationFootprint?.length===4 && <polygon points={calibrationFootprint.map(p=>p.join(',')).join(' ')} fill="#ffb34018" stroke="#ffb340" strokeWidth={scale*2} strokeDasharray={`${scale*7} ${scale*4}`} pointerEvents="none"><title>Huella proyectada de toda la imagen. Si sale invertida, cruzada o fuera del suelo, revisa las correspondencias.</title></polygon>}
      {editable && tool==='calibrate' && sharedPairs.map(s => <g key={`shared-${s.camera.id}-${s.index}`} pointerEvents="none"><circle cx={s.point[0]} cy={s.point[1]} r={scale*8} fill="none" stroke={s.camera.color || '#9aa7b2'} strokeWidth={scale*1.8} strokeDasharray={`${scale*3} ${scale*2}`}/><circle cx={s.point[0]} cy={s.point[1]} r={scale*1.6} fill={s.camera.color || '#9aa7b2'}/><text x={s.point[0]+scale*11} y={s.point[1]+scale*4} fontSize={scale*10} fontWeight="600" fill={s.camera.color || '#9aa7b2'} stroke="#031018" strokeWidth={scale*2.2} paintOrder="stroke">{s.camera.id}·{s.index+1}</text></g>)}
      {!isSetup&&show('metrics', lod.metrics)&&floorCameras.map(c=>{const a=state.cameraAnalytics?.[c.id];if(!a)return null;const entries=(a.crossings||[]).reduce((n:number,l:any)=>n+l.entries,0),exits=(a.crossings||[]).reduce((n:number,l:any)=>n+l.exits,0);const alerta=a.occupancy?.zones?.some((z:any)=>z.alert);return <g key={`metrics-${c.id}`} transform={`translate(${c.x},${c.y}) rotate(${-bearing})`} pointerEvents="none"><rect x={scale*20} y={-scale*40} width={scale*190} height={scale*50} rx={scale*6} fill="white" stroke={alerta?'#d92d43':'#126494'} strokeWidth={scale*2}/><text x={scale*28} y={-scale*22} fontSize={scale*11} fill="#126494">{`Personas en la imagen: ${a.occupancy?.count??0}`}</text><text x={scale*28} y={-scale*5} fontSize={scale*11} fill="#243746">{a.crossings?.length?`${entries} entradas · ${exits} salidas`:`Máximo: ${a.occupancy?.peak??0}`}</text><title>{(a.crossings||[]).map((l:any)=>`${l.name}: ${l.entries} entradas, ${l.exits} salidas`).join(' · ')}. Conteo del seguimiento dentro de la zona útil de la cámara.</title></g>;})}
      {!isSetup&&layers.accesses&&floorCameras.flatMap(c=>(state.cameraAnalytics?.[c.id]?.crossings||[]).filter((l:any)=>l.place&&(l.place.planId||c.planId)===config.planId).map((l:any)=><g key={'access-'+c.id+l.id} transform={`translate(${l.place.point[0]},${l.place.point[1]}) rotate(${-bearing})`} onPointerUp={e=>{e.stopPropagation();onCamera(c.id);}} style={{cursor:'pointer'}}><rect x={-scale*22} y={-scale*10} width={scale*44} height={scale*20} rx={scale*5} fill="#126b67" stroke="white" strokeWidth={scale}/><text fontSize={scale*10} fill="white" textAnchor="middle" y={scale*4}>↑{l.entries} ↓{l.exits}</text><title>{l.place.name} / {l.name}: {l.entries} entradas y {l.exits} salidas. Cámara {c.name||c.id}.</title></g>))}
      {editable&&esHerramientaDeTrazo(tool)&&draft.length>0&&cursor&&<line pointerEvents="none" x1={draft[0][0]} y1={draft[0][1]} x2={cursor[0]} y2={cursor[1]} stroke="#ffffff" strokeWidth={scale*1.4} strokeDasharray={`${scale*6} ${scale*4}`} opacity=".8"/>}
      {draft.length > 0 && <g><polyline points={draft.map(p=>p.join(',')).join(' ')} fill="#ffb34022" stroke="#ffce81" strokeWidth={scale*2}/>{draft.map((p,i)=><circle key={i} cx={p[0]} cy={p[1]} r={scale*4} fill="#ffce81"/>)}</g>}
      {groups.map(g => {
        if (g.count > 1) {
          // El radio crece con la raíz de la cuenta para que el área, y no el ancho,
          // sea lo proporcional a cuánta gente hay dentro.
          const r = scale * Math.min(20, 7 + Math.sqrt(g.count) * 2.6);
          return <g key={g.key} transform={`translate(${g.point[0]},${g.point[1]})`} className="map-person map-cluster" style={{cursor:'zoom-in'}} onPointerUp={e => {e.stopPropagation(); zoomToGroup(g);}}>
            <circle r={r*1.5} fill={g.uncertain?'#ffb34026':'#21a8ff22'}/>
            <circle r={r} fill={g.uncertain?'#e8952a':'#1b86d8'} stroke="#061c31" strokeWidth={scale*1.2}/>
            <text textAnchor="middle" y={scale*3.4} fontSize={scale*(g.count>99?8:10)} fontWeight="700" fill="#ffffff" transform={`rotate(${-bearing})`}>{g.count}</text>
            <title>{g.count} personas en este punto{g.uncertain?', alguna con identidad dudosa':''}. Toca para acercarte y verlas por separado.</title>
          </g>;
        }
        const p = g.members[0].person, label = labelOffset.get(g.key) || (peopleFirst ? {dx:scale*7,dy:-scale*6} : undefined);
        return <g key={g.key} transform={`translate(${g.point[0]},${g.point[1]})`} className="map-person" onPointerUp={e => {e.stopPropagation(); onPerson?.(p);}}>
          <circle r={scale*(selectedPerson===p.id ? 8.5 : peopleFirst ? 5.2 : 5.4)} fill={p.association==='uncertain' ? '#ffb340' : '#21a8ff'} stroke="#03111f" strokeWidth={scale*(peopleFirst ? 1.4 : 1.5)}/>
          {label && <text x={label.dx} y={label.dy} fontSize={scale*(peopleFirst ? 9.5 : 10)} fontWeight="700" fill="#ffffff" stroke="#061c31" strokeWidth={scale*(peopleFirst?2.2:2.4)} paintOrder="stroke" transform={`rotate(${-bearing})`}>{p.id}{p.association==='uncertain' ? ' ?' : p.association==='estimated' || p.association==='reidentified' ? ' ~' : ''}</text>}
          {show('prediction', lod.prediction) && p.velocity && <path d={`M0,0 L${p.velocity[0]*2},${p.velocity[1]*2}`} stroke="#ffc777" strokeDasharray={`${scale*4} ${scale*3}`} strokeWidth={scale*1.4}/>}
        </g>;
      })}
    </g>
      {bounded&&<polygon points={config.workArea!.map(p=>p.join(',')).join(' ')} fill="none" stroke="#c9790a" strokeWidth={scale*2}/>}
      {areaEditing&&areaDraft.length>0&&<g><polygon points={areaDraft.map(p=>p.join(',')).join(' ')} fill="#c9790a20" stroke="#c9790a" strokeWidth={scale*2}/>{areaDraft.map((p,i)=><g key={i} onPointerDown={e=>beginDrag(e,'work',i)}><circle cx={p[0]} cy={p[1]} r={scale*7} fill="#c9790a"/><text x={p[0]+scale*10} y={p[1]} fill="#ffffff" fontSize={scale*12}>{i+1}</text></g>)}</g>}
    </g></svg>{showLayers && <div className="layer-menu" id={`${pattern}-layers`} onKeyDown={e=>{if(e.key==='Escape')setShowLayers(false);}}><div className="layer-menu-heading"><div><strong>Capas del mapa</strong><p>Elige qué información mostrar</p></div><button aria-label="Cerrar capas" onClick={()=>setShowLayers(false)}>×</button></div>{!isSetup&&<label className="layer-auto"><input type="checkbox" checked={autoDetail} onChange={()=>setAutoDetail(v=>!v)}/><span>Detalle según el zoom<small> · Agrupa personas y oculta capas cuando el plano se ve completo. Desactívalo para mostrar todo siempre.</small></span></label>}{Object.entries({ accesses:'Accesos asociados a locales', metrics: 'Conteos y accesos por cámara', cameras: 'Cámaras', labels: 'Etiquetas e IDs', trajectories: 'Recorridos recientes (6 s)', heat: 'Presencia acumulada', prediction: 'Dirección estimada', flow:'Direcciones predominantes', zones: 'Zonas dibujadas' }).filter(([key])=>!isSetup||!['accesses','metrics','heat','trajectories','prediction','flow'].includes(key)).map(([key,label])=><label key={key}><input type="checkbox" checked={layers[key as keyof typeof layers]} onChange={()=>setLayers({...layers,[key]:!layers[key as keyof typeof layers]})}/><span>{label}{key==='zones'&&!config.zones.length&&<small> · Sin zonas del plano configuradas</small>}{key==='trajectories'&&!people.some(p=>p.history.length>1)&&<small> · Sin recorridos en este instante</small>}{key==='prediction'&&!people.some(p=>p.velocity)&&<small> · Sin dirección disponible</small>}</span></label>)}</div>}
      {!config.mapConfigured && !config.background && !config.zones.length && state.mode !== 'demo' && <div className="map-empty"><Icon name="map" size={30}/><strong>Plano no configurado</strong><span>Importa tu plano o define un espacio en blanco.<br/>Después coloca y calibra tus cámaras.</span></div>}
      {!isSetup&&<div className="detail-indicator" title={peopleFirst?'Cada persona conserva su punto, ID y recorrido reciente.':autoDetail?DETALLE[level].hint:'Se muestran todas las capas sin importar el zoom.'}>
        <strong>{peopleFirst?'Nodos individuales':autoDetail?DETALLE[level].label:'Detalle completo'}</strong>
        <span>{mag<1?'plano completo':`${mag.toFixed(mag<10?1:0)}× aumento`}{groups.length<people.length?` · ${people.length} personas en ${groups.length} grupos`:people.length?` · ${people.length} ${people.length===1?'persona':'personas'}`:''}</span>
      </div>}
      <div className="scale-indicator"><span title="Distancia aproximada en el plano, no precisión de calibración">{config.unit==='meters'?'Escala aprox.':'Escala relativa'} · {(scale*80).toFixed(1)} {config.unit==='meters'?'m':'u'}</span><i style={{display:'block',width:80,height:5,border:'1px solid currentColor',borderTop:0}}/></div>
    </div>{config.mapAsset&&<details className="map-attribution"><summary>Información cartográfica</summary><p>© Living Map · Lima Airport Partners. Referencia local con escala aproximada. <a href="https://map.lima-airport.com/" target="_blank" rel="noreferrer">Ver mapa oficial</a></p></details>}<div className="map-caption compact-map-legend">{!isSetup&&<><span><i className="legend-swatch presence"/>Presencia acumulada</span><span><i className="legend-swatch concentration"/>Concentración</span><span><i className="legend-swatch alert"/>Alerta</span></>}<span className="map-gesture-help">Arrastrar para mover · Rueda para ampliar</span></div>
  </div>;
}
