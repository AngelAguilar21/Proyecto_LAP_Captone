import { createContext, useContext, useEffect, useMemo, useReducer } from 'react';
import type { ReactNode } from 'react';
import type { CameraId } from '../types/camera';
import type { CameraFilter, DataSourceMode, LayerVisibility, StatusFilter, TrackingState } from '../types/tracking';
import { REAL_SESSION } from '../data/realSession';
import { camerasAtFrame, personsAtFrame } from './replay';

type Action =
  | { type: 'SET_FRAME'; index: number }
  | { type: 'TOGGLE_PLAY' }
  | { type: 'SET_SPEED'; value: number }
  | { type: 'SELECT_PERSON'; id: string | null }
  | { type: 'SET_CAMERA_FILTER'; value: CameraFilter }
  | { type: 'SET_STATUS_FILTER'; value: StatusFilter }
  | { type: 'TOGGLE_LAYER'; key: keyof LayerVisibility }
  | { type: 'SET_HIGHLIGHT_CAMERA'; id: CameraId | null }
  | { type: 'SET_MODE'; mode: DataSourceMode };

const initialPersons = personsAtFrame(0);

const initialState: TrackingState = {
  mode: 'demo',
  frameIndex: 0,
  playing: true,
  speed: 0.5,
  cameras: camerasAtFrame(initialPersons),
  persons: initialPersons,
  events: [],
  selectedPersonId: null,
  highlightedCamera: null,
  cameraFilter: 'all',
  statusFilter: 'all',
  layers: {
    persons: true,
    coverageA: true,
    coverageB: true,
    trajectories: true,
    connections: true,
    transitionZone: true,
  },
};

function reducer(state: TrackingState, action: Action): TrackingState {
  switch (action.type) {
    case 'SET_FRAME': {
      const persons = personsAtFrame(action.index);
      return { ...state, frameIndex: action.index, persons, cameras: camerasAtFrame(persons) };
    }
    case 'TOGGLE_PLAY':
      return { ...state, playing: !state.playing };
    case 'SET_SPEED':
      return { ...state, speed: action.value };
    case 'SELECT_PERSON':
      return { ...state, selectedPersonId: action.id };
    case 'SET_CAMERA_FILTER':
      return { ...state, cameraFilter: action.value };
    case 'SET_STATUS_FILTER':
      return { ...state, statusFilter: action.value };
    case 'TOGGLE_LAYER':
      return { ...state, layers: { ...state.layers, [action.key]: !state.layers[action.key] } };
    case 'SET_HIGHLIGHT_CAMERA':
      return { ...state, highlightedCamera: action.id };
    case 'SET_MODE':
      return { ...state, mode: action.mode };
    default:
      return state;
  }
}

interface TrackingContextValue {
  state: TrackingState;
  selectPerson: (id: string | null) => void;
  setCameraFilter: (value: CameraFilter) => void;
  setStatusFilter: (value: StatusFilter) => void;
  toggleLayer: (key: keyof LayerVisibility) => void;
  setHighlightedCamera: (id: CameraId | null) => void;
  setMode: (mode: DataSourceMode) => void;
  togglePlay: () => void;
  seekFrame: (index: number) => void;
  setSpeed: (value: number) => void;
}

const TrackingContext = createContext<TrackingContextValue | null>(null);

export function TrackingProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(() => {
    if (!state.playing) return undefined;
    const tickMs = Math.max(30, (REAL_SESSION.meta.paso * 1000) / state.speed);
    const id = window.setInterval(() => {
      const next = (state.frameIndex + 1) % REAL_SESSION.meta.totalBins;
      dispatch({ type: 'SET_FRAME', index: next });
    }, tickMs);
    return () => window.clearInterval(id);
  }, [state.playing, state.frameIndex, state.speed]);

  const value = useMemo<TrackingContextValue>(
    () => ({
      state,
      selectPerson: (id) => dispatch({ type: 'SELECT_PERSON', id }),
      setCameraFilter: (value) => dispatch({ type: 'SET_CAMERA_FILTER', value }),
      setStatusFilter: (value) => dispatch({ type: 'SET_STATUS_FILTER', value }),
      toggleLayer: (key) => dispatch({ type: 'TOGGLE_LAYER', key }),
      setHighlightedCamera: (id) => dispatch({ type: 'SET_HIGHLIGHT_CAMERA', id }),
      setMode: (mode) => dispatch({ type: 'SET_MODE', mode }),
      togglePlay: () => dispatch({ type: 'TOGGLE_PLAY' }),
      seekFrame: (index) => dispatch({ type: 'SET_FRAME', index }),
      setSpeed: (value) => dispatch({ type: 'SET_SPEED', value }),
    }),
    [state]
  );

  return <TrackingContext.Provider value={value}>{children}</TrackingContext.Provider>;
}

export function useTrackingContext(): TrackingContextValue {
  const ctx = useContext(TrackingContext);
  if (!ctx) throw new Error('useTrackingContext debe usarse dentro de <TrackingProvider>');
  return ctx;
}
