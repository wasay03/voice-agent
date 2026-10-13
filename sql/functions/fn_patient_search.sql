-- Active patients matching every filter that is not NULL, newest first.
-- last_name: case-insensitive exact match; phone: 10 digits; total_count ignores limit/offset
-- (it is 0 when offset is past the last row, because no row carries it).
CREATE OR REPLACE FUNCTION fn_patient_search(
  p_last_name     text,
  p_date_of_birth date,
  p_phone_number  text,
  p_limit         integer,
  p_offset        integer
)
RETURNS TABLE (patient jsonb, total_count bigint)
LANGUAGE sql STABLE AS $$
  SELECT to_jsonb(p.*), count(*) OVER ()
    FROM patients p
   WHERE p.deleted_at IS NULL
     AND (p_last_name     IS NULL OR lower(p.last_name) = lower(p_last_name))
     AND (p_date_of_birth IS NULL OR p.date_of_birth = p_date_of_birth)
     AND (p_phone_number  IS NULL OR p.phone_number = p_phone_number)
   ORDER BY p.created_at DESC, p.patient_id DESC   -- uuidv7 breaks ties within one transaction
   LIMIT p_limit OFFSET p_offset;
$$;
