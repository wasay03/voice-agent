-- Administrative sex as the brief defines it.
DO $$ BEGIN
  CREATE TYPE sex_t AS ENUM ('Male', 'Female', 'Other', 'Decline to Answer');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
