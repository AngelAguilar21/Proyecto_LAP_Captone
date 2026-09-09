import { Header } from '../Header/Header';
import { Sidebar } from '../Sidebar/Sidebar';
import { MapView } from '../MapView/MapView';
import { IdentityFlow } from '../IdentityFlow/IdentityFlow';

export function Dashboard() {
  return (
    <div className="flex h-screen flex-col bg-plane text-ink-secondary">
      <Header />
      <div className="flex min-h-0 flex-1">
        <Sidebar />

        <main className="flex min-h-0 flex-1 flex-col gap-3 p-3">
          <IdentityFlow />
          <div className="min-h-0 flex-1">
            <MapView />
          </div>
        </main>
      </div>
    </div>
  );
}
