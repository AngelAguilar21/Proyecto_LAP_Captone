import { useMemo } from 'react';
import { useTracking } from './useTracking';
import type { Person } from '../types/person';

/** Personas presentes en el frame actual del replay, filtradas por camara y
 * estado (los mismos filtros que controla la Sidebar). */
export function usePersons(): Person[] {
  const { state } = useTracking();
  const { persons, cameraFilter, statusFilter } = state;
  return useMemo(() => {
    return Object.values(persons)
      .filter((p) => cameraFilter === 'all' || p.cameras.includes(cameraFilter))
      .filter((p) => statusFilter === 'all' || p.status === statusFilter)
      .sort((a, b) => a.id.localeCompare(b.id));
  }, [persons, cameraFilter, statusFilter]);
}
