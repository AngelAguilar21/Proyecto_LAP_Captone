import { useTracking } from './useTracking';
import type { Camera, CameraId } from '../types/camera';

export function useCameras(): Record<CameraId, Camera> {
  return useTracking().state.cameras;
}
