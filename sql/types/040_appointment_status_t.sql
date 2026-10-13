-- Bonus: appointment scheduling.
DO $$ BEGIN
  CREATE TYPE appointment_status_t AS ENUM ('booked', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
