import { useEffect, useRef, useState } from 'react';
import type { Point, Zone } from './types';

export const COLORS = ['#12b8a6', '#e5a032', '#818cf8', '#fb7185', '#38bdf8'];

export default function VideoCanvas({ revision, visible, zones, points = [], draft = [], drawing = false, onPoint, grid, showPoints = true, fitHeight }: {
  fitHeight?: number; revision: string | number; visible: boolean; zones: Zone[]; points?: Point[]; draft?: Point[];
  drawing?: boolean; onPoint?: (p: Point) => void; grid?: number[][]; showPoints?: boolean;
}) {
  const [aspect,setAspect]=useState(16/9);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => { setFailed(false); }, [revision]);
  useEffect(() => {
    const ctx = canvas.current?.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, 400, 240);
    if (!grid?.length) return;
    const max = Math.max(1, ...grid.flat());
    grid.forEach((row, y) => row.forEach((v, x) => {
      if (v <= 0) return;
      const ratio = v / max;
      ctx.fillStyle = `hsla(${175 - ratio * 165}, 95%, 55%, ${.2 + ratio*.5})`;
      ctx.fillRect(x*10, y*10, 10, 10);
    }));
  }, [grid, loaded]);
  return <div className={`count-video ${drawing ? 'is-drawing' : ''}`}>
    {visible && !failed ? <div className="count-frame" style={fitHeight?{maxWidth:fitHeight*aspect}:undefined}>
      <img src={`/api/counting/frame?v=${revision}`} alt="Imagen de la fuente de conteo" onLoad={e=>{setLoaded(true);setAspect(e.currentTarget.naturalWidth/e.currentTarget.naturalHeight);}} onError={()=>{setFailed(true);setLoaded(false);}} />
      <canvas ref={canvas} width={400} height={240} className="count-heat" aria-hidden="true" />
      <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label={drawing ? 'Selecciona al menos tres vértices de la zona en la imagen' : 'Zonas de conteo y cabezas detectadas'}
        onClick={e => { if (!drawing || !onPoint || !loaded) return; const r=e.currentTarget.getBoundingClientRect(); onPoint([Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]); }}>
        {zones.map((z, i) => <polygon key={z.id} points={z.points.map(p=>`${p[0]*1000},${p[1]*1000}`).join(' ')} fill={`${COLORS[i%COLORS.length]}12`} stroke={COLORS[i%COLORS.length]} strokeWidth={2} vectorEffect="non-scaling-stroke" />)}
        {showPoints && points.map((p,i)=><circle key={i} cx={p[0]*1000} cy={p[1]*1000} r={4} fill="#55ffb5" stroke="#07382b" strokeWidth={1} />)}
        {draft.length>0&&<><polyline points={draft.map(p=>`${p[0]*1000},${p[1]*1000}`).join(' ')} stroke="#ffd166" strokeWidth={3} fill="#ffd16622" vectorEffect="non-scaling-stroke"/>{draft.map((p,i)=><circle key={i} cx={p[0]*1000} cy={p[1]*1000} r={6} fill="#ffd166"/>)}</>}
      </svg>
    </div> : <div className="count-video-empty"><span className="count-empty-symbol">▷</span><h3>{failed ? 'Imagen no disponible' : 'Tu video, listo para analizar'}</h3><p>{failed ? 'Obtén una nueva imagen desde Preparar video.' : 'Selecciona un archivo y pulsa «Obtener imagen». No necesitas un plano ni calibración.'}</p></div>}
    {drawing && <div className="count-draw-hint">Marca el contorno del área útil · {draft.length} puntos</div>}
  </div>;
}
