-- After 001 creates inspectors: fill nullable inspector_id, drop unusable rows, enforce NOT NULL + FK.

DO $$
DECLARE
  insp uuid;
BEGIN
  IF to_regclass('public.inspectors') IS NOT NULL THEN
    SELECT id INTO insp FROM public.inspectors ORDER BY created_at NULLS LAST LIMIT 1;
  END IF;

  IF to_regclass('public.inspections') IS NOT NULL
     AND EXISTS (
       SELECT 1
       FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'inspections'
         AND column_name = 'inspector_id'
     )
  THEN
    IF insp IS NOT NULL THEN
      UPDATE public.inspections SET inspector_id = insp WHERE inspector_id IS NULL;
    END IF;
    DELETE FROM public.inspections WHERE inspector_id IS NULL;
    ALTER TABLE public.inspections ALTER COLUMN inspector_id SET NOT NULL;
    BEGIN
      ALTER TABLE public.inspections
        ADD CONSTRAINT inspections_inspector_id_fkey
        FOREIGN KEY (inspector_id) REFERENCES public.inspectors (id) ON DELETE CASCADE;
    EXCEPTION
      WHEN duplicate_object THEN
        NULL;
    END;
  END IF;

  IF to_regclass('public.facilities') IS NOT NULL
     AND EXISTS (
       SELECT 1
       FROM information_schema.columns
       WHERE table_schema = 'public'
         AND table_name = 'facilities'
         AND column_name = 'inspector_id'
     )
  THEN
    IF insp IS NOT NULL THEN
      UPDATE public.facilities SET inspector_id = insp WHERE inspector_id IS NULL;
    END IF;
    DELETE FROM public.facilities WHERE inspector_id IS NULL;
    ALTER TABLE public.facilities ALTER COLUMN inspector_id SET NOT NULL;
    BEGIN
      ALTER TABLE public.facilities
        ADD CONSTRAINT facilities_inspector_id_fkey
        FOREIGN KEY (inspector_id) REFERENCES public.inspectors (id) ON DELETE CASCADE;
    EXCEPTION
      WHEN duplicate_object THEN
        NULL;
    END;
  END IF;
END $$;
