-- Generic updated_at stamp for tables without other write rules.
CREATE OR REPLACE FUNCTION trg_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

CREATE OR REPLACE TRIGGER call_sessions_touch_updated_at
  BEFORE UPDATE ON call_sessions
  FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at();

CREATE OR REPLACE TRIGGER appointments_touch_updated_at
  BEFORE UPDATE ON appointments
  FOR EACH ROW EXECUTE FUNCTION trg_touch_updated_at();
