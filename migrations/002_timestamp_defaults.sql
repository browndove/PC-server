-- Fix NOT NULL timestamp columns without DEFAULT (INSERT then fails with 23502).
-- Each ALTER runs only if the table and column exist (legacy DBs may use different shapes).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspectors' AND column_name = 'created_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspectors ALTER COLUMN created_at SET DEFAULT now()';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspectors' AND column_name = 'updated_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspectors ALTER COLUMN updated_at SET DEFAULT now()';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'facilities' AND column_name = 'created_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.facilities ALTER COLUMN created_at SET DEFAULT now()';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'facilities' AND column_name = 'updated_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.facilities ALTER COLUMN updated_at SET DEFAULT now()';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'created_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspections ALTER COLUMN created_at SET DEFAULT now()';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'updated_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspections ALTER COLUMN updated_at SET DEFAULT now()';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspection_staff' AND column_name = 'created_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspection_staff ALTER COLUMN created_at SET DEFAULT now()';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspection_staff' AND column_name = 'updated_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspection_staff ALTER COLUMN updated_at SET DEFAULT now()';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspection_responses' AND column_name = 'updated_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspection_responses ALTER COLUMN updated_at SET DEFAULT now()';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspection_signoff' AND column_name = 'updated_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspection_signoff ALTER COLUMN updated_at SET DEFAULT now()';
  END IF;
END $$;
