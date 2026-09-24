import { useState } from 'react';
import type { Session } from './useSession';
import { isActive } from './types';
import Icon from './Icon';

function since(updated: number) {
  const minutes = Math.max(0, (Date.now() / 1000 - updated) / 60);
  if (minutes < 1) return 'hace un momento';
  if (minutes < 60) return `hace ${Math.round(minutes)} min`;
  if (minutes < 1440) return `hace ${Math.round(minutes / 60)} h`;
  return new Date(updated * 1000).toLocaleDateString('es-PE', { timeZone: 'America/Lima' });
}

function UsersPanel({ session }: { session: Session }) {
  const [abierto, setAbierto] = useState(false);
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [rol, setRol] = useState('administrador');

  function crear() {
    void session.action(async () => {
      await session.userAction('crear', { usuario, clave, rol });
      setUsuario(''); setClave('');
      session.setNotice('Usuario creado.');
    });
  }
  function eliminar(nombre: string) {
    if (!confirm(`Se eliminará el usuario "${nombre}" y se cerrará su sesión.`)) return;
    void session.action(async () => {
      await session.userAction('eliminar', { usuario: nombre });
      session.setNotice('Usuario eliminado.');
    });
  }

  return <section className="aero-panel users-panel">
    <div className="panel-heading">
      <div><h2>Usuarios del sistema</h2><p className="subtle">El operador configura cámaras y plano. El administrador ve resultados y ajusta umbrales de alerta, sin entrar a Configuración.</p></div>
      <button onClick={() => setAbierto(v => !v)}>{abierto ? 'Ocultar' : `Ver (${session.auth.usuarios.length})`}</button>
    </div>
    {abierto && <div className="users-body">
      <div className="users-list">
        {session.auth.usuarios.map(u => <div className="users-row" key={u.usuario}>
          <span><strong>{u.usuario}</strong><small>{u.rol}</small></span>
          <button className="danger ghost" disabled={session.busy || u.usuario === session.auth.usuario} onClick={() => eliminar(u.usuario)}>
            <Icon name="trash" size={13} /> Eliminar
          </button>
        </div>)}
      </div>
      <div className="rules-form">
        <label>Usuario nuevo<input value={usuario} onChange={e => setUsuario(e.target.value)} placeholder="nombre" /></label>
        <label>Contraseña<input type="password" value={clave} onChange={e => setClave(e.target.value)} placeholder="mínimo 6 caracteres" /></label>
        <label>Rol<select value={rol} onChange={e => setRol(e.target.value)}><option value="administrador">Administrador</option><option value="operador">Operador</option></select></label>
        <button className="primary" disabled={session.busy || !usuario.trim() || clave.length < 6} onClick={crear}>Crear usuario</button>
      </div>
    </div>}
  </section>;
}

export default function ProjectHome({ session, onNewProject, onAddCamera }: { session: Session; onNewProject: () => void; onAddCamera: () => void }) {
  const { projects } = session;
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [renaming, setRenaming] = useState('');
  const busy = session.busy || isActive(session.state.status);
  const active = projects.projects.find(p => p.id === projects.active);

  function create() {
    if (!name.trim()) return;
    void session.action(async () => {
      await session.projectAction('create', { name: name.trim() });
      setCreating(false); setName('');
      session.setNotice('Proyecto creado. Sigue los pasos para configurarlo.');
      onNewProject();
    });
  }
  function open(id: string) {
    if (id === projects.active) return;
    void session.action(async () => { await session.projectAction('open', { id }); session.setNotice('Proyecto abierto.'); });
  }
  function rename(id: string, value: string) {
    void session.action(async () => { await session.projectAction('rename', { id, name: value }); setRenaming(''); });
  }
  function remove(id: string, label: string) {
    if (!confirm(`Se eliminará "${label}" con su plano, cámaras y calibración. Esta acción no se puede deshacer.`)) return;
    void session.action(async () => { await session.projectAction('delete', { id }); session.setNotice('Proyecto eliminado.'); });
  }

  return <section className="project-home">
    <div className="page-heading">
      <div>
        <h1>¿Qué quieres hacer?</h1>
        <p>Cada proyecto guarda su propio plano, sus cámaras y su calibración. Puedes tener varios y cambiar entre ellos cuando quieras.</p>
      </div>
    </div>

    <div className="project-actions">
      <button className="project-action" disabled={busy} onClick={() => setCreating(true)}>
        <Icon name="plus" size={26} />
        <strong>Crear un proyecto nuevo</strong>
        <span>Te guío paso a paso: datos, plano, cámara y calibración.</span>
      </button>
      <button className="project-action" disabled={busy || !active} onClick={onAddCamera}>
        <Icon name="camera" size={26} />
        <strong>Añadir una cámara</strong>
        <span>{active ? `Se agrega a "${active.name}", el proyecto abierto.` : 'Abre un proyecto primero.'}</span>
      </button>
    </div>

    {creating && <div className="project-create">
      <label>Nombre del proyecto
        <input autoFocus value={name} placeholder="Terminal A · Nivel 1" onChange={e => setName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') create(); if (e.key === 'Escape') setCreating(false); }} />
      </label>
      <button className="primary" disabled={!name.trim() || session.busy} onClick={create}>Crear y configurar</button>
      <button onClick={() => { setCreating(false); setName(''); }}>Cancelar</button>
    </div>}

    {session.auth.rol === 'operador' && <UsersPanel session={session} />}

    <div className="section-label"><h3>Proyectos guardados</h3><span>{projects.projects.length}</span></div>

    {isActive(session.state.status) && <div className="notice warning"><Icon name="alert" /> Hay una sesión en curso. Finalízala para cambiar de proyecto o editar su configuración.</div>}

    <div className="project-list">
      {projects.projects.map(p => <article key={p.id} className={p.id === projects.active ? 'project-card current' : 'project-card'}>
        <div className="project-card-main">
          {renaming === p.id
            ? <input autoFocus defaultValue={p.name} onBlur={e => rename(p.id, e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') rename(p.id, (e.target as HTMLInputElement).value); if (e.key === 'Escape') setRenaming(''); }} />
            : <strong>{p.name}</strong>}
          <small>{p.airport || 'Sin aeropuerto'}{p.floor ? ` · ${p.floor}` : ''}</small>
          <div className="project-card-meta">
            <span>{p.cameras} {p.cameras === 1 ? 'cámara' : 'cámaras'}</span>
            <span>{p.plans} {p.plans === 1 ? 'plano' : 'planos'}</span>
            <span>Editado {since(p.updated)}</span>
          </div>
        </div>
        <div className="project-card-side">
          <span className={`pill ${p.setupComplete ? 'good' : 'warn'}`}>{p.setupComplete ? 'Configurado' : 'Incompleto'}</span>
          {p.id === projects.active
            ? <button className="primary" disabled={busy} onClick={onNewProject}>Continuar configuración</button>
            : <button disabled={busy} onClick={() => open(p.id)}>Abrir</button>}
          <div className="project-card-tools">
            <button disabled={busy} onClick={() => setRenaming(p.id)}>Renombrar</button>
            <button className="danger ghost" disabled={busy || projects.projects.length < 2} onClick={() => remove(p.id, p.name)}><Icon name="trash" size={14} /> Eliminar</button>
          </div>
        </div>
      </article>)}
      {!projects.projects.length && <p className="empty-text">Todavía no hay proyectos guardados. Crea el primero para empezar.</p>}
    </div>
  </section>;
}
