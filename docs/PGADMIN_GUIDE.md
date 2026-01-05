# pgAdmin Access Guide

pgAdmin is a web-based database management tool for PostgreSQL. It's running in a Docker container on your EC2 instance.

## Accessing pgAdmin

### Step 1: Start SSH Tunnel

Open Git Bash and run:
```bash
bash pgadmin_tunnel.sh
```

Or manually:
```bash
ssh -i "C:/Users/gdsak/OneDrive/Desktop/starsceen_key.pem" -L 5050:localhost:5050 ubuntu@54.158.113.25 -N
```

**Keep this terminal window open** - it will appear to hang, which is normal. This creates a secure tunnel to pgAdmin.

### Step 2: Access pgAdmin in Browser

Open your web browser and go to:
```
http://localhost:5050
```

### Step 3: Login to pgAdmin

Use these credentials:
- **Email**: `admin@starscreen.net`
- **Password**: `Starscreen2026!`

## Connecting to Your Database

Once logged into pgAdmin:

### First Time Setup

1. Click **"Add New Server"** (or right-click "Servers" → Register → Server)

2. **General Tab**:
   - **Name**: `Starscreen Production`

3. **Connection Tab**:
   - **Host name/address**: `db`
   - **Port**: `5432`
   - **Maintenance database**: `starscreen_prod`
   - **Username**: `starscreen_user`
   - **Password**: `Ilikecode1!`

4. **Advanced Tab** (optional):
   - Check **"Save password"** if you want to avoid re-entering it

5. Click **"Save"**

### Database Structure

After connecting, you'll see:
```
Starscreen Production
└── Databases
    └── starscreen_prod
        └── Schemas
            └── public
                ├── Tables
                │   ├── alembic_version
                │   ├── candidates
                │   ├── job_postings
                │   ├── subscriptions
                │   └── users
                └── Sequences
```

## Common Tasks

### View Table Data
1. Navigate to: Databases → starscreen_prod → Schemas → public → Tables
2. Right-click on a table (e.g., `users`)
3. Select **"View/Edit Data"** → **"All Rows"**

### Run SQL Queries
1. Right-click on `starscreen_prod` database
2. Select **"Query Tool"**
3. Type your SQL query
4. Press **F5** or click the ▶️ play button

Example queries:
```sql
-- View all users
SELECT * FROM users;

-- View all job postings
SELECT * FROM job_postings;

-- View subscription counts by tier
SELECT subscription_tier, COUNT(*)
FROM users
GROUP BY subscription_tier;
```

### Export Data
1. Right-click on a table
2. Select **"Import/Export Data"**
3. Choose format (CSV, JSON, etc.)
4. Select options and download

### View Database Size
Run this query in the Query Tool:
```sql
SELECT
    pg_size_pretty(pg_database_size('starscreen_prod')) as database_size;
```

### Check Active Connections
```sql
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state
FROM pg_stat_activity
WHERE datname = 'starscreen_prod';
```

## Troubleshooting

### Can't Connect to localhost:5050
- Check that the SSH tunnel is still running
- Make sure you didn't close the terminal running `pgadmin_tunnel.sh`
- Try stopping and restarting the tunnel

### "Could not connect to server" in pgAdmin
- Use hostname `db` (not `localhost` or `54.158.113.25`)
- This is because you're connecting from within the Docker network
- Make sure the credentials are correct

### SSH Tunnel Keeps Disconnecting
Add these options to keep the connection alive:
```bash
ssh -i "C:/Users/gdsak/OneDrive/Desktop/starsceen_key.pem" \
    -L 5050:localhost:5050 \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    ubuntu@54.158.113.25 -N
```

## Security Notes

✅ **Using SSH tunnel is secure** - data is encrypted
⚠️ **Don't open port 5050** to the internet - anyone could access your database admin panel
🔒 **Keep your pgAdmin password strong** - it's currently set to `Starscreen2026!`

## Stopping pgAdmin Access

To stop the SSH tunnel:
1. Go to the terminal running the tunnel
2. Press **Ctrl+C**

The pgAdmin container will keep running on EC2, you just won't be able to access it until you create the tunnel again.

## Alternative: Direct Database Connection Tools

If you prefer, you can use other database tools with a direct connection:

**Using DBeaver, TablePlus, or other GUI tools:**
- **Host**: `54.158.113.25`
- **Port**: `5433` (note: external port is 5433, not 5432)
- **Database**: `starscreen_prod`
- **Username**: `starscreen_user`
- **Password**: `Ilikecode1!`

**Using psql command line:**
```bash
psql -h 54.158.113.25 -p 5433 -U starscreen_user -d starscreen_prod
```
