import { useCallback, useEffect, useRef, useState } from 'react';
import { EMPTY_STATE, isActive } from './types';
import type { Config, SessionState } from './types';

export function useSession() {
  const [config, setConfig] = useState<Config | null>(null);
  const [state, setState] = useState<SessionState>(EMPTY_STATE);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const token = useRef('');
  const saved = useRef('');
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
          if (!current.current || isActive(next.status) || JSON.stringify(current.current) === saved.current) setConfig(data.config);
          else setNotice('Otra ventana actualizó la configuración. Tu borrador se conserva; guárdalo o recarga para usar los cambios del servidor.');
          saved.current = JSON.stringify(data.config);
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
    const response = await fetch(`/api/${path}`, { method: 'POST', headers: { 'Content-Type': binary ? 'application/octet-stream' : 'application/json', 'X-LAP-Token': token.current }, body: binary ? body as Blob : JSON.stringify(body), signal: AbortSignal.timeout(binary ? 180000 : 15000) });
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
    await post('config', value);
    saved.current = JSON.stringify(value);
    setConfig(latest => latest === before ? value : latest);
  }, [post]);
  return { config, setConfig, state, connected, busy, error, setError, notice, setNotice, post, action, save, dirty };
}
export type Session = ReturnType<typeof useSession>;

export function downloadFile(name: string, value: string | Blob, mime = 'application/json') {
  const url = URL.createObjectURL(value instanceof Blob ? value : new Blob([value], { type: mime }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
