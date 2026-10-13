-- The brief's patient demographic data model. Constraint names follow patients_<field>_<rule>
-- so a violation can be reported against the right field. The app validates the same rules
-- first with friendlier messages; these are the backstop for any path that skips the app.
-- "date_of_birth not in the future" lives in triggers/patients_before_write.sql because
-- CURRENT_DATE is not immutable and cannot appear in a CHECK.
CREATE TABLE IF NOT EXISTS patients (
  patient_id               uuid         PRIMARY KEY DEFAULT uuidv7(),
  first_name               varchar(50)  NOT NULL
    CONSTRAINT patients_first_name_format CHECK (first_name ~ '^[[:alpha:]]+([ ''-][[:alpha:]]+)*$'),
  last_name                varchar(50)  NOT NULL
    CONSTRAINT patients_last_name_format  CHECK (last_name  ~ '^[[:alpha:]]+([ ''-][[:alpha:]]+)*$'),
  date_of_birth            date         NOT NULL
    CONSTRAINT patients_date_of_birth_range CHECK (date_of_birth >= DATE '1900-01-01'),
  sex                      sex_t        NOT NULL,
  phone_number             char(10)     NOT NULL
    CONSTRAINT patients_phone_number_format CHECK (phone_number ~ '^[2-9][0-9]{2}[2-9][0-9]{6}$'),
  email                    varchar(254)
    CONSTRAINT patients_email_format CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  address_line_1           varchar(100) NOT NULL
    CONSTRAINT patients_address_line_1_present CHECK (length(btrim(address_line_1)) > 0),
  address_line_2           varchar(100),
  city                     varchar(100) NOT NULL
    CONSTRAINT patients_city_present CHECK (length(btrim(city)) > 0),
  state                    char(2)      NOT NULL
    CONSTRAINT patients_state_fkey REFERENCES us_states (code),
  zip_code                 varchar(10)  NOT NULL
    CONSTRAINT patients_zip_code_format CHECK (zip_code ~ '^[0-9]{5}(-[0-9]{4})?$'),
  insurance_provider       varchar(100),
  insurance_member_id      varchar(30)
    CONSTRAINT patients_insurance_member_id_format CHECK (insurance_member_id ~ '^[A-Za-z0-9]+$'),
  preferred_language       varchar(40)  NOT NULL DEFAULT 'English'
    CONSTRAINT patients_preferred_language_present CHECK (length(btrim(preferred_language)) > 0),
  emergency_contact_name   varchar(100),
  emergency_contact_phone  char(10)
    CONSTRAINT patients_emergency_contact_phone_format
    CHECK (emergency_contact_phone ~ '^[2-9][0-9]{2}[2-9][0-9]{6}$'),
  created_at               timestamptz  NOT NULL DEFAULT now(),
  updated_at               timestamptz  NOT NULL DEFAULT now(),
  deleted_at               timestamptz                          -- soft delete
);
