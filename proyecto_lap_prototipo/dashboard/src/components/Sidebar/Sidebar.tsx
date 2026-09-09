import type { ReactNode } from 'react';
import { useTracking } from '../../hooks/useTracking';
import type { CameraFilter, LayerVisibility, StatusFilter } from '../../types/tracking';

function SectionLabel({ children }: { children: string }) {
  return <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{children}</div>;
}

function SegButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2.5 py-1.5 text-left text-xs transition-colors ${
        active ? 'bg-series-1/15 text-series-1' : 'text-ink-secondary hover:bg-surface-2'
      }`}
    >
      {children}
    </button>
  );
}

const LAYER_ITEMS: { key: keyof LayerVisibility; label: string }[] = [
  { key: 'persons', label: 'Personas' },
  { key: 'coverageA', label: 'Cobertura Cámara A' },
  { key: 'coverageB', label: 'Cobertura Cámara B' },
  { key: 'trajectories', label: 'Trayectorias' },
  { key: 'connections', label: 'Conexiones' },
  { key: 'transitionZone', label: 'Zona de transición' },
];

const CAMERA_FILTERS: { value: CameraFilter; label: string }[] = [
  { value: 'all', label: 'Todas' },
  { value: 'A', label: 'Cámara A' },
  { value: 'B', label: 'Cámara B' },
];

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'active', label: 'Activos' },
  { value: 'transitioning', label: 'Transicionando' },
];

export function Sidebar() {
  const { state, setCameraFilter, setStatusFilter, toggleLayer } = useTracking();

  return (
    <aside className="flex w-52 shrink-0 flex-col gap-6 overflow-y-auto border-r border-hairline bg-surface p-4">
      <div>
        <SectionLabel>Cámaras</SectionLabel>
        <div className="flex flex-col gap-1">
          {CAMERA_FILTERS.map((f) => (
            <SegButton key={f.value} active={state.cameraFilter === f.value} onClick={() => setCameraFilter(f.value)}>
              {f.label}
            </SegButton>
          ))}
        </div>
      </div>

      <div>
        <SectionLabel>Capas del mapa</SectionLabel>
        <div className="flex flex-col gap-1.5">
          {LAYER_ITEMS.map((item) => (
            <label key={item.key} className="flex cursor-pointer items-center gap-2 text-xs text-ink-secondary">
              <input
                type="checkbox"
                checked={state.layers[item.key]}
                onChange={() => toggleLayer(item.key)}
                className="h-3.5 w-3.5 accent-series-1"
              />
              {item.label}
            </label>
          ))}
        </div>
      </div>

      <div>
        <SectionLabel>Estado</SectionLabel>
        <div className="flex flex-col gap-1">
          {STATUS_FILTERS.map((f) => (
            <SegButton key={f.value} active={state.statusFilter === f.value} onClick={() => setStatusFilter(f.value)}>
              {f.label}
            </SegButton>
          ))}
        </div>
      </div>
    </aside>
  );
}
