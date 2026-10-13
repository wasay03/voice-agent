-- Duplicate detection: active patients sharing a phone number. Returns names only, never the
-- full record, because the caller has not proven who they are.
CREATE OR REPLACE FUNCTION fn_patient_find_by_phone(p_phone_number text)
RETURNS TABLE (patient_id uuid, first_name text, last_name text)
LANGUAGE sql STABLE AS $$
  SELECT p.patient_id, p.first_name::text, p.last_name::text
    FROM patients p
   WHERE p.phone_number = p_phone_number
     AND p.deleted_at IS NULL
   ORDER BY p.created_at, p.patient_id
   LIMIT 5;
$$;
