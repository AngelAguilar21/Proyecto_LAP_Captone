import type { Camera } from './types';

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); }
}

export interface CalibrationDiagnostics {
  rmse: number; warning?: string; spread: number;
  maxError: number; pointErrors: number[];
  validationError: number | null; validationPoints: number;
}
export interface CalibrationCheck {
  key: string;
  status: 'checking' | 'valid' | 'invalid' | 'unavailable';
  message?: string;
  diagnostics?: CalibrationDiagnostics;
}
export type CalibrationChecks = Record<string, CalibrationCheck>;
export type CalibrationScope = { projectId: string | null; serverInstance: string | undefined };
export type CalibrationCamera = Pick<Camera, 'id' | 'planId' | 'pairs'>;

// This is an identity for a backend result, not a second geometry validator.
export function calibrationKey(camera: CalibrationCamera, scope: CalibrationScope): string {
  return JSON.stringify([scope.projectId, scope.serverInstance, camera.id, camera.planId, camera.pairs]);
}

export function currentCalibration(camera: CalibrationCamera, scope: CalibrationScope, checks: CalibrationChecks): CalibrationCheck | undefined {
  const check = checks[camera.id];
  return check?.key === calibrationKey(camera, scope) ? check : undefined;
}

export function calibrationMessage(camera: CalibrationCamera, check?: CalibrationCheck): string {
  const placed = `${camera.pairs.length} referencias colocadas`;
  if (camera.pairs.length < 4) return `${placed} · faltan referencias`;
  if (check?.status === 'valid') return `${placed} · geometría válida según el servidor`;
  if (check?.status === 'invalid') return `${placed} · calibración inválida: ${check.message}`;
  if (check?.status === 'checking') return `${placed} · validando geometría`;
  return `${placed} · calibración sin comprobar${check?.message ? `: ${check.message}` : ''}`;
}

export function isCalibrationError(message: string): boolean {
  return ['Correspondencias inconsistentes', 'Calibración degenerada', 'La proyección se cruza',
    'referencias repetidas', 'Referencias casi alineadas', 'Referencias inválidas',
    'Puntos fuera del video o del plano', 'correspondencias de calibración'].some(text => message.includes(text));
}

/** Shares backend answers across the wizard. A newer request cancels ownership
 * of every earlier answer, including a response for the same camera after an edit. */
export class CalibrationValidator {
  private generation = 0;
  private checks: CalibrationChecks = {};

  constructor(private readonly request: (pairs: number[][]) => Promise<CalibrationDiagnostics>) {}

  cancel(): void { this.generation += 1; }

  clear(): void { this.cancel(); this.checks = {}; }

  async validate(cameras: CalibrationCamera[], scope: CalibrationScope, publish: (checks: CalibrationChecks) => void,
    forceCamera?: string): Promise<CalibrationChecks | undefined> {
    const generation = ++this.generation;
    const next: CalibrationChecks = {};
    const pending: { camera: CalibrationCamera; key: string }[] = [];
    for (const camera of cameras) {
      if (camera.pairs.length < 4) continue;
      const key = calibrationKey(camera, scope);
      const previous = this.checks[camera.id];
      if (camera.id !== forceCamera && previous?.key === key && ['valid', 'invalid'].includes(previous.status)) {
        next[camera.id] = previous;
      } else {
        next[camera.id] = { key, status: 'checking' };
        // Copy references so later caller mutations cannot change the request.
        pending.push({ camera: { ...camera, pairs: camera.pairs.map(pair => [...pair]) }, key });
      }
    }
    this.checks = next;
    publish({ ...next });
    await Promise.all(pending.map(async ({ camera, key }) => {
      let check: CalibrationCheck;
      try {
        const diagnostics = await this.request(camera.pairs);
        check = { key, status: 'valid', diagnostics };
      } catch (error) {
        check = { key, status: error instanceof ApiError && error.status === 400 ? 'invalid' : 'unavailable',
          message: error instanceof Error ? error.message : String(error) };
      }
      if (generation !== this.generation) return;
      this.checks = { ...this.checks, [camera.id]: check };
      publish({ ...this.checks });
    }));
    return generation === this.generation ? { ...this.checks } : undefined;
  }
}
