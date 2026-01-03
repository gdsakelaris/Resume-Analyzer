# AWS Server Database Management Guide

## 🔧 Run the Migration on Your Server

You're on the server now. Run these commands:

```bash
# Option 1: Copy SQL into container and run it
docker-compose exec -T db psql -U user -d talent_db << 'EOF'
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
EOF
```

Or simpler:

```bash
# Option 2: Use the migration file
cat migrations/add_soft_delete.sql | docker-compose exec -T db psql -U user -d talent_db
```

## 🗄️ Database Management Tool Recommendations

### Option 1: pgAdmin (Recommended for AWS)

**Best for:** Full-featured management, backups, query building

**Setup:**

1. **Run pgAdmin in Docker** (easiest):
```bash
# Add to your docker-compose.yml
pgadmin:
  image: dpage/pgadmin4:latest
  environment:
    PGADMIN_DEFAULT_EMAIL: admin@yourdomain.com
    PGADMIN_DEFAULT_PASSWORD: your-secure-password
    PGADMIN_LISTEN_PORT: 5050
  ports:
    - "5050:5050"
  depends_on:
    - db
```

2. **Start it:**
```bash
docker-compose up -d pgadmin
```

3. **Access it:**
- URL: `http://your-aws-ip:5050`
- Login with email/password from above
- Add connection:
  - Host: `db` (Docker network name)
  - Port: `5432`
  - Database: `talent_db`
  - Username: `user`
  - Password: `password`

**Security:** Make sure to:
- Use strong password
- Set up AWS security group to only allow your IP
- Or use SSH tunnel (see below)

### Option 2: Adminer (Lightweight Alternative)

**Best for:** Simple, one-file, lightweight admin

**Setup:**

```bash
# Add to docker-compose.yml
adminer:
  image: adminer
  restart: always
  ports:
    - 8080:8080
  depends_on:
    - db
```

**Access:** `http://your-aws-ip:8080`
- System: PostgreSQL
- Server: `db`
- Username: `user`
- Password: `password`
- Database: `talent_db`

### Option 3: DBeaver (Desktop Client)

**Best for:** Local desktop management, advanced features

**Setup:**
1. Download: https://dbeaver.io/download/
2. Install on your local machine
3. Connect via SSH tunnel:

```bash
# On your local machine, create SSH tunnel:
ssh -i your-key.pem -L 5432:localhost:5432 ubuntu@your-aws-ip

# Keep this terminal open
# In DBeaver, connect to localhost:5432
```

### Option 4: AWS RDS (If using RDS instead of Docker)

If you migrate to AWS RDS PostgreSQL:
- Query Editor in AWS Console
- Enhanced Monitoring
- Automated Backups
- Performance Insights

## 🔐 Secure Database Access

### Best Practice: SSH Tunnel

**Why:** Never expose PostgreSQL directly to the internet

**Setup:**
```bash
# Local machine - create tunnel
ssh -i ~/.ssh/your-key.pem -L 5432:localhost:5432 ubuntu@your-aws-ip -N

# Now connect any tool to localhost:5432
```

### AWS Security Group Rules

**For pgAdmin/Adminer:**
```
Type: Custom TCP
Port: 5050 (pgAdmin) or 8080 (Adminer)
Source: Your IP address only (e.g., 123.45.67.89/32)
```

**For direct PostgreSQL (NOT recommended):**
```
Type: PostgreSQL
Port: 5432
Source: Your IP only (e.g., 123.45.67.89/32)
```

## 📊 Quick Database Management Commands

### From Server (SSH):

```bash
# Access PostgreSQL directly
docker-compose exec db psql -U user -d talent_db

# List tables
docker-compose exec db psql -U user -d talent_db -c "\dt"

# Check candidates table structure
docker-compose exec db psql -U user -d talent_db -c "\d candidates"

# Count soft-deleted candidates
docker-compose exec db psql -U user -d talent_db -c "SELECT COUNT(*) FROM candidates WHERE is_deleted = true;"

# View recent candidates
docker-compose exec db psql -U user -d talent_db -c "SELECT id, original_filename, is_deleted, deleted_at FROM candidates ORDER BY created_at DESC LIMIT 10;"

# Create backup
docker-compose exec db pg_dump -U user talent_db > backup_$(date +%Y%m%d).sql

# Restore backup
docker-compose exec -T db psql -U user -d talent_db < backup_20260102.sql
```

## 🎯 My Recommendation

**For your setup, I recommend:**

1. **Short term:** Use pgAdmin in Docker (easiest, most features)
2. **Long term:** Consider AWS RDS PostgreSQL for:
   - Automated backups
   - Automatic failover
   - Better monitoring
   - Easier scaling
   - Less maintenance

## 📝 Quick Setup Script

Save this as `setup-pgadmin.sh`:

```bash
#!/bin/bash

# Add pgAdmin to docker-compose if not exists
if ! grep -q "pgadmin:" docker-compose.yml; then
    cat >> docker-compose.yml << 'PGADMIN'

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: resume-analyzer-pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@starscreen.com
      PGADMIN_DEFAULT_PASSWORD: ChangeThisPassword123!
      PGADMIN_LISTEN_PORT: 5050
    ports:
      - "5050:5050"
    depends_on:
      - db
    networks:
      - app-network
PGADMIN

    echo "✅ pgAdmin added to docker-compose.yml"
    echo "Starting pgAdmin..."
    docker-compose up -d pgadmin
    echo ""
    echo "🌐 Access pgAdmin at: http://$(curl -s ifconfig.me):5050"
    echo "📧 Email: admin@starscreen.com"
    echo "🔑 Password: ChangeThisPassword123!"
    echo ""
    echo "⚠️  IMPORTANT: Change the password in docker-compose.yml!"
else
    echo "pgAdmin already configured"
fi
```

Run it: `bash setup-pgadmin.sh`
