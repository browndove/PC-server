-- Legacy DBs already had public.inspectors (different shape). 001_init skips CREATE;
-- the app still expects updated_at + signature_url for signup and /auth/me.
ALTER TABLE public.inspectors
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.inspectors
  ADD COLUMN IF NOT EXISTS signature_url text;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'inspectors'
      AND column_name = 'signature_ref'
  ) THEN
    EXECUTE
      $u$
      UPDATE public.inspectors
      SET signature_url = signature_ref
      WHERE signature_url IS NULL AND signature_ref IS NOT NULL
      $u$;
  END IF;
END $$;

-- Canonical signup INSERT only sends first_name / last_name. Legacy schemas often
-- had NOT NULL full_name; without a default, INSERT hits 23502.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'inspectors'
      AND column_name = 'full_name'
  ) THEN
    BEGIN
      EXECUTE 'ALTER TABLE public.inspectors ALTER COLUMN full_name DROP NOT NULL';
    EXCEPTION
      WHEN OTHERS THEN
        NULL;
    END;
  END IF;
END $$;
