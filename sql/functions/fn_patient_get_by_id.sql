-- One active patient as jsonb, or NULL if missing or soft-deleted.
CREATE OR REPLACE FUNCTION fn_patient_get_by_id(p_patient_id uuid)
RETURNS jsonb
LANGUAGE sql STABLE AS $$
  SELECT to_jsonb(p.*)
    FROM patients p
   WHERE p.patient_id = p_patient_id
     AND p.deleted_at IS NULL;
$$;
