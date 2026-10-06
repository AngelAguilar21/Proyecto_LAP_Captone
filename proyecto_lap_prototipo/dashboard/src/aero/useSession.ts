import { useCallback, useEffect, useRef, useState } from 'react';
import { EMPTY_STATE, isActive } from './types';
import type { Config, ProjectListing, SessionState } from './types';

type AuthState = { configurado: boolean; usuario: string | null; rol: string | null; usuarios: { usuario: string; rol: string }[]; cargado: boolean };

export function useSession() {
  const [config, setConfig] = useState<Config | null>(null);
  const [state, setState] = useState<SessionState>(EMPTY_STATE);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [projects, setProjects] = useState<ProjectListing>({ active: null, projects: [] });
  const [auth, setAuth] = useState<AuthState>({ configurado: true, usuario: null, rol: null, usuarios: [], cargado: false });
  const sessionToken = useRef<string>(localStorage.getItem('aero.session') || '');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const token = useRef('');
  const saved = useRef('');
  const rejected = useRef('');
  const projectId = useRef<string | null>(null);
  const switching = useRef(false);
  const revision = useRef(-1);
  const instance = useRef<string>();
  const current = useRef(config);
  current.current = config;
  const dirty = config !== null && JSON.stringify(config) !== saved.current;

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const response = await fetch('/api/state', { signal: AbortSignal.timeout(6000) });
        if (!response.ok) throw new Error('Backend no disponible');
        const next: SessionState = await response.json();
        if (!alive) return;
        if (!token.current || revision.current !== next.configRevision || instance.current !== next.serverInstance) {
          const configResponse = await fetch('/api/config', { signal: AbortSignal.timeout(6000) });
          if (!configResponse.ok) throw new Error('No se pudo sincronizar la configuración');
          const data = await configResponse.json();
          if (!alive) return;
          token.current = data.token;
          instance.current = next.serverInstance;
          revision.current = data.revision;
          // Un borrador solo se conserva dentro de su propio proyecto: si el
          // servidor abrió otro, ese borrador pertenece al anterior y mezclarlo
          // sobrescribiría su plano.
          const switched = projectId.current !== data.projectId;
          projectId.current = data.projectId ?? null;
          if (switched || !current.current || isActive(next.status) || JSON.stringify(current.current) === saved.current) setConfig(data.config);
          else setNotice('Otra ventana actualizó la configuración. Tu borrador se conserva; guárdalo o recarga para usar los cambios del servidor.');
          saved.current = JSON.stringify(data.config);
          rejected.current = '';
          const listing = await fetch('/api/projects', { signal: AbortSignal.timeout(6000) });
          if (listing.ok && alive) setProjects(await listing.json());
        }
        setState(next); setConnected(true);
      } catch { if (alive) setConnected(false); }
      if (alive) timer = setTimeout(load, 450);
    };
    void load();
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[dirty]);

  const post = useCallback(async (path: string, body: unknown, binary = false) => {
    const response = await fetch(`/api/${path}`, { method: 'POST', headers: { 'Content-Type': binary ? 'application/octet-stream' : 'application/json', 'X-LAP-Token': token.current, 'X-LAP-Session': sessionToken.current }, body: binary ? body as Blob : JSON.stringify(body), signal: AbortSignal.timeout(binary ? 6 * 3600 * 1000 : 15000) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo completar la operación');
    return data;
  }, []);
  const action = useCallback(async (operation: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }, []);
  const save = useCallback(async (draft?: Config) => {
    const before = current.current;
    const value = draft || current.current;
    if (!value) throw new Error('Todavía no hay configuración');
    await post(projectId.current ? `config?project=${encodeURIComponent(projectId.current)}` : 'config', value);
    saved.current = JSON.stringify(value);
    rejected.current = '';
    setSaveError('');
    setConfig(latest => latest === before ? value : latest);
  }, [post]);

  // Autoguardado: cada cambio llega al proyecto activo sin pedir confirmación.
  // Un borrador que el servidor rechaza no se reintenta hasta que cambie.
  useEffect(() => {
    if (!config || !dirty || busy || saving || switching.current || isActive(state.status)) return;
    const payload = JSON.stringify(config);
    if (payload === rejected.current) return;
    const owner = projectId.current;
    const timer = setTimeout(() => {
      // Entre programar el guardado y ejecutarlo se puede haber abierto otro
      // proyecto: entonces este borrador ya no es de nadie y se descarta.
      if (switching.current || projectId.current !== owner) return;
      setSaving(true);
      post(owner ? `config?project=${encodeURIComponent(owner)}` : 'config', config)
        .then(() => { saved.current = payload; rejected.current = ''; setSaveError(''); })
        .catch(e => { rejected.current = payload; setSaveError(e instanceof Error ? e.message : String(e)); })
        .finally(() => setSaving(false));
    }, 900);
    return () => clearTimeout(timer);
  }, [config, dirty, busy, saving, state.status, post]);

  const projectAction = useCallback(async (operation: string, payload: Record<string, unknown> = {}) => {
    switching.current = true;
    try {
      const listing: ProjectListing = await post('projects', { action: operation, ...payload });
      setProjects(listing);
      if (operation !== 'rename') {
        // Adoptar de inmediato el proyecto abierto, sin esperar al sondeo y sin
        // arrastrar el borrador del anterior.
        const response = await fetch('/api/config', { signal: AbortSignal.timeout(6000) });
        if (response.ok) {
          const data = await response.json();
          token.current = data.token;
          revision.current = data.revision;
          projectId.current = data.projectId ?? null;
          saved.current = JSON.stringify(data.config);
          rejected.current = '';
          setSaveError('');
          setConfig(data.config);
        }
      }
      return listing;
    } finally {
      switching.current = false;
    }
  }, [post]);

  const refreshAuth = useCallback(async () => {
    const response = await fetch('/api/auth', { headers: { 'X-LAP-Session': sessionToken.current } });
    if (!response.ok) return;
    const data = await response.json();
    setAuth({ ...data, cargado: true });
  }, []);
  useEffect(() => { void refreshAuth(); }, [refreshAuth]);

  const login = useCallback(async (usuario: string, clave: string) => {
    const data = await post('auth', { accion: 'login', usuario, clave });
    sessionToken.current = data.sesion;
    try { localStorage.setItem('aero.session', data.sesion); } catch { /* modo privado */ }
    await refreshAuth();
  }, [post, refreshAuth]);

  const logout = useCallback(async () => {
    try { await post('auth', { accion: 'logout' }); } catch { /* la sesión ya podía estar vencida */ }
    sessionToken.current = '';
    try { localStorage.removeItem('aero.session'); } catch { /* modo privado */ }
    await refreshAuth();
  }, [post, refreshAuth]);

  const userAction = useCallback(async (accion: string, payload: Record<string, unknown> = {}) => {
    await post('auth', { accion, ...payload });
    await refreshAuth();
  }, [post, refreshAuth]);

  return { config, setConfig, state, connected, busy, error, setError, notice, setNotice, post, action, save, dirty,
    projects, projectAction, saving, saveError, auth, login, logout, userAction, refreshAuth };
}
export type Session = ReturnType<typeof useSession>;

export function downloadFile(name: string, value: string | Blob, mime = 'application/json') {
  const url = URL.createObjectURL(value instanceof Blob ? value : new Blob([value], { type: mime }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
