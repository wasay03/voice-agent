-- Remember what was read back and at which draft version; submit is refused unless the draft
-- is still at that version.
CREATE OR REPLACE PROCEDURE sp_call_session_save_readback(
  p_call_id text,
  p_version integer,
  p_chunks  jsonb
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE call_sessions c
     SET readback_version = p_version, readback_chunks = p_chunks
   WHERE c.call_id = p_call_id;
END $$;
