-- Legacy ``inspections`` rows may require ``inspection_type`` (enum) and ``inspection_date``
-- while the mobile API only sets ``type`` (text: pharmacy_routine / otcms_routine) and ``data``.

DO $$
BEGIN
  IF to_regclass('public.inspections') IS NULL THEN
    RETURN;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'inspection_date'
  ) THEN
    UPDATE public.inspections
    SET inspection_date = COALESCE(inspection_date, CURRENT_DATE)
    WHERE inspection_date IS NULL;
    BEGIN
      ALTER TABLE public.inspections ALTER COLUMN inspection_date SET DEFAULT (CURRENT_DATE);
    EXCEPTION WHEN others THEN
      NULL;
    END;
    BEGIN
      ALTER TABLE public.inspections ALTER COLUMN inspection_date DROP NOT NULL;
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.inspections_legacy_from_type()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'inspection_type'
  ) THEN
    IF NEW.type = 'otcms_routine' THEN
      NEW.inspection_type := 'over_the_counter'::public.inspection_type_enum;
    ELSE
      NEW.inspection_type := 'pharmacy'::public.inspection_type_enum;
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'inspection_date'
  ) AND NEW.inspection_date IS NULL THEN
    NEW.inspection_date := CURRENT_DATE;
  END IF;

  RETURN NEW;
END;
$fn$;

DO $$
BEGIN
  IF to_regclass('public.inspections') IS NULL THEN
    RETURN;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'inspections' AND column_name = 'inspection_type'
  ) THEN
    RETURN;
  END IF;

  DROP TRIGGER IF EXISTS inspections_legacy_from_type_trg ON public.inspections;
  CREATE TRIGGER inspections_legacy_from_type_trg
    BEFORE INSERT OR UPDATE OF type ON public.inspections
    FOR EACH ROW
    EXECUTE PROCEDURE public.inspections_legacy_from_type();
END $$;
