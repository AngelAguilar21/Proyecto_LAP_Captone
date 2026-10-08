import type { Config, SessionState } from './types';

// New snapshots preserve the name in `zone` and carry identity separately.
// The fallback is only for archived results that predate stable episodes.
export function planAlerts(config: Config, state: SessionState) {
  if (state.analytics.zoneEpisodes) {
    return state.analytics.zoneEpisodes.filter(e => e.alert).map(e => ({
      id: `plan:${e.scope}:${e.id}`, at: e.start, zone: e.zone,
      camera: 'Plano (varias cámaras)', people: e.peak, duration: e.duration,
      threshold: e.threshold, dwell: e.dwell, open: e.end == null, origin: 'plan' as const,
    }));
  }
  return state.analytics.zones.filter(z => z.alert).map(zone => {
    const start = state.t - (zone.duration || 0);
    const rule = config.zones.find(z => z.name === zone.name)?.rule;
    return {
      id: `plan:${zone.name}:${Math.round(start)}`, at: start, zone: zone.name,
      camera: 'Plano (varias cámaras)', people: zone.peak ?? zone.count ?? 0,
      duration: zone.duration || 0, threshold: rule?.minPeople ?? config.minPeople,
      dwell: rule?.dwell ?? config.dwell, open: true, origin: 'plan' as const,
    };
  });
}
