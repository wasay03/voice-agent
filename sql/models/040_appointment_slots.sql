-- Bonus: bookable appointment slots (mock schedule).
CREATE TABLE IF NOT EXISTS appointment_slots (
  slot_id           uuid        PRIMARY KEY DEFAULT uuidv7(),
  starts_at         timestamptz NOT NULL,
  duration_minutes  integer     NOT NULL DEFAULT 30
    CONSTRAINT appointment_slots_duration_positive CHECK (duration_minutes > 0),
  provider_name     varchar(100) NOT NULL,
  is_open           boolean     NOT NULL DEFAULT true,
  CONSTRAINT appointment_slots_provider_time_uq UNIQUE (provider_name, starts_at)
);
