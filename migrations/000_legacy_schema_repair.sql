-- Before 001: old DBs may already have facilities/inspections without inspector_id.
-- CREATE TABLE IF NOT EXISTS then skips, and CREATE INDEX on inspector_id fails.
-- Add nullable columns only; 003 backfills + NOT NULL + FK after inspectors exists.

DO $$
BEGIN
  IF to_regclass('public.facilities') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'facilities'
        AND column_name = 'inspector_id'
    ) THEN
      ALTER TABLE public.facilities ADD COLUMN inspector_id uuid;
    END IF;
  END IF;

  IF to_regclass('public.inspections') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'inspections'
        AND column_name = 'inspector_id'
    ) THEN
      ALTER TABLE public.inspections ADD COLUMN inspector_id uuid;
    END IF;
  END IF;
END $$;
