CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS schema_version (version integer PRIMARY KEY);
INSERT INTO schema_version VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS documents (
 tenant text NOT NULL, id uuid NOT NULL, owner_id text NOT NULL,
 readers text[] NOT NULL DEFAULT '{}', source text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}',
 version integer NOT NULL, content_hash text NOT NULL, embedding_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant,id)
);
CREATE INDEX IF NOT EXISTS document_hash ON documents(tenant,content_hash);
CREATE TABLE IF NOT EXISTS versions (
 tenant text NOT NULL, document_id uuid NOT NULL, version integer NOT NULL,
 text text NOT NULL, content_hash text NOT NULL, source text NOT NULL, metadata jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(tenant,document_id,version),
 FOREIGN KEY(tenant,document_id) REFERENCES documents(tenant,id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS chunks (
 tenant text NOT NULL, document_id uuid NOT NULL, version integer NOT NULL, ordinal integer NOT NULL,
 text text NOT NULL, start_char integer NOT NULL, end_char integer NOT NULL,
 embedding vector(__DIMENSIONS__) NOT NULL,
 lexical tsvector GENERATED ALWAYS AS (to_tsvector('english',text)) STORED,
 PRIMARY KEY(tenant,document_id,ordinal),
 FOREIGN KEY(tenant,document_id) REFERENCES documents(tenant,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS chunks_lexical ON chunks USING gin(lexical);
CREATE TABLE IF NOT EXISTS jobs (
 id uuid PRIMARY KEY, tenant text NOT NULL, document_id uuid NOT NULL, version integer NOT NULL,
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','complete','failed','superseded')),
 attempts integer NOT NULL DEFAULT 0, lease_until timestamptz, lease_token uuid, error_code text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(tenant,document_id) REFERENCES documents(tenant,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS pending_jobs ON jobs(status,lease_until,created_at);
