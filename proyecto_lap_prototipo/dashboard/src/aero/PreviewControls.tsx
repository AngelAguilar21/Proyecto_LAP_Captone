import { useEffect } from 'react';
import type { Camera } from './types';
import { formatTime, isActive, isStream } from './types';
import type { Session } from './useSession';
import Icon from './Icon';

/** Controles de la vista en vivo: reproducir, pausar y moverse por el video.
 * El servidor suelta la cámara solo si nadie mira, así que al salir del paso no
 * queda el celular transmitiendo. */
export default function PreviewControls({ session, camera }: { session: Session; camera: Camera }) {
  const preview = session.state.preview;
  const mine = preview?.camera === camera.id;
  const playing = !!mine && !!preview?.playing;
  const live = isStream(camera.source) || !!preview?.live;
  const blocked = isActive(session.state.status);

  const send = (action: string, seconds?: number) => void session.action(async () => {
    await session.post('preview', { camera: camera.id, action, seconds });
  });

  // Al cambiar de cámara o salir, corta la transmisión anterior.
  useEffect(() => () => { if (mine) void session.post('preview', { action: 'stop' }).catch(() => {}); }, [camera.id]);

  return <div className="preview-controls">
    {!playing
      ? <button className="primary" disabled={blocked || session.busy || camera.source === ''} onClick={() => send('start', 0)}>
          <Icon name="eye" size={15} /> {mine ? 'Reanudar' : 'Ver en vivo'}
        </button>
      : <button disabled={session.busy} onClick={() => send('pause')}>Ⅱ Pausar</button>}
    {mine && <button disabled={session.busy} onClick={() => send('stop')}>Detener</button>}

    {mine && !live && (preview?.duration || 0) > 0 && <label className="preview-seek">
      <input type="range" min={0} max={Math.round(preview!.duration)} step={1} value={Math.round(preview!.t)}
        onChange={e => send('seek', +e.target.value)} aria-label="Instante del video" />
      <span>{formatTime(preview!.t)} / {formatTime(preview!.duration)}</span>
    </label>}

    {mine && live && playing && <span className="preview-flag"><i /> En vivo</span>}
    {blocked && <span className="subtle">Hay una sesión de seguimiento en curso: finalízala para usar la vista en vivo.</span>}
    {mine && preview?.error && <span className="preview-error">{preview.error}</span>}
  </div>;
}
