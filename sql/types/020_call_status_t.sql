-- Lifecycle of one phone call: in_progress -> completed | abandoned | failed.
DO $$ BEGIN
  CREATE TYPE call_status_t AS ENUM ('in_progress', 'completed', 'abandoned', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
