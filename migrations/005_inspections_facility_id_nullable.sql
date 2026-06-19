-- Draft routine inspections are created before a facility exists; API expects NULL facility_id.
-- Legacy schemas sometimes marked facility_id NOT NULL.

DO $$
BEGIN
  IF to_regclass('public.inspections') IS NULL THEN
    RETURN;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'inspections'
      AND column_name = 'facility_id'
      AND is_nullable = 'NO'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspections ALTER COLUMN facility_id DROP NOT NULL';
  END IF;
END $$;
