-- Migration: Add soft delete columns to candidates table
-- Run this SQL script to add EEOC/OFCCP compliance features

-- Add soft delete columns
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deleted_by_user_id INTEGER;
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS retention_until TIMESTAMP WITH TIME ZONE;

-- Create index for performance
CREATE INDEX IF NOT EXISTS ix_candidates_is_deleted ON candidates(is_deleted);

-- Add foreign key constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'candidates_deleted_by_user_id_fkey'
    ) THEN
        ALTER TABLE candidates
        ADD CONSTRAINT candidates_deleted_by_user_id_fkey
        FOREIGN KEY (deleted_by_user_id) REFERENCES users(id);
    END IF;
END $$;

-- Fix cascade delete for evaluations
DO $$
BEGIN
    ALTER TABLE evaluations DROP CONSTRAINT IF EXISTS evaluations_candidate_id_fkey;
    ALTER TABLE evaluations
    ADD CONSTRAINT evaluations_candidate_id_fkey
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE;
END $$;

-- Verify the changes
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'candidates'
  AND column_name IN ('is_deleted', 'deleted_at', 'deleted_by_user_id', 'retention_until')
ORDER BY column_name;
