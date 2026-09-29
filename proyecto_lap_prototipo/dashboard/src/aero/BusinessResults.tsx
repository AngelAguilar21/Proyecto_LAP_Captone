import { useEffect, useState } from 'react';

interface Row { id: string; nombre: string; empresa?: string; entries: number | null; exits: number | null; accesses: { cameraId: string; name: string; entries: number; exits: number }[] }

export default function BusinessResults() {
  const [rows, setRows] = useState<Row[]>([]);
  const [mode, setMode] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch('/api/businesses/metrics', { headers: { 'X-LAP-Session': localStorage.getItem('aero.session') || '' }, signal: controller.signal });
        const data = await response.json(); if (!response.ok) throw Error(data.error);
        if (alive) { setRows(data.negocios.filter((item: Row) => item.entries !== null)); setMode(data.mode || ''); setError(''); }
      } catch (cause) { if (alive) setError(cause instanceof Error ? cause.message : 'No se pudieron cargar las métricas.'); }
    };
    void load(); const timer = setInterval(() => void load(), 2000);
    return () => { alive = false; controller.abort(); clearInterval(timer); };
  }, []);
  function exportCsv() {
    const escape = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`;
    const text = '\uFEFF' + [['Empresa', 'Negocio', 'Entradas', 'Salidas', 'Origen'], ...rows.map(row => [row.empresa || 'Sin empresa', row.nombre, row.entries ?? 0, row.exits ?? 0, mode === 'demo' ? 'Simulación' : 'Monitoreo'])].map(row => row.map(escape).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'accesos-negocios.csv'; link.click(); URL.revokeObjectURL(url);
  }
  return <section className="aero-panel" style={{ padding: '24px' }}><div className="panel-heading"><div><h2>Entradas y salidas por negocio</h2><p>{mode === 'demo' ? 'Simulación de cruces · datos de prueba' : 'Resultados del monitoreo en curso o del último guardado'}</p></div><button disabled={!rows.length} onClick={exportCsv}>Exportar CSV</button></div>{error ? <p role="alert">{error}</p> : !rows.length ? <p>Vincula una línea a un negocio e inicia un monitoreo o una simulación para ver sus entradas y salidas.</p> : <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Empresa</th><th>Negocio</th><th>Accesos medidos</th><th>Entradas</th><th>Salidas</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.empresa || 'Sin empresa'}</td><td>{row.nombre}</td><td>{row.accesses.map(access => access.name).join(' · ')}</td><td>{row.entries}</td><td>{row.exits}</td></tr>)}</tbody></table><p>Se cuentan cruces de puertas. Una persona puede entrar más de una vez.</p></div>}</section>;
}
