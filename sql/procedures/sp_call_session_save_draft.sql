-- Replace the draft and bump draft_version. Any earlier readback is now stale because its
-- readback_version no longer equals draft_version. Returns the new version (NULL: no session).
CREATE OR REPLACE PROCEDURE sp_call_session_save_draft(
  p_call_id             text,
  p_draft               jsonb,
  INOUT p_draft_version integer DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET draft = p_draft, draft_version = c.draft_version + 1
   WHERE c.call_id = p_call_id
  RETURNING c.draft_version INTO p_draft_version;
END $$;
