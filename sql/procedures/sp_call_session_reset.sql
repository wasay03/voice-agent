-- "Start over": empty draft, back to create mode, readback cleared. The version still goes
-- up, so an old readback can never be submitted.
CREATE OR REPLACE PROCEDURE sp_call_session_reset(
  p_call_id             text,
  INOUT p_draft_version integer DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET mode = 'create',
         target_patient_id = NULL,
         draft = '{}'::jsonb,
         draft_version = c.draft_version + 1,
         readback_version = NULL,
         readback_chunks = NULL
   WHERE c.call_id = p_call_id
  RETURNING c.draft_version INTO p_draft_version;
END $$;
