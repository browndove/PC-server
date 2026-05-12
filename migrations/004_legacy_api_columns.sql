-- Legacy Neon schemas: inspections may use inspection_type / created_by and omit type, data, submitted_at.
-- Facilities may omit meta (and mmda). The FastAPI list endpoints SELECT fixed column sets.

DO $$
BEGIN
  IF to_regclass('public.inspections') IS NOT NULL THEN

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'created_by'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'inspector_id'
  ) THEN
    EXECUTE $sync$
      UPDATE public.inspections
      SET inspector_id = created_by
      WHERE created_by IS NOT NULL AND inspector_id IS DISTINCT FROM created_by
    $sync$;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'type'
  ) THEN
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'inspection_type'
    ) THEN
      EXECUTE 'ALTER TABLE public.inspections ADD COLUMN type text';
      EXECUTE $t$
        UPDATE public.inspections
        SET type = COALESCE(NULLIF(trim(inspection_type::text), ''), 'pharmacy_routine')
      $t$;
      EXECUTE 'ALTER TABLE public.inspections ALTER COLUMN type SET DEFAULT ''pharmacy_routine''';
      EXECUTE $t2$UPDATE public.inspections SET type = 'pharmacy_routine' WHERE type IS NULL$t2$;
      EXECUTE 'ALTER TABLE public.inspections ALTER COLUMN type SET NOT NULL';
    ELSE
      EXECUTE 'ALTER TABLE public.inspections ADD COLUMN type text NOT NULL DEFAULT ''pharmacy_routine''';
    END IF;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'data'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspections ADD COLUMN data jsonb NOT NULL DEFAULT ''{}''::jsonb';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'submitted_at'
  ) THEN
    EXECUTE 'ALTER TABLE public.inspections ADD COLUMN submitted_at timestamptz';
  END IF;

  END IF;
END $$;

ALTER TABLE public.facilities ADD COLUMN IF NOT EXISTS mmda text;

ALTER TABLE public.facilities ADD COLUMN IF NOT EXISTS meta jsonb;

UPDATE public.facilities SET meta = '{}'::jsonb WHERE meta IS NULL;

DO $$
BEGIN
  BEGIN
    ALTER TABLE public.facilities ALTER COLUMN meta SET NOT NULL;
  EXCEPTION
    WHEN others THEN
      NULL;
  END;
END $$;

DO $$
BEGIN
  BEGIN
    ALTER TABLE public.facilities ALTER COLUMN meta SET DEFAULT '{}'::jsonb;
  EXCEPTION
    WHEN others THEN
      NULL;
  END;
END $$;
