# Database Migrations Applied

Track which migrations have been applied to the database.

## Format
- [ ] Not applied
- [x] Applied
- Date applied in parentheses

## Migrations

- [x] `f93f4b3e658f_initial_schema.py` - Initial database schema (auto-applied on first run)
- [ ] `a1b2c3d4e5f6_add_cascade_delete_evaluations.py` - Add CASCADE delete for evaluations
- [ ] `b2c3d4e5f6a7_add_soft_delete_to_candidates.py` - Add soft delete columns for EEOC/OFCCP compliance
  - Adds: is_deleted, deleted_at, deleted_by_user_id, retention_until
  - **Alternative:** Run `migrations/add_soft_delete.sql` directly

## How to Apply Migrations

### Option 1: Using alembic (if dependencies installed)
```bash
alembic upgrade head
```

### Option 2: Using Docker + SQL file (recommended for production)
```bash
cat migrations/add_soft_delete.sql | docker-compose exec -T db psql -U user -d talent_db
```

### Option 3: Via pgAdmin
1. Access pgAdmin at http://your-server:5050
2. Connect to database
3. Run the SQL from `migrations/add_soft_delete.sql`

## Check Current Database Version

```bash
# Via Docker
docker-compose exec db psql -U user -d talent_db -c "SELECT version_num FROM alembic_version;"

# Check if soft delete columns exist
docker-compose exec db psql -U user -d talent_db -c "\d candidates" | grep deleted
```

## Mark as Applied

Once you run the migration, mark it here:

```markdown
- [x] `b2c3d4e5f6a7_add_soft_delete_to_candidates.py` (Applied: 2026-01-02)
```
