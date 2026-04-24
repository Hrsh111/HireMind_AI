CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS interview_sessions (
  id TEXT PRIMARY KEY,
  round_type TEXT NOT NULL,
  resume_text TEXT DEFAULT '',
  resume_file_name TEXT DEFAULT '',
  weak_areas JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_events (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT REFERENCES interview_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS skill_graphs (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT REFERENCES interview_sessions(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  score DOUBLE PRECISION NOT NULL DEFAULT 0,
  evidence TEXT DEFAULT '',
  embedding vector(1536),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_graphs_session_skill
ON skill_graphs(session_id, skill);
