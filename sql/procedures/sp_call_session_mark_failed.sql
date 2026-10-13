-- A save attempt failed. Never downgrades a call that already produced a patient.
CREATE OR REPLACE PROCEDURE sp_call_session_mark_failed(
  p_call_id text,
  p_reason  text
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET status = 'failed', failure_reason = p_reason
   WHERE c.call_id = p_call_id
     AND c.patient_id IS NULL;
END $$;
