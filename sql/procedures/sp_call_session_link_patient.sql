-- Record the patient this call created or updated. A session that had been marked failed by a
-- first attempt goes back to in_progress; the final status is set when the call ends.
CREATE OR REPLACE PROCEDURE sp_call_session_link_patient(
  p_call_id    text,
  p_patient_id uuid
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET patient_id = p_patient_id,
         failure_reason = NULL,
         status = CASE WHEN c.status = 'failed' THEN 'in_progress'::call_status_t ELSE c.status END
   WHERE c.call_id = p_call_id;
END $$;
