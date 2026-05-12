-- Fix NOT NULL timestamp columns without DEFAULT (INSERT then fails with 23502).
-- Safe if defaults already exist (replaces with same behavior).
ALTER TABLE inspectors
  ALTER COLUMN created_at SET DEFAULT now(),
  ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE facilities
  ALTER COLUMN created_at SET DEFAULT now(),
  ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE inspections
  ALTER COLUMN created_at SET DEFAULT now(),
  ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE inspection_staff
  ALTER COLUMN created_at SET DEFAULT now(),
  ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE inspection_responses
  ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE inspection_signoff
  ALTER COLUMN updated_at SET DEFAULT now();
