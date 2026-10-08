export type ZoneRow = { t: number; zones: { name: string; count: number | null; observed?: boolean; peak?: number; alert?: boolean }[] };

export function zoneSeries(rows: ZoneRow[], name: string) {
  return rows.flatMap((row, index) => {
    const zone = row.zones.find(z => z.name === name);
    return zone && zone.observed !== false && zone.count != null && Number.isFinite(zone.count)
      ? [{ t: row.t, count: zone.count, index }] : [];
  });
}

export function zoneRanking(rows: ZoneRow[]) {
  const names = [...new Set(rows.flatMap(r => r.zones.map(z => z.name)))];
  return names.flatMap(name => {
    const samples = zoneSeries(rows, name);
    if (!samples.length) return [];
    let total = 0, seconds = 0;
    for (let i = 1; i < samples.length; i++) {
      // A missing sample is not zero and cannot bridge an unobserved interval.
      if (samples[i].index !== samples[i - 1].index + 1) continue;
      const dt = Math.max(0, samples[i].t - samples[i - 1].t);
      total += samples[i - 1].count * dt;
      seconds += dt;
    }
    const peak = samples.reduce((a, b) => b.count > a.count ? b : a);
    return [{ name, mean: seconds ? total / seconds : samples[0].count, peak: peak.count, t: peak.t }];
  }).sort((a, b) => b.mean - a.mean);
}
