-- Whether a call is creating a new patient or updating an existing one (duplicate detection).
DO $$ BEGIN
  CREATE TYPE registration_mode_t AS ENUM ('create', 'update');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
