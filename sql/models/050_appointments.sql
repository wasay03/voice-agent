-- Bonus: a patient's booking of one slot. At most one active booking per slot (see indexes.sql).
CREATE TABLE IF NOT EXISTS appointments (
  appointment_id  uuid                 PRIMARY KEY DEFAULT uuidv7(),
  patient_id      uuid                 NOT NULL REFERENCES patients (patient_id),
  slot_id         uuid                 NOT NULL REFERENCES appointment_slots (slot_id),
  call_id         text                 REFERENCES call_sessions (call_id),
  status          appointment_status_t NOT NULL DEFAULT 'booked',
  created_at      timestamptz          NOT NULL DEFAULT now(),
  updated_at      timestamptz          NOT NULL DEFAULT now()
);
