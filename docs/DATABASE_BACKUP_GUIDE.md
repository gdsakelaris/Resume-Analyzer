# Database Backup and Recovery Guide

## Overview

This guide covers database backup configuration, restoration procedures, and disaster recovery for the Resume Analyzer application.

## AWS RDS Automated Backups

### Configuration

1. **Enable Automated Backups** (if not already enabled):
   ```bash
   aws rds modify-db-instance \
     --db-instance-identifier your-db-instance \
     --backup-retention-period 7 \
     --preferred-backup-window "03:00-04:00" \
     --apply-immediately
   ```

2. **Backup Settings**:
   - **Retention Period**: 7 days (recommended minimum)
   - **Backup Window**: 3:00 AM - 4:00 AM UTC (low-traffic period)
   - **Automatic Backups**: Enabled
   - **Point-in-Time Recovery**: Enabled

3. **Verify Configuration**:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier your-db-instance \
     --query 'DBInstances[0].[BackupRetentionPeriod,PreferredBackupWindow]'
   ```

### Manual Snapshots

Create manual snapshots before:
- Major migrations
- Production deployments
- Schema changes

```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier your-db-instance \
  --db-snapshot-identifier pre-migration-$(date +%Y%m%d-%H%M%S)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier your-db-instance
```

## Backup Testing

**CRITICAL**: Test backup restoration monthly to ensure recoverability.

### Monthly Test Procedure

1. **Create Test Restoration** (DO NOT restore over production):
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier test-restore-$(date +%Y%m%d) \
     --db-snapshot-identifier your-snapshot-id \
     --db-instance-class db.t3.micro \
     --no-publicly-accessible
   ```

2. **Verify Data Integrity**:
   ```bash
   # Connect to restored instance
   psql -h test-restore-instance.xxx.rds.amazonaws.com -U postgres -d resume_analyzer

   # Check record counts
   SELECT 'users' as table_name, COUNT(*) FROM users
   UNION ALL
   SELECT 'jobs', COUNT(*) FROM jobs
   UNION ALL
   SELECT 'candidates', COUNT(*) FROM candidates;
   ```

3. **Delete Test Instance**:
   ```bash
   aws rds delete-db-instance \
     --db-instance-identifier test-restore-$(date +%Y%m%d) \
     --skip-final-snapshot
   ```

## Point-in-Time Recovery (PITR)

Restore database to any point within the retention period:

```bash
# Restore to specific time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier your-db-instance \
  --target-db-instance-identifier restored-db-$(date +%Y%m%d) \
  --restore-time 2025-01-02T10:30:00Z
```

## Disaster Recovery Procedure

### In Case of Data Loss

1. **Identify Recovery Point**:
   - What time do we need to restore to?
   - What data was lost?

2. **Create New Instance from Snapshot**:
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier recovery-instance \
     --db-snapshot-identifier latest-snapshot
   ```

3. **Update Application Connection**:
   - Update `DATABASE_URL` in `.env`
   - Restart application services
   - Verify connectivity

4. **Post-Recovery Verification**:
   - Check all critical tables
   - Verify user authentication works
   - Test job and candidate operations
   - Review application logs for errors

## Local Development Backups

For local PostgreSQL instances:

```bash
# Create backup
pg_dump -U postgres resume_analyzer > backup_$(date +%Y%m%d).sql

# Restore backup
psql -U postgres resume_analyzer < backup_20250102.sql
```

## Backup Monitoring

### CloudWatch Alarms

Set up alarms for:
- Backup failures
- Storage running low
- Backup older than 24 hours

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name rds-backup-failed \
  --alarm-description "Alert when RDS backup fails" \
  --metric-name SnapshotStorageUsed \
  --namespace AWS/RDS \
  --statistic Average \
  --period 86400 \
  --threshold 0 \
  --comparison-operator LessThanThreshold
```

## Retention Policy

| Backup Type | Retention Period | Purpose |
|-------------|------------------|---------|
| Automated Daily | 7 days | Regular recovery |
| Pre-Migration | 30 days | Rollback safety |
| Monthly Archive | 12 months | Compliance/Audit |
| Major Release | Indefinite | Historical reference |

## Best Practices

1. ✅ **Test restores monthly** - Untested backups are useless
2. ✅ **Snapshot before migrations** - Always have a rollback point
3. ✅ **Monitor backup health** - Set up CloudWatch alarms
4. ✅ **Document recovery procedures** - Keep this guide updated
5. ✅ **Encrypt backups** - Use AWS KMS for encryption at rest
6. ✅ **Store backup metadata** - Track what each backup contains

## Emergency Contacts

- **Database Admin**: [Your contact]
- **AWS Support**: [Support plan details]
- **On-Call Engineer**: [PagerDuty/Phone]

## Checklist for New Team Members

- [ ] Understand backup schedule
- [ ] Practice restore procedure in test environment
- [ ] Know where to find latest backup
- [ ] Understand RTO (Recovery Time Objective): 1 hour
- [ ] Understand RPO (Recovery Point Objective): 24 hours
