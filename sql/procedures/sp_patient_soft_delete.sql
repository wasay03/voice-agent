-- Soft delete: stamps deleted_at. Returns the deleted row in p_record, or NULL if the patient
-- is missing or already deleted (both are a 404 to the API).
CREATE OR REPLACE PROCEDURE sp_patient_soft_delete(
  p_patient_id   uuid,
  INOUT p_record jsonb DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE patients p
     SET deleted_at = now()
   WHERE p.patient_id = p_patient_id
     AND p.deleted_at IS NULL
  RETURNING to_jsonb(p.*) INTO p_record;
END $$;
