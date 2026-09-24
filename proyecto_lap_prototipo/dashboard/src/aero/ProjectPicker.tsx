import type { Session } from './useSession';
import Icon from './Icon';

/** Al abrir el sistema con varios proyectos guardados hay que elegir uno antes
 * de entrar: así no se trabaja por error sobre el plano de otro espacio. */
export default function ProjectPicker({ session, onEnter }: { session: Session; onEnter: () => void }) {
  const { projects } = session;
  function enter(id: string) {
    if (id === projects.active) return onEnter();
    void session.action(async () => { await session.projectAction('open', { id }); onEnter(); });
  }
  return <div className="aero connection-screen">
    <div className="aero-logo"><Icon name="plane" size={38} /><strong>AeroTrack</strong></div>
    <div className="picker-card">
      <h1>¿En qué proyecto quieres trabajar?</h1>
      <p>Cada proyecto tiene su propio plano y sus cámaras. Elige uno para no mezclar espacios.</p>
      <div className="picker-list">
        {projects.projects.map(p => <button key={p.id} disabled={session.busy} onClick={() => enter(p.id)}>
          <Icon name="map" size={22} />
          <span>
            <strong>{p.name}</strong>
            <small>{p.airport || 'Sin aeropuerto'}{p.floor ? ` · ${p.floor}` : ''}</small>
            <small>{p.cameras} {p.cameras === 1 ? 'cámara' : 'cámaras'}{p.setupComplete ? '' : ' · configuración incompleta'}</small>
          </span>
          {p.id === projects.active && <span className="pill muted">Último abierto</span>}
        </button>)}
      </div>
      {session.error && <p className="notice error" role="alert">{session.error}</p>}
    </div>
  </div>;
}
