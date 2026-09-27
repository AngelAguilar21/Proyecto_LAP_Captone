import AeroTrack from './aero/AeroTrack';
import Icon from './aero/Icon';
import { useEffect, useState } from 'react';

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try {
      const saved = localStorage.getItem('aero.theme.v2');
      return saved === 'dark' ? 'dark' : 'light';
    } catch {
      return 'light';
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try { localStorage.setItem('aero.theme.v2', theme); } catch { /* modo privado */ }
  }, [theme]);
  return <>
    <button
      className="global-theme-toggle"
      type="button"
      aria-label={theme === 'dark' ? 'Cambiar a fondo claro' : 'Cambiar a fondo oscuro'}
      title={theme === 'dark' ? 'Fondo claro' : 'Fondo oscuro'}
      onClick={() => setTheme(value => value === 'dark' ? 'light' : 'dark')}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={17} />
      <span>{theme === 'dark' ? 'Claro' : 'Oscuro'}</span>
    </button>
    <AeroTrack />
  </>;
}
