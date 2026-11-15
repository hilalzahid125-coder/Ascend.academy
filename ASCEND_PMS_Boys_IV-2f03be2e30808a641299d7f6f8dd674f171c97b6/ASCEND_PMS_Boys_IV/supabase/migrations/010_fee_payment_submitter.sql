SET LOCAL search_path = ascend, pg_catalog;
ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS submitted_by INTEGER REFERENCES users(id);
