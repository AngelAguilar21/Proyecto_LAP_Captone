import type { PersonStatus } from '../types/person';
import type { CameraStatus } from '../types/camera';

export const PERSON_STATUS_COLOR: Record<PersonStatus, string> = {
  active: '#0ca30c',
  transitioning: '#fab219',
};

const CAMERA_STATUS_COLOR: Record<CameraStatus, string> = {
  online: '#0ca30c',
  offline: '#d03b3b',
};

export function PersonStatusDot({ status }: { status: PersonStatus }) {
  return (
    <span
      className="inline-block h-2 w-2 rounded-full shrink-0"
      style={{ background: PERSON_STATUS_COLOR[status] }}
      aria-hidden
    />
  );
}

export function CameraStatusDot({ status }: { status: CameraStatus }) {
  return (
    <span
      className="inline-block h-2 w-2 rounded-full shrink-0"
      style={{ background: CAMERA_STATUS_COLOR[status] }}
      aria-hidden
    />
  );
}

export const PERSON_STATUS_LABEL: Record<PersonStatus, string> = {
  active: 'Activo',
  transitioning: 'Transicionando',
};
