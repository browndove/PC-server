-- Inspector profile signature (PNG data URL or https asset) for team-leader auto-fill.
ALTER TABLE public.inspectors
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.inspectors
  ADD COLUMN IF NOT EXISTS signature_url text;
