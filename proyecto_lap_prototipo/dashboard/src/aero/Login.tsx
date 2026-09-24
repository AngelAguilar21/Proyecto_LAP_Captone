import { useState } from 'react';
import type { Session } from './useSession';
import Icon from './Icon';

/** Entrada al sistema. Si todavía no hay ningún usuario creado, el primero que
 * se registra queda como operador: es quien después da de alta a los demás. */
export default function Login({ session }: { session: Session }) {
  const primeraVez = !session.auth.configurado;
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [repetir, setRepetir] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (primeraVez && clave !== repetir) return setError('Las dos contraseñas no coinciden.');
    setEnviando(true);
    try {
      if (primeraVez) {
        await session.userAction('crear', { usuario, clave, rol: 'operador' });
        await session.login(usuario, clave);
      } else {
        await session.login(usuario, clave);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  return <div className="aero connection-screen">
    <div className="aero-logo"><Icon name="plane" size={38} /><strong>AeroTrack</strong></div>
    <form className="login-card" onSubmit={enviar}>
      <h1>{primeraVez ? 'Crea el primer usuario' : 'Entrar al sistema'}</h1>
      <p>{primeraVez
        ? 'Este primer usuario queda como operador y podrá dar de alta a los demás.'
        : 'Usa el usuario que te entregó el operador del sistema.'}</p>

      <label>Usuario
        <input autoFocus autoComplete="username" value={usuario} onChange={e => setUsuario(e.target.value)} />
      </label>
      <label>Contraseña
        <input type="password" autoComplete={primeraVez ? 'new-password' : 'current-password'}
          value={clave} onChange={e => setClave(e.target.value)} />
      </label>
      {primeraVez && <label>Repite la contraseña
        <input type="password" autoComplete="new-password" value={repetir} onChange={e => setRepetir(e.target.value)} />
      </label>}

      {error && <p className="notice error" role="alert">{error}</p>}
      <button className="primary" type="submit" disabled={enviando || !usuario.trim() || clave.length < 6}>
        {enviando ? 'Comprobando…' : primeraVez ? 'Crear y entrar' : 'Entrar'}
      </button>
      {primeraVez && <small>La contraseña debe tener al menos 6 caracteres. Se guarda cifrada en este equipo, nunca en texto plano.</small>}
    </form>
  </div>;
}
