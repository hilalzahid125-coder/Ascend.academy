SET LOCAL search_path = ascend, pg_catalog;
-- Subject is explicit metadata only; existing points and totals never change.
ALTER TABLE challenges ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE point_transactions ADD COLUMN IF NOT EXISTS subject TEXT;
