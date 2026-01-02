"""
Quick script to manually run the soft delete migration.
Run this with: python run_migration.py
"""
import os
from sqlalchemy import create_engine, text

# Get database URL from environment or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/talent_db"
)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

migrations = [
    # Add soft delete columns
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT false;",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS deleted_by_user_id INTEGER;",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS retention_until TIMESTAMP WITH TIME ZONE;",

    # Create index
    "CREATE INDEX IF NOT EXISTS ix_candidates_is_deleted ON candidates(is_deleted);",

    # Add foreign key
    """
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
    """,

    # Also fix the cascade delete for evaluations
    """
    DO $$
    BEGIN
        ALTER TABLE evaluations DROP CONSTRAINT IF EXISTS evaluations_candidate_id_fkey;
        ALTER TABLE evaluations
        ADD CONSTRAINT evaluations_candidate_id_fkey
        FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE;
    END $$;
    """
]

try:
    with engine.connect() as conn:
        for i, migration in enumerate(migrations, 1):
            print(f"Running migration {i}/{len(migrations)}...")
            conn.execute(text(migration))
            conn.commit()
            print(f"  ✓ Migration {i} completed")

    print("\n✅ All migrations completed successfully!")
    print("\nNew columns added to candidates table:")
    print("  - is_deleted (boolean, default false)")
    print("  - deleted_at (timestamp)")
    print("  - deleted_by_user_id (integer, FK to users)")
    print("  - retention_until (timestamp)")
    print("\nYour application should now work correctly!")

except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    print("\nPlease check:")
    print("  1. Database is running")
    print("  2. DATABASE_URL is correct")
    print("  3. You have permission to alter tables")
