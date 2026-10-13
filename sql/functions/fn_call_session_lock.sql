-- Same as fn_call_session_get but takes a row lock until the transaction ends, so concurrent
-- tool calls for one call (the model may emit several at once) are applied one at a time.
CREATE OR REPLACE FUNCTION fn_call_session_lock(p_call_id text)
RETURNS jsonb
LANGUAGE sql VOLATILE AS $$
  SELECT to_jsonb(c.*) FROM call_sessions c WHERE c.call_id = p_call_id FOR UPDATE;
$$;
