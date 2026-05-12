-- Quik Inspect — initial schema (Neon / PostgreSQL)
-- Idempotent: safe to re-run (e.g. after a partial run or new environments).
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS inspectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  first_name text NOT NULL,
  last_name text NOT NULL,
  phone text,
  signature_url text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS facilities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  inspector_id uuid NOT NULL REFERENCES inspectors (id) ON DELETE CASCADE,
  name text NOT NULL,
  region text,
  mmda text,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS facilities_inspector_lower_name ON facilities (inspector_id, lower(name));
CREATE INDEX IF NOT EXISTS facilities_inspector_region ON facilities (inspector_id, lower(region));

CREATE TABLE IF NOT EXISTS inspections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  inspector_id uuid NOT NULL REFERENCES inspectors (id) ON DELETE CASCADE,
  facility_id uuid REFERENCES facilities (id) ON DELETE SET NULL,
  type text NOT NULL DEFAULT 'pharmacy_routine',
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'signed')),
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  submitted_at timestamptz
);

CREATE INDEX IF NOT EXISTS inspections_inspector_created ON inspections (inspector_id, created_at DESC);
CREATE INDEX IF NOT EXISTS inspections_inspector_status ON inspections (inspector_id, status);

CREATE TABLE IF NOT EXISTS inspection_staff (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id uuid NOT NULL REFERENCES inspections (id) ON DELETE CASCADE,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inspection_staff_inspection ON inspection_staff (inspection_id);

CREATE TABLE IF NOT EXISTS inspection_responses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id uuid NOT NULL REFERENCES inspections (id) ON DELETE CASCADE,
  question_key text NOT NULL,
  value jsonb,
  flagged boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (inspection_id, question_key)
);

CREATE INDEX IF NOT EXISTS inspection_responses_inspection ON inspection_responses (inspection_id);

CREATE TABLE IF NOT EXISTS inspection_signoff (
  inspection_id uuid PRIMARY KEY REFERENCES inspections (id) ON DELETE CASCADE,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);
