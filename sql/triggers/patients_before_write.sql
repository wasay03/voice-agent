-- Stamps updated_at and rejects a future date_of_birth (CURRENT_DATE is not allowed in CHECK).
-- The session time zone is UTC, so this is at most a day more lenient than the app's
-- clinic-time-zone check, never stricter.
CREATE OR REPLACE FUNCTION trg_patients_before_write() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.date_of_birth > CURRENT_DATE THEN
    RAISE EXCEPTION 'date_of_birth cannot be in the future'
      USING ERRCODE = 'check_violation',
            CONSTRAINT = 'patients_date_of_birth_not_future',
            COLUMN = 'date_of_birth';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE OR REPLACE TRIGGER patients_before_write
  BEFORE INSERT OR UPDATE ON patients
  FOR EACH ROW EXECUTE FUNCTION trg_patients_before_write();
