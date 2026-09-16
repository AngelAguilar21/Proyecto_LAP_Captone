import { TrackingProvider } from './state/TrackingContext';
import { Dashboard } from './components/Dashboard/Dashboard';
import LiveDashboard from './LiveDashboard';
import AeroTrack from './aero/AeroTrack';

export default function App() {
  const view = new URLSearchParams(window.location.search).get('view');
  if (view === 'classic') return <LiveDashboard />;
  if (view !== 'legacy-replay') return <AeroTrack />;
  return (
    <TrackingProvider>
      <Dashboard />
    </TrackingProvider>
  );
}
