-- Move a call between "create a new patient" and "update this existing patient" (duplicate
-- detection). The draft is replaced and any readback is cleared.
CREATE OR REPLACE PROCEDURE sp_call_session_switch_mode(
  p_call_id             text,
  p_mode                registration_mode_t,
  p_target_patient_id   uuid,
  p_draft               jsonb,
  INOUT p_draft_version integer DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET mode = p_mode,
         target_patient_id = p_target_patient_id,
         draft = p_draft,
         draft_version = c.draft_version + 1,
         readback_version = NULL,
         readback_chunks = NULL
   WHERE c.call_id = p_call_id
  RETURNING c.draft_version INTO p_draft_version;
END $$;
