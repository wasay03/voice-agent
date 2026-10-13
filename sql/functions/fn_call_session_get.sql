-- One call session as jsonb, or NULL if the call has no session yet.
CREATE OR REPLACE FUNCTION fn_call_session_get(p_call_id text)
RETURNS jsonb
LANGUAGE sql STABLE AS $$
  SELECT to_jsonb(c.*) FROM call_sessions c WHERE c.call_id = p_call_id;
$$;
