-- One row per phone call: the in-progress registration draft while the call is live,
-- then the transcript and outcome. call_id is Vapi's call id and the submit idempotency key.
CREATE TABLE IF NOT EXISTS call_sessions (
  call_id            text                PRIMARY KEY,
  caller_number      varchar(20),                                   -- caller ID as delivered (E.164); may be absent
  status             call_status_t       NOT NULL DEFAULT 'in_progress',
  mode               registration_mode_t NOT NULL DEFAULT 'create',
  target_patient_id  uuid                REFERENCES patients (patient_id),  -- set in update mode
  draft              jsonb               NOT NULL DEFAULT '{}'::jsonb
    CONSTRAINT call_sessions_draft_is_object CHECK (jsonb_typeof(draft) = 'object'),
  draft_version      integer             NOT NULL DEFAULT 0
    CONSTRAINT call_sessions_draft_version_nonnegative CHECK (draft_version >= 0),
  readback_version   integer,                                       -- draft_version at the last readback
  readback_chunks    jsonb,                                         -- spoken chunks of the last readback
  patient_id         uuid                REFERENCES patients (patient_id),  -- record created/updated by this call
  failure_reason     text,
  ended_reason       text,
  transcript         text,
  summary            text,
  recording_url      text,
  started_at         timestamptz         NOT NULL DEFAULT now(),
  updated_at         timestamptz         NOT NULL DEFAULT now(),
  ended_at           timestamptz,
  CONSTRAINT call_sessions_update_has_target CHECK (mode = 'create' OR target_patient_id IS NOT NULL)
);
