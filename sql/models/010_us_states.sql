-- Lookup that constrains patients.state; seeded by seed/010_us_states.sql.
CREATE TABLE IF NOT EXISTS us_states (
  code  char(2) PRIMARY KEY CONSTRAINT us_states_code_format CHECK (code ~ '^[A-Z]{2}$'),
  name  text    NOT NULL UNIQUE
);
