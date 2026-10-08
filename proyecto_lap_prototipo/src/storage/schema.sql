CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS aero_sessions (
  project_id text NOT NULL,
  session_id text NOT NULL,
  created_at timestamptz NOT NULL,
  status text NOT NULL,
  metadata jsonb NOT NULL,
  insights jsonb,
  imported_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, session_id)
);
CREATE TABLE IF NOT EXISTS aero_observations (
  project_id text NOT NULL,
  session_id text NOT NULL,
  sample_index bigint NOT NULL,
  observation_index integer NOT NULL,
  camera_id text NOT NULL,
  floor_id text NOT NULL,
  person_id text NOT NULL,
  content_seconds double precision NOT NULL CHECK (content_seconds >= 0),
  confirmed boolean NOT NULL,
  duplicate boolean NOT NULL,
  predicted boolean NOT NULL,
  -- SRID 0: coordenadas del plano local, NO latitud/longitud inventadas.
  position geometry(Point, 0),
  PRIMARY KEY (project_id, session_id, sample_index, observation_index),
  FOREIGN KEY (project_id, session_id) REFERENCES aero_sessions ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS aero_observations_spatial ON aero_observations USING gist(position);
CREATE INDEX IF NOT EXISTS aero_observations_time ON aero_observations(project_id, session_id, content_seconds);
CREATE INDEX IF NOT EXISTS aero_observations_person ON aero_observations(project_id, session_id, person_id, content_seconds);
CREATE TABLE IF NOT EXISTS aero_session_routes (
  project_id text NOT NULL,
  session_id text NOT NULL,
  source_camera text NOT NULL,
  target_camera text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('overlap', 'transition')),
  min_seconds double precision NOT NULL CHECK (min_seconds >= 0),
  max_seconds double precision NOT NULL CHECK (max_seconds >= min_seconds),
  PRIMARY KEY(project_id, session_id, source_camera, target_camera),
  FOREIGN KEY(project_id, session_id) REFERENCES aero_sessions ON DELETE CASCADE
);
