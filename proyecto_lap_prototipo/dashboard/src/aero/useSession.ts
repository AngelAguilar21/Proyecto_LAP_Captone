import { useCallback, useEffect, useRef, useState } from 'react';
import { EMPTY_STATE, isActive } from './types';
import type { Camera, Config, ProjectListing, SessionState } from './types';
import { ApiError, CalibrationValidator, calibrationKey, currentCalibration } from './calibration';
import type { CalibrationChecks } from './calibration';
import { ConfigSaveQueue, saveWithFeedback } from './sessionSave';

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
  const [calibrationChecks, setCalibrationChecks] = useState<CalibrationChecks>({});
  const pendingSaves = useRef(0);
  const saveSequence = useRef(0);
  const saveQueue = useRef(new ConfigSaveQueue());
  const projectGeneration = useRef(0);
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
          if (switched) projectGeneration.current += 1;
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
    const response = await fetch(`/api/${path}`, { method: 'POST', headers: { 'Content-Type': binary ? 'application/octet-stream' : 'application/json', 'X-LAP-Token': token.current, 'X-LAP-Session': sessionToken.current }, body: binary ? body as Blob : JSON.stringify(body), signal: AbortSignal.timeout(binary ? 180000 : 15000) });
    const data = await response.json();
    if (!response.ok) throw new ApiError(data.error || 'No se pudo completar la operación', response.status);
    return data;
  }, []);
  const calibrationValidator = useRef<CalibrationValidator>();
  if (!calibrationValidator.current) calibrationValidator.current = new CalibrationValidator(pairs => post('calibration-check', { pairs }));
  const calibrationScope = { projectId: projectId.current, serverInstance: instance.current };
  const canValidateCalibration = connected && auth.cargado && auth.rol === 'operador';
  const calibrationInputs = JSON.stringify((config?.cameras || []).map(camera => calibrationKey(camera, calibrationScope)));
  useEffect(() => {
    const validator = calibrationValidator.current!;
    if (!canValidateCalibration) {
      validator.clear();
      setCalibrationChecks({});
      return;
    }
    void validator.validate(current.current?.cameras || [],
      { projectId: projectId.current, serverInstance: instance.current }, setCalibrationChecks);
    return () => validator.cancel();
  }, [calibrationInputs, canValidateCalibration]);

  const calibrationFor = (camera: Camera) => canValidateCalibration
    ? currentCalibration(camera, calibrationScope, calibrationChecks) : undefined;
  const validateCalibration = async (cameraId: string) => {
    if (!canValidateCalibration) throw new Error('Conecta el servidor e inicia sesión como operador para comprobar la calibración.');
    const cameras = current.current?.cameras || [];
    const camera = cameras.find(value => value.id === cameraId);
    if (!camera || camera.pairs.length < 4) throw new Error('Se necesitan al menos cuatro referencias.');
    const scope = { projectId: projectId.current, serverInstance: instance.current };
    const checks = await calibrationValidator.current!.validate(cameras, scope, setCalibrationChecks, cameraId);
    const latest = current.current?.cameras.find(value => value.id === cameraId);
    const check = latest && checks && currentCalibration(latest,
      { projectId: projectId.current, serverInstance: instance.current }, checks);
    if (!check) throw new Error('La configuración cambió durante la validación. Comprueba las referencias actuales.');
    if (check.status !== 'valid') throw new Error(check.message || 'No se pudo comprobar la calibración.');
    return check.diagnostics!;
  };
  const action = useCallback(async (operation: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }, []);
  const save = useCallback(async (draft?: Config) => {
    const before = current.current;
    const value = draft || current.current;
    if (!value) throw new Error('Todavía no hay configuración');
    const owner = projectId.current;
    const generation = projectGeneration.current;
    const sequence = ++saveSequence.current;
    const payload = JSON.stringify(value);
    const ownsProject = () => projectId.current === owner && projectGeneration.current === generation && !switching.current;
    const ownsFeedback = () => ownsProject() && saveSequence.current === sequence;
    await saveWithFeedback(() => saveQueue.current.enqueue(value, ownsProject,
      snapshot => post(owner ? `config?project=${encodeURIComponent(owner)}` : 'config', snapshot)), {
      started: () => { pendingSaves.current += 1; setSaving(true); if (ownsFeedback()) setSaveError(''); },
      saved: () => {
        if (!ownsFeedback()) return;
        saved.current = payload;
        rejected.current = '';
        setSaveError('');
        setConfig(latest => latest === before ? JSON.parse(payload) as Config : latest);
      },
      failed: message => { if (ownsFeedback()) { rejected.current = payload; setSaveError(message); } },
      finished: () => { pendingSaves.current -= 1; setSaving(pendingSaves.current > 0); },
    });
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
      void save(config).catch(() => { /* save already preserves the rejected draft and concrete cause. */ });
    }, 900);
    return () => clearTimeout(timer);
  }, [config, dirty, busy, saving, state.status, save]);

  const projectAction = useCallback(async (operation: string, payload: Record<string, unknown> = {}) => {
    switching.current = true;
    // Invalidate outstanding ownership even if the user opens the same project
    // again before an older queued request gets its turn.
    if (operation !== 'rename') projectGeneration.current += 1;
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
    projects, projectAction, saving, saveError, calibrationFor, validateCalibration, auth, login, logout, userAction, refreshAuth };
}
export type Session = ReturnType<typeof useSession>;

export function downloadFile(name: string, value: string | Blob, mime = 'application/json') {
  const url = URL.createObjectURL(value instanceof Blob ? value : new Blob([value], { type: mime }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
