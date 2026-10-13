-- Two fictional demo patients (555-01xx numbers are reserved for fiction). Fixed ids so the
-- README's curl examples work against a fresh database.
INSERT INTO patients (
  patient_id, first_name, last_name, date_of_birth, sex, phone_number, email,
  address_line_1, address_line_2, city, state, zip_code,
  insurance_provider, insurance_member_id, preferred_language,
  emergency_contact_name, emergency_contact_phone
) VALUES
  ('01920000-0000-7000-8000-000000000001', 'Jane', 'Doe', DATE '1980-03-05', 'Female', '5125550198',
   'jane.doe@example.com', '1200 Barton Springs Rd', 'Apt 4B', 'Austin', 'TX', '78704',
   'Blue Cross Blue Shield', 'XJH123456789', 'English', 'John Doe', '5125550199'),
  ('01920000-0000-7000-8000-000000000002', 'Carlos', 'De La Cruz', DATE '1992-11-21', 'Male', '6825550142',
   NULL, '400 Main St', NULL, 'Fort Worth', 'TX', '76102-3104',
   NULL, NULL, 'Spanish', NULL, NULL)
ON CONFLICT (patient_id) DO NOTHING;
