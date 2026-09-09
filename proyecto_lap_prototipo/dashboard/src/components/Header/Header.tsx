import { useTracking } from '../../hooks/useTracking';
import { useCameras } from '../../hooks/useCameras';
import { REAL_SESSION } from '../../data/realSession';
import { formatVideoTime } from '../../utils/format';

const SPEEDS = [0.25, 0.5, 1] as const;

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="font-mono text-sm font-semibold tabular-nums" style={{ color: accent }}>
        {value}
      </span>
      <span className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</span>
    </div>
  );
}

function Divider() {
  return <div className="h-8 w-px bg-hairline" aria-hidden />;
}

export function Header() {
  const { state, setMode, togglePlay, seekFrame, setSpeed } = useTracking();
  const cameras = useCameras();

  const camerasOnline = Object.values(cameras).filter((c) => c.status === 'online').length;
  const activePersons = Object.keys(state.persons).length;
  const transitioning = Object.values(state.persons).filter((p) => p.status === 'transitioning').length;
  const { totalBins, duracionTotal, paso } = REAL_SESSION.meta;

  return (
    <header className="flex h-14 shrink-0 items-center gap-5 border-b border-hairline bg-surface px-5">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 items-center justify-center rounded bg-series-1/15 font-mono text-xs font-bold text-series-1">
          LAP
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-ink-primary">Consola de Tracking</div>
          <div className="text-[10px] text-ink-muted">Cámara A + Cámara B · misma losa</div>
        </div>
      </div>

      <Divider />

      <div className="flex items-center gap-6">
        <Metric label="Tracking" value="ONLINE" accent="#0ca30c" />
        <Metric label="Cámaras" value={`${camerasOnline}/2`} />
        <Metric label="Personas en cuadro" value={String(activePersons)} />
        <Metric label="Transicionando" value={String(transitioning)} accent={transitioning > 0 ? '#fab219' : undefined} />
      </div>

      <Divider />

      <div className="flex flex-1 items-center gap-3">
        <div className="flex overflow-hidden rounded border border-hairline font-mono text-[11px] font-semibold">
          <button
            onClick={() => setMode('demo')}
            className={`px-2.5 py-1 transition-colors ${state.mode === 'demo' ? 'bg-series-1 text-plane' : 'text-ink-muted hover:text-ink-secondary'}`}
          >
            REPLAY
          </button>
          <button
            disabled
            title="Se habilita cuando proyecto_lap_prototipo exponga un backend en vivo"
            className="cursor-not-allowed px-2.5 py-1 text-ink-muted/40"
          >
            LIVE
          </button>
        </div>

        <button
          onClick={togglePlay}
          aria-label={state.playing ? 'Pausar' : 'Reproducir'}
          className="flex h-7 w-7 items-center justify-center rounded border border-hairline text-ink-secondary transition-colors hover:border-series-1 hover:text-series-1"
        >
          {state.playing ? '⏸' : '▶'}
        </button>

        <input
          type="range"
          min={0}
          max={totalBins - 1}
          value={state.frameIndex}
          onChange={(e) => seekFrame(Number(e.target.value))}
          className="h-1 flex-1 max-w-[220px] accent-series-1"
        />

        <span className="whitespace-nowrap font-mono text-xs tabular-nums text-ink-secondary">
          {formatVideoTime(state.frameIndex * paso)} <span className="text-ink-muted">/ {formatVideoTime(duracionTotal)}</span>
        </span>

        <div className="flex overflow-hidden rounded border border-hairline font-mono text-[11px] font-semibold">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              title={`Velocidad ${s}×`}
              className={`px-2 py-1 transition-colors ${state.speed === s ? 'bg-series-1 text-plane' : 'text-ink-muted hover:text-ink-secondary'}`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
