import { Component, StrictMode, type ErrorInfo, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) { return { error }; }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('AeroTrack UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return <main role="alert" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24, background: '#081522', color: '#fff', fontFamily: 'Segoe UI, sans-serif' }}>
      <section style={{ maxWidth: 620, width: '100%', padding: 28, borderRadius: 16, background: '#102a40', border: '1px solid #ef6474', boxShadow: '0 20px 60px #0008' }}>
        <h1 style={{ margin: '0 0 10px', fontSize: 24 }}>No se pudo mostrar esta sección</h1>
        <p style={{ margin: '0 0 16px', color: '#d9e8f4', lineHeight: 1.6 }}>La interfaz encontró un dato incompatible o un error inesperado. El video y las sesiones guardadas no se han eliminado.</p>
        <pre style={{ margin: '0 0 20px', padding: 12, overflow: 'auto', whiteSpace: 'pre-wrap', color: '#ffd6dc', background: '#07131e', borderRadius: 8, fontSize: 12 }}>{this.state.error.message}</pre>
        <button type="button" onClick={() => location.reload()} style={{ padding: '10px 16px', borderRadius: 8, border: '1px solid #8ac7ef', background: '#1683c4', color: '#fff', fontWeight: 700, cursor: 'pointer' }}>Recargar AeroTrack</button>
      </section>
    </main>;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary><App /></AppErrorBoundary>
  </StrictMode>
);
