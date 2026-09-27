import { useState } from 'react';
import type { Session } from './useSession';
import { isActive } from './types';
import Icon from './Icon';

/** Gestión de proyectos, compartida por los dos roles.
 *
 * Crear y eliminar proyectos es administrar el espacio de trabajo, no configurar
 * cámaras ni plano, así que el administrador también entra aquí. Lo que sigue
 * siendo solo del operador es el contenido de cada proyecto.
 *
 * Vive en un componente aparte para que la sección propia del administrador y el
 * inicio del operador usen la misma lista: con dos copias, una acabaría
 * comportándose distinto de la otra.
 */

export function since(updated: number) {
  const minutes = Math.max(0, (Date.now() / 1000 - updated) / 60);
  if (minutes < 1) return 'hace un momento';
  if (minutes < 60) return `hace ${Math.round(minutes)} min`;
  if (minutes < 1440) return `hace ${Math.round(minutes / 60)} h`;
  return new Date(updated * 1000).toLocaleDateString('es-PE', { timeZone: 'America/Lima' });
}

export default function ProjectsPanel({ session, onConfigure, onCreated }: {
  session: Session; onConfigure?: () => void; onCreated?: () => void;
}) {
  const { projects } = session;
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [renaming, setRenaming] = useState('');
  const running = isActive(session.state.status);
  const busy = session.busy || running;
  const puedeConfigurar = session.auth.rol === 'operador';

  // El nombre repetido lo rechaza el servidor; avisarlo antes evita perder lo escrito.
  const igual = (a: string, b: string) =>
    a.split(/\s+/).join(' ').toLocaleLowerCase() === b.split(/\s+/).join(' ').toLocaleLowerCase();
  const repetido = name.trim() !== '' && projects.projects.some(p => igual(p.name, name));

  function create() {
    if (!name.trim() || repetido) return;
    void session.action(async () => {
      await session.projectAction('create', { name: name.trim() });
      setCreating(false); setName('');
      session.setNotice(puedeConfigurar
        ? 'Proyecto creado. Sigue los pasos para configurarlo.'
        : 'Proyecto creado y abierto. Un operador debe cargar su plano y sus cámaras.');
      onCreated?.();
    });
  }
  function open(id: string) {
    if (id === projects.active) return;
    void session.action(async () => { await session.projectAction('open', { id }); session.setNotice('Proyecto abierto.'); });
  }
  function rename(id: string, value: string) {
    if (!value.trim()) return setRenaming('');
    void session.action(async () => { await session.projectAction('rename', { id, name: value }); setRenaming(''); });
  }
  function remove(id: string, label: string) {
    if (!confirm(`Se eliminará "${label}" con su plano, cámaras, calibración e incidentes. Esta acción no se puede deshacer.`)) return;
    void session.action(async () => { await session.projectAction('delete', { id }); session.setNotice('Proyecto eliminado.'); });
  }

  const ultimo = projects.projects.length < 2;

  return <>
    <div className="section-label">
      <h3>Proyectos guardados</h3>
      <span>{projects.projects.length}</span>
      {!creating && <button disabled={busy} onClick={() => setCreating(true)}><Icon name="plus" size={14} /> Nuevo proyecto</button>}
    </div>

    {creating && <div className="project-create">
      <label>Nombre del proyecto
        <input autoFocus value={name} placeholder="Universidad · Pabellón A" onChange={e => setName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') create(); if (e.key === 'Escape') { setCreating(false); setName(''); } }} />
      </label>
      <button className="primary" disabled={!name.trim() || repetido || session.busy} onClick={create}>
        {puedeConfigurar ? 'Crear y configurar' : 'Crear proyecto'}
      </button>
      <button onClick={() => { setCreating(false); setName(''); }}>Cancelar</button>
      {repetido && <p className="notice warning" role="alert"><Icon name="alert" /> Ya hay un proyecto con ese nombre. Cada proyecto es un espacio distinto y necesita un nombre propio.</p>}
    </div>}

    {running && <div className="notice warning"><Icon name="alert" /> Hay una sesión en curso. Finalízala para crear, cambiar o eliminar proyectos.</div>}

    <div className="project-list">
      {projects.projects.map(p => <article key={p.id} className={p.id === projects.active ? 'project-card current' : 'project-card'}>
        <div className="project-card-main">
          {renaming === p.id
            ? <input autoFocus defaultValue={p.name} onBlur={e => rename(p.id, e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') rename(p.id, (e.target as HTMLInputElement).value); if (e.key === 'Escape') setRenaming(''); }} />
            : <strong>{p.name}</strong>}
          <small>{p.airport || 'Sin espacio definido'}{p.floor ? ` · ${p.floor}` : ''}</small>
          <div className="project-card-meta">
            <span>{p.cameras} {p.cameras === 1 ? 'cámara' : 'cámaras'}</span>
            <span>{p.plans} {p.plans === 1 ? 'plano' : 'planos'}</span>
            <span>Editado {since(p.updated)}</span>
          </div>
        </div>
        <div className="project-card-side">
          <span className={`pill ${p.setupComplete ? 'good' : 'warn'}`}>{p.setupComplete ? 'Configurado' : 'Incompleto'}</span>
          {p.id === projects.active
            ? (onConfigure && puedeConfigurar
                ? <button className="primary" disabled={busy} onClick={onConfigure}>Continuar configuración</button>
                : <span className="pill muted">Abierto</span>)
            : <button disabled={busy} onClick={() => open(p.id)}>Abrir</button>}
          <div className="project-card-tools">
            <button disabled={busy} onClick={() => setRenaming(p.id)}>Renombrar</button>
            <button className="danger ghost" disabled={busy || ultimo} title={ultimo ? 'Crea otro proyecto antes de eliminar este.' : undefined}
              onClick={() => remove(p.id, p.name)}><Icon name="trash" size={14} /> Eliminar</button>
          </div>
        </div>
      </article>)}
      {!projects.projects.length && <p className="empty-text">Todavía no hay proyectos guardados. Crea el primero para empezar.</p>}
    </div>

    {ultimo && !!projects.projects.length && <p className="subtle">Para eliminar el proyecto abierto primero crea otro: el sistema no se queda sin ninguno.</p>}
  </>;
}
