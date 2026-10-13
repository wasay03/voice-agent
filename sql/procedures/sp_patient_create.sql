-- Insert one patient; returns the stored row as jsonb in p_record.
-- Constraints and the patients_before_write trigger enforce every rule; violations surface
-- as SQLSTATE 23xxx with the constraint name, which the app maps to a 422 on that field.
CREATE OR REPLACE PROCEDURE sp_patient_create(
  p_first_name              text,
  p_last_name               text,
  p_date_of_birth           date,
  p_sex                     sex_t,
  p_phone_number            text,
  p_email                   text,
  p_address_line_1          text,
  p_address_line_2          text,
  p_city                    text,
  p_state                   text,
  p_zip_code                text,
  p_insurance_provider      text,
  p_insurance_member_id     text,
  p_preferred_language      text,
  p_emergency_contact_name  text,
  p_emergency_contact_phone text,
  INOUT p_record            jsonb DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO patients (
    first_name, last_name, date_of_birth, sex, phone_number, email,
    address_line_1, address_line_2, city, state, zip_code,
    insurance_provider, insurance_member_id, preferred_language,
    emergency_contact_name, emergency_contact_phone
  ) VALUES (
    p_first_name, p_last_name, p_date_of_birth, p_sex, p_phone_number, p_email,
    p_address_line_1, p_address_line_2, p_city, p_state, p_zip_code,
    p_insurance_provider, p_insurance_member_id, coalesce(p_preferred_language, 'English'),
    p_emergency_contact_name, p_emergency_contact_phone
  )
  RETURNING to_jsonb(patients.*) INTO p_record;
END $$;
