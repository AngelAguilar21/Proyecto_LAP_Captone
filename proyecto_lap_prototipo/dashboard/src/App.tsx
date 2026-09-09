import { TrackingProvider } from './state/TrackingContext';
import { Dashboard } from './components/Dashboard/Dashboard';

export default function App() {
  return (
    <TrackingProvider>
      <Dashboard />
    </TrackingProvider>
  );
}
