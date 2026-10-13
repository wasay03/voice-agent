-- Partial update: only keys present in p_changes are written (a key with JSON null clears an
-- optional field; NOT NULL constraints stop required fields being cleared). Returns the updated
-- row in p_record, or NULL if the patient is missing or soft-deleted.
CREATE OR REPLACE PROCEDURE sp_patient_update(
  p_patient_id   uuid,
  p_changes      jsonb,
  INOUT p_record jsonb DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
  v_unknown text;
BEGIN
  SELECT string_agg(k, ', ') INTO v_unknown
    FROM jsonb_object_keys(p_changes) AS k
   WHERE k NOT IN (
     'first_name', 'last_name', 'date_of_birth', 'sex', 'phone_number', 'email',
     'address_line_1', 'address_line_2', 'city', 'state', 'zip_code',
     'insurance_provider', 'insurance_member_id', 'preferred_language',
     'emergency_contact_name', 'emergency_contact_phone'
   );
  IF v_unknown IS NOT NULL THEN
    RAISE EXCEPTION 'unknown or read-only patient fields: %', v_unknown
      USING ERRCODE = 'invalid_parameter_value';
  END IF;

  UPDATE patients p SET
    first_name              = CASE WHEN p_changes ? 'first_name'              THEN p_changes->>'first_name'              ELSE p.first_name END,
    last_name               = CASE WHEN p_changes ? 'last_name'               THEN p_changes->>'last_name'               ELSE p.last_name END,
    date_of_birth           = CASE WHEN p_changes ? 'date_of_birth'           THEN (p_changes->>'date_of_birth')::date   ELSE p.date_of_birth END,
    sex                     = CASE WHEN p_changes ? 'sex'                     THEN (p_changes->>'sex')::sex_t            ELSE p.sex END,
    phone_number            = CASE WHEN p_changes ? 'phone_number'            THEN p_changes->>'phone_number'            ELSE p.phone_number END,
    email                   = CASE WHEN p_changes ? 'email'                   THEN p_changes->>'email'                   ELSE p.email END,
    address_line_1          = CASE WHEN p_changes ? 'address_line_1'          THEN p_changes->>'address_line_1'          ELSE p.address_line_1 END,
    address_line_2          = CASE WHEN p_changes ? 'address_line_2'          THEN p_changes->>'address_line_2'          ELSE p.address_line_2 END,
    city                    = CASE WHEN p_changes ? 'city'                    THEN p_changes->>'city'                    ELSE p.city END,
    state                   = CASE WHEN p_changes ? 'state'                   THEN p_changes->>'state'                   ELSE p.state END,
    zip_code                = CASE WHEN p_changes ? 'zip_code'                THEN p_changes->>'zip_code'                ELSE p.zip_code END,
    insurance_provider      = CASE WHEN p_changes ? 'insurance_provider'      THEN p_changes->>'insurance_provider'      ELSE p.insurance_provider END,
    insurance_member_id     = CASE WHEN p_changes ? 'insurance_member_id'     THEN p_changes->>'insurance_member_id'     ELSE p.insurance_member_id END,
    preferred_language      = CASE WHEN p_changes ? 'preferred_language'      THEN p_changes->>'preferred_language'      ELSE p.preferred_language END,
    emergency_contact_name  = CASE WHEN p_changes ? 'emergency_contact_name'  THEN p_changes->>'emergency_contact_name'  ELSE p.emergency_contact_name END,
    emergency_contact_phone = CASE WHEN p_changes ? 'emergency_contact_phone' THEN p_changes->>'emergency_contact_phone' ELSE p.emergency_contact_phone END
  WHERE p.patient_id = p_patient_id
    AND p.deleted_at IS NULL
  RETURNING to_jsonb(p.*) INTO p_record;
END $$;
