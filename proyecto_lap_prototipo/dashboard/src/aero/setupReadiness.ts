import type { Camera, Config, SessionState } from './types';
import { isStream } from './types';
import type { CalibrationCheck } from './calibration';

export type SetupStepId = 'project' | 'plan' | 'source' | 'test' | 'calibrate' | 'zones' | 'review';

export function geometryReady(camera: Camera, check?: CalibrationCheck): boolean {
  return camera.pairs.length >= 4 && check?.status === 'valid';
}

export function projectReadiness(config: Config, state: SessionState, calibrationFor: (camera: Camera) => CalibrationCheck | undefined) {
  const cameras = config.cameras.filter(c => (c.planId || 'custom') === (config.planId || 'custom'));
  const mode = config.sourceMode || 'recordings';
  const tests = cameras.filter(c => state.sourceChecks?.[c.id]?.valid && state.sourceChecks[c.id].source === c.source);
  const placed = cameras.filter(c => c.pairs.length >= 4).length;
  const calibrated = cameras.filter(c => geometryReady(c, calibrationFor(c))).length;
  const invalid = cameras.filter(c => calibrationFor(c)?.status === 'invalid').length;
  const useful = cameras.filter(c => !!c.detectionZone).length;
  const businesses = config.zones.filter(z => z.kind === 'commercial').length;
  const commercialReady = config.commercialContext?.hasBusinesses === false || (config.commercialContext?.hasBusinesses === true && businesses > 0);
  return [
    { step:'project' as SetupStepId, title:'Proyecto', subtitle:'Espacio y modo de trabajo', done:!!config.airport?.trim() && !!config.floor?.trim(), icon:'grid' },
    { step:'source' as SetupStepId, title:'Cámaras', subtitle:`${cameras.length} cámaras · ${tests.length} probadas`, done:cameras.length > 0 && cameras.every(c => mode === 'demo' || (c.source !== '' && isStream(c.source) === (mode === 'live'))), icon:'camera' },
    { step:'calibrate' as SetupStepId, title:'Homografía y alcance',
      subtitle:!config.mapConfigured ? 'Falta el plano' : mode === 'demo' ? 'Plano preparado' : `${placed}/${cameras.length} con referencias suficientes · ${calibrated}/${cameras.length} geometrías válidas${invalid ? ` · ${invalid} inválidas` : ''} · ${useful}/${cameras.length} zonas útiles`,
      done:!!config.mapConfigured && (mode === 'demo' || (cameras.length > 0 && cameras.every(c => geometryReady(c, calibrationFor(c)) && !!c.detectionZone))), icon:'map' },
    { step:'zones' as SetupStepId, title:'Contexto comercial', subtitle:config.commercialContext?.hasBusinesses === false ? 'Piso sin negocios existentes' : businesses ? `${businesses} negocios registrados` : 'Indica si existen negocios', done:commercialReady && config.radius > 0 && config.minPeople >= 2 && config.dwell >= 0, icon:'layers' },
    { step:'review' as SetupStepId, title:'Validación', subtitle:mode === 'demo' ? 'Preparar demostración' : 'Validar antes de operar', done:mode === 'demo' || (cameras.length > 0 && tests.length === cameras.length && (cameras.length === 1 || config.clocksVerified)), icon:'check' },
  ];
}
