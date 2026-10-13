-- Every index in the schema. Idempotent; re-applied on every migrator run, so a new index
-- needs no migration file. Partial indexes keep soft-deleted patients out of lookups.

-- patients: the API's filters and duplicate detection
CREATE INDEX IF NOT EXISTS patients_phone_idx      ON patients (phone_number)     WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS patients_last_name_idx  ON patients (lower(last_name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS patients_dob_idx        ON patients (date_of_birth)    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS patients_created_at_idx ON patients (created_at DESC)  WHERE deleted_at IS NULL;

-- call_sessions: transcripts per patient, resume-after-drop by caller
CREATE INDEX IF NOT EXISTS call_sessions_patient_idx ON call_sessions (patient_id);
CREATE INDEX IF NOT EXISTS call_sessions_caller_idx  ON call_sessions (caller_number, started_at DESC);

-- appointments (bonus)
CREATE INDEX IF NOT EXISTS appointment_slots_open_idx ON appointment_slots (starts_at) WHERE is_open;
CREATE INDEX IF NOT EXISTS appointments_patient_idx   ON appointments (patient_id);
CREATE UNIQUE INDEX IF NOT EXISTS appointments_slot_booked_uq ON appointments (slot_id) WHERE status = 'booked';
