import { useTracking } from '../../hooks/useTracking';
import { usePersons } from '../../hooks/usePersons';
import type { CameraId } from '../../types/camera';

/** Posicion horizontal (0..100) del chip de una persona: pegado a la
 * cámara real que la ve, al centro mientras el punto cae dentro del
 * alcance de las dos a la vez (fusion). */
function chipPosition(cameras: CameraId[]): number {
  if (cameras.length >= 2) return 50;
  if (cameras[0] === 'A') return 14;
  return 86;
}

export function IdentityFlow() {
  const { state, selectPerson } = useTracking();
  const persons = usePersons();

  return (
    <div className="flex h-16 shrink-0 items-center gap-4 rounded-md border border-hairline bg-surface px-4">
      <div className="font-mono text-[11px] font-bold text-camA">CÁMARA A</div>
      <div className="relative h-8 flex-1">
        <div className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-hairline" />
        <div className="absolute inset-y-0 left-[42%] right-[42%] rounded bg-status-warning/10" />
        {persons.map((p) => (
          <button
            key={p.id}
            onClick={() => selectPerson(p.id)}
            className="absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold transition-[left] duration-700 ease-in-out"
            style={{
              left: `${chipPosition(p.cameras)}%`,
              borderColor: p.color,
              color: p.color,
              background: p.id === state.selectedPersonId ? `${p.color}26` : 'transparent',
            }}
            title={`ID ${p.id} · ${p.status}`}
          >
            {p.id}
          </button>
        ))}
      </div>
      <div className="font-mono text-[11px] font-bold text-camB">CÁMARA B</div>
    </div>
  );
}
