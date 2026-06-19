-- Legacy ``facilities`` rows may require ``facility_type`` (enum) and NOT NULL ``region``
-- while the API only inserts (inspector_id, name, region, mmda, meta).

DO $$
BEGIN
  IF to_regclass('public.facilities') IS NULL THEN
    RETURN;
  END IF;

  CREATE OR REPLACE FUNCTION public.facilities_legacy_insert_defaults()
  RETURNS trigger
  LANGUAGE plpgsql
  AS $fn$
  BEGIN
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'facilities' AND column_name = 'facility_type'
    ) AND NEW.facility_type IS NULL THEN
      IF NEW.meta IS NOT NULL AND (NEW.meta::jsonb ->> 'source') = 'otcms_routine_part1' THEN
        NEW.facility_type := 'over_the_counter'::public.facility_type_enum;
      ELSE
        NEW.facility_type := 'pharmacy'::public.facility_type_enum;
      END IF;
    END IF;

    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'facilities'
        AND column_name = 'region'
        AND is_nullable = 'NO'
    ) AND (NEW.region IS NULL OR btrim(NEW.region) = '') THEN
      NEW.region := '';
    END IF;

    RETURN NEW;
  END;
  $fn$;

  DROP TRIGGER IF EXISTS facilities_legacy_insert_defaults_trg ON public.facilities;
  CREATE TRIGGER facilities_legacy_insert_defaults_trg
    BEFORE INSERT ON public.facilities
    FOR EACH ROW
    EXECUTE PROCEDURE public.facilities_legacy_insert_defaults();
END $$;
