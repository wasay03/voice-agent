-- Create the session for a call if it does not exist (idempotent; either the status-update
-- webhook or the first tool call may arrive first). Fills in caller_number if it was unknown.
-- Returns the session row in p_record.
CREATE OR REPLACE PROCEDURE sp_call_session_start(
  p_call_id       text,
  p_caller_number text,
  INOUT p_record  jsonb DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO call_sessions (call_id, caller_number)
  VALUES (p_call_id, p_caller_number)
  ON CONFLICT (call_id) DO UPDATE
     SET caller_number = EXCLUDED.caller_number
   WHERE call_sessions.caller_number IS NULL AND EXCLUDED.caller_number IS NOT NULL;

  SELECT to_jsonb(c.*) INTO p_record FROM call_sessions c WHERE c.call_id = p_call_id;
END $$;
