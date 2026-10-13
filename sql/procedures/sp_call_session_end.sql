-- Close the call with its final status and the end-of-call report. NULL arguments keep the
-- stored value, so a partial report cannot wipe earlier data. Returns the row in p_record.
CREATE OR REPLACE PROCEDURE sp_call_session_end(
  p_call_id       text,
  p_status        call_status_t,
  p_ended_reason  text,
  p_transcript    text,
  p_summary       text,
  p_recording_url text,
  INOUT p_record  jsonb DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET status        = p_status,
         ended_reason  = coalesce(p_ended_reason, c.ended_reason),
         transcript    = coalesce(p_transcript, c.transcript),
         summary       = coalesce(p_summary, c.summary),
         recording_url = coalesce(p_recording_url, c.recording_url),
         ended_at      = coalesce(c.ended_at, now())
   WHERE c.call_id = p_call_id
  RETURNING to_jsonb(c.*) INTO p_record;
END $$;
