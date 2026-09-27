import { useState } from 'react';
import type { Session } from './useSession';
import { isActive } from './types';
import Icon from './Icon';
import ProjectsPanel from './ProjectsPanel';

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
  const busy = session.busy || isActive(session.state.status);
  const active = projects.projects.find(p => p.id === projects.active);

  return <section className="project-home">
    <div className="page-heading">
      <div>
        <h1>¿Qué quieres hacer?</h1>
        <p>Cada proyecto guarda su propio plano, sus cámaras y su calibración. Puedes tener varios y cambiar entre ellos cuando quieras.</p>
      </div>
    </div>

    <div className="project-actions">
      <button className="project-action" disabled={busy || !active} onClick={onAddCamera}>
        <Icon name="camera" size={26} />
        <strong>Añadir una cámara</strong>
        <span>{active ? `Se agrega a "${active.name}", el proyecto abierto.` : 'Abre un proyecto primero.'}</span>
      </button>
      <button className="project-action" disabled={busy || !active} onClick={onNewProject}>
        <Icon name="settings" size={26} />
        <strong>Continuar la configuración</strong>
        <span>{active ? `Datos, plano y calibración de "${active.name}".` : 'Abre un proyecto primero.'}</span>
      </button>
    </div>

    {session.auth.rol === 'operador' && <UsersPanel session={session} />}

    <ProjectsPanel session={session} onConfigure={onNewProject} onCreated={onNewProject} />
  </section>;
}
