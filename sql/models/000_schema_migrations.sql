-- Bookkeeping for app/db/migrator.py: one row per applied SQL file (or the 'baseline' marker).
CREATE TABLE IF NOT EXISTS schema_migrations (
  name        text        PRIMARY KEY,                -- path relative to sql/, e.g. 'functions/fn_x.sql'
  kind        text        NOT NULL CHECK (kind IN ('baseline', 'versioned', 'repeatable')),
  checksum    text        NOT NULL,                   -- sha256 of the file when applied
  applied_at  timestamptz NOT NULL DEFAULT now()
);
