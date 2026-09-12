import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import Icon from './Icon';
import type { Session } from './useSession';

type Rect = { x: number; y: number; w: number; h: number };
type Drag = { mode: 'move' | 'nw' | 'ne' | 'sw' | 'se'; startRect: Rect; startX: number; startY: number };

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export default function PlanCropper({ src, session, targetWidth, onConfirm, onCancel }: {
  src: string; session: Session; targetWidth: number;
  onConfirm: (background: string, width: number, height: number, warnings: string[] | undefined) => void;
  onCancel: () => void;
}) {
  const stage = useRef<HTMLDivElement>(null);
  const img = useRef<HTMLImageElement>(null);
  const [rect, setRect] = useState<Rect>({ x: .08, y: .08, w: .84, h: .84 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const drag = useRef<Drag | null>(null);

  function ratio(e: PointerEvent): [number, number] {
    const box = stage.current!.getBoundingClientRect();
    return [(e.clientX - box.left) / box.width, (e.clientY - box.top) / box.height];
  }
  function begin(e: PointerEvent, mode: Drag['mode']) {
    e.stopPropagation();
    const [x, y] = ratio(e);
    drag.current = { mode, startRect: rect, startX: x, startY: y };
    stage.current?.setPointerCapture(e.pointerId);
  }
  function onMove(e: PointerEvent) {
    if (!drag.current) return;
    const [x, y] = ratio(e);
    const dx = x - drag.current.startX, dy = y - drag.current.startY;
    const s = drag.current.startRect;
    let next: Rect = s;
    if (drag.current.mode === 'move') {
      next = { ...s, x: clamp(s.x + dx, 0, 1 - s.w), y: clamp(s.y + dy, 0, 1 - s.h) };
    } else {
      let { x: rx, y: ry, w, h } = s;
      if (drag.current.mode.includes('w')) { const nx = clamp(s.x + dx, 0, s.x + s.w - .04); w = s.x + s.w - nx; rx = nx; }
      if (drag.current.mode.includes('e')) { w = clamp(s.w + dx, .04, 1 - s.x); }
      if (drag.current.mode.includes('n')) { const ny = clamp(s.y + dy, 0, s.y + s.h - .04); h = s.y + s.h - ny; ry = ny; }
      if (drag.current.mode.includes('s')) { h = clamp(s.h + dy, .04, 1 - s.y); }
      next = { x: rx, y: ry, w, h };
    }
    setRect(next);
  }
  async function send(rx: number, ry: number, rw: number, rh: number) {
    const el = img.current;
    if (!el || busy) return;
    setBusy(true); setError('');
    try {
      const sx = rx * el.naturalWidth, sy = ry * el.naturalHeight;
      const sw = rw * el.naturalWidth, sh = rh * el.naturalHeight;
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(sw));
      canvas.height = Math.max(1, Math.round(sh));
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('No se pudo preparar el recorte.');
      ctx.drawImage(el, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
      const blob: Blob = await new Promise((resolve, reject) => canvas.toBlob(b => b ? resolve(b) : reject(new Error('No se pudo generar la imagen recortada.')), 'image/png'));
      const result = await session.post(`plan-lines?width=${targetWidth}`, blob, true);
      onConfirm(result.background, result.width, result.height, result.warnings);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el plano a partir de la imagen.');
    } finally {
      setBusy(false);
    }
  }

  const handles: Drag['mode'][] = ['nw', 'ne', 'sw', 'se'];
  return <div className="plan-cropper-backdrop">
    <div className="plan-cropper">
      <div className="plan-cropper-head"><h3>Recorta la zona real del plano</h3><p>El documento importado suele incluir cuadros, sellos o mapas de ubicación. Marca solo el área que representa el espacio a monitorear — el sistema convierte esa zona en un dibujo de líneas, no usa la foto tal cual.</p></div>
      <div className="plan-cropper-stage" ref={stage} onPointerMove={onMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        <img ref={img} src={src} alt="Plano importado, sin recortar" draggable={false}/>
        <div className="crop-mask" style={{ clipPath: `polygon(0 0,100% 0,100% 100%,0 100%,0 ${rect.y*100}%,${rect.x*100}% ${rect.y*100}%,${rect.x*100}% ${(rect.y+rect.h)*100}%,${(rect.x+rect.w)*100}% ${(rect.y+rect.h)*100}%,${(rect.x+rect.w)*100}% ${rect.y*100}%,0 ${rect.y*100}%)` }}/>
        <div className="crop-rect" style={{ left: `${rect.x*100}%`, top: `${rect.y*100}%`, width: `${rect.w*100}%`, height: `${rect.h*100}%` }} onPointerDown={e => begin(e, 'move')}>
          {handles.map(h => <i key={h} className={`crop-handle ${h}`} onPointerDown={e => begin(e, h)}/>)}
        </div>
        {busy && <div className="crop-busy"><span className="loader"/><span>Generando líneas del plano…</span></div>}
      </div>
      {error && <p className="notice compact error-inline">{error}</p>}
      <div className="plan-cropper-actions">
        <button disabled={busy} onClick={onCancel}><Icon name="arrow" size={14}/> Cancelar importación</button>
        <button disabled={busy} onClick={() => void send(0, 0, 1, 1)}>Usar el documento completo</button>
        <button className="primary" disabled={busy} onClick={() => void send(rect.x, rect.y, rect.w, rect.h)}><Icon name="check" size={14}/> Recortar y generar plano</button>
      </div>
    </div>
  </div>;
}
