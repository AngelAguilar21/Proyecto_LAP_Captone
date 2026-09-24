import { useEffect, useState } from 'react';
import type { Session } from './useSession';
import Icon from './Icon';

type MailConfig = { enabled: boolean; host: string; port: number; user: string; recipients: string[]; configured: boolean; lastError?: string | null; sent?: number };

export default function MailSettings({ session }: { session: Session }) {
  const [mail, setMail] = useState<MailConfig | null>(null);
  const [password, setPassword] = useState('');
  const [people, setPeople] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => { void fetch('/api/mail').then(r => r.json()).then((data: MailConfig) => { setMail(data); setPeople(data.recipients.join(', ')); }).catch(() => {}); }, []);
  if (!mail) return null;

  const patch = (changes: Record<string, unknown>) => void session.action(async () => {
    const saved = await session.post('mail', changes);
    setMail(current => ({ ...current!, ...saved }));
    setPassword('');
    session.setNotice('Avisos por correo actualizados.');
  });

  return <section className="aero-panel mail-settings">
    <div className="panel-heading">
      <div><h2>Avisar por correo</h2><p className="subtle">{mail.enabled ? `Activado · ${mail.recipients.length} destinatario${mail.recipients.length === 1 ? '' : 's'}` : 'Desactivado'}{mail.lastError ? ' · último envío falló' : ''}</p></div>
      <button onClick={() => setOpen(v => !v)}>{open ? 'Ocultar' : 'Configurar'}</button>
    </div>

    {open && <div className="mail-form">
      <label className="check"><input type="checkbox" checked={mail.enabled} onChange={e => patch({ enabled: e.target.checked })} /> Enviar un correo cuando salte una alerta</label>

      <div className="form-grid">
        <label>Cuenta que envía<input value={mail.user} placeholder="tucuenta@gmail.com" onChange={e => setMail({ ...mail, user: e.target.value })} onBlur={e => patch({ user: e.target.value })} /></label>
        <label>Contraseña de aplicación<input type="password" value={password} placeholder={mail.configured ? 'Guardada · escribe para cambiarla' : 'Pégala aquí'} onChange={e => setPassword(e.target.value)} onBlur={() => password && patch({ password })} /></label>
      </div>

      <label>Correos que reciben el aviso (separados por coma)
        <input value={people} placeholder="seguridad@ejemplo.com, jefatura@ejemplo.com" onChange={e => setPeople(e.target.value)}
          onBlur={() => patch({ recipients: people.split(',').map(v => v.trim()).filter(Boolean) })} />
      </label>

      <div className="inline">
        <button disabled={session.busy || !mail.configured} onClick={() => patch({ action: 'test' })}><Icon name="upload" size={14} /> Enviar correo de prueba</button>
        {mail.lastError && <span className="preview-error">{mail.lastError}</span>}
      </div>

      <p className="subtle">Gmail no acepta la contraseña normal de la cuenta. Entra a tu cuenta de Google, activa la verificación en dos pasos y genera una <b>contraseña de aplicación</b>: esa es la que va aquí. Se guarda solo en este equipo, fuera de la carpeta del proyecto, y nunca se muestra de vuelta ni se copia al duplicar un proyecto.</p>
    </div>}
  </section>;
}
