# Database Migration Guide

## Quick Fix: Add Soft Delete Columns

You're getting the error because the database needs to be updated with the new columns. Here are your options:

### Option 1: Using Docker (Recommended if you have Docker running)

```bash
# Start Docker Desktop, then run:
docker-compose up -d db
docker-compose exec db psql -U user -d talent_db -f /migrations/add_soft_delete.sql
```

### Option 2: Using psql directly (if PostgreSQL is installed locally)

```bash
psql -U user -d talent_db -f migrations/add_soft_delete.sql
```

### Option 3: Using pgAdmin or any PostgreSQL GUI

1. Open your PostgreSQL GUI tool (pgAdmin, DBeaver, etc.)
2. Connect to the `talent_db` database
3. Open the file: `migrations/add_soft_delete.sql`
4. Execute the entire script

### Option 4: Manual SQL Execution

Copy and paste these commands into your PostgreSQL console:

```sql
-- Add soft delete columns
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deleted_by_user_id INTEGER;
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS retention_until TIMESTAMP WITH TIME ZONE;

-- Create index
CREATE INDEX IF NOT EXISTS ix_candidates_is_deleted ON candidates(is_deleted);

-- Add foreign key
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
```

## What This Migration Does

1. **Adds 4 new columns** to the `candidates` table:
   - `is_deleted` - Marks candidates as deleted (but keeps the data)
   - `deleted_at` - Timestamp when deleted
   - `deleted_by_user_id` - Who deleted it (audit trail)
   - `retention_until` - When it can be permanently purged (3 years by default)

2. **Creates an index** on `is_deleted` for fast queries

3. **Adds foreign key** to track who deleted records

4. **Fixes cascade delete** so evaluations are deleted when candidates are deleted

## After Running the Migration

Your app should work normally. When users click "Delete" on a candidate:
- The record is marked as deleted (invisible in UI)
- The file is kept in storage
- After 3 years, it can be purged (for EEOC/OFCCP compliance)

## Verification

To verify the migration worked, run:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'candidates'
  AND column_name LIKE '%delete%';
```

You should see the 4 new columns listed.
