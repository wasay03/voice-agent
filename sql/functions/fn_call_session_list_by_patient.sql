-- Calls that created or updated a patient, newest first (transcripts for the dashboard / API).
CREATE OR REPLACE FUNCTION fn_call_session_list_by_patient(p_patient_id uuid)
RETURNS TABLE (
  call_id       text,
  started_at    timestamptz,
  ended_at      timestamptz,
  status        call_status_t,
  ended_reason  text,
  summary       text,
  transcript    text,
  recording_url text
)
LANGUAGE sql STABLE AS $$
  SELECT c.call_id, c.started_at, c.ended_at, c.status, c.ended_reason,
         c.summary, c.transcript, c.recording_url
    FROM call_sessions c
   WHERE c.patient_id = p_patient_id
   ORDER BY c.started_at DESC, c.call_id;
$$;
