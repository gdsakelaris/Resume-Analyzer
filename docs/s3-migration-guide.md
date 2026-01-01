# AWS S3 Storage Migration Guide

> **Purpose**: This guide explains how to migrate from local file storage to AWS S3 for horizontal scalability.

**Status**: ✅ Code Complete - S3 integration implemented, backward compatible with local storage

**When to Enable S3**: Before deploying multiple API servers or worker containers

---

## Why S3 is Critical for Scaling

### Current Problem (Local Storage)
- Resumes stored in `uploads/` directory on disk
- Works fine for single-server deployment
- **Breaks horizontal scaling**: Worker 1 uploads file → Worker 2 can't access it
- Container restart = lost files

### Solution (S3 Storage)
- Resumes stored in AWS S3 bucket
- All API servers and workers access same S3 bucket
- Stateless containers (can scale horizontally)
- 99.999999999% durability (no data loss)
- Pre-signed URLs for direct browser uploads (Phase 3 optimization)

---

## Architecture Changes

### Before (Local Storage)
```
Browser → API Server → Local uploads/ → Worker reads from uploads/
```

### After (S3 Storage)
```
Browser → API Server → S3 Bucket → Worker downloads from S3
                ↓
         Multiple API Servers (all access same S3 bucket)
                ↓
         Multiple Workers (all access same S3 bucket)
```

---

## Setup Instructions

### Step 1: Create S3 Bucket

1. **Login to AWS Console**: https://console.aws.amazon.com/s3

2. **Create Bucket**:
   - Name: `starscreen-resumes-prod` (must be globally unique)
   - Region: `us-east-1` (or your preferred region)
   - Block all public access: **ENABLED** (resumes are private)
   - Versioning: Optional (recommended for data recovery)
   - Encryption: **Enable** (AES-256 server-side encryption)

3. **Bucket Policy** (Optional - for stricter security):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "AllowStarscreenAppAccess",
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:user/starscreen-app"
         },
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject"
         ],
         "Resource": "arn:aws:s3:::starscreen-resumes-prod/resumes/*"
       }
     ]
   }
   ```

### Step 2: Create IAM User (If not using IAM Roles)

**Option A: IAM User with Access Keys** (for development, local testing)

1. **Create IAM User**:
   - Name: `starscreen-app`
   - Access type: Programmatic access (generates access key)

2. **Attach Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject",
           "s3:HeadObject"
         ],
         "Resource": "arn:aws:s3:::starscreen-resumes-prod/resumes/*"
       }
     ]
   }
   ```

3. **Copy Credentials**:
   - Access Key ID: `AKIAIOSFODNN7EXAMPLE`
   - Secret Access Key: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

**Option B: IAM Roles** (for production EC2/ECS)

1. **Create IAM Role**:
   - Trusted entity: EC2 or ECS
   - Attach same S3 policy as above

2. **Attach Role to EC2/ECS**:
   - No need for access keys (more secure)
   - Credentials automatically rotated by AWS

### Step 3: Update Environment Variables

Edit `.env` file:

```bash
# AWS S3 File Storage Settings
USE_S3=true  # CHANGE FROM false TO true

# AWS Credentials (skip if using IAM roles on EC2/ECS)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# S3 Bucket for resume storage
S3_BUCKET_NAME=starscreen-resumes-prod
```

### Step 4: Install boto3 Dependency

**Local Development**:
```bash
pip install boto3==1.34.34
```

**Docker (already in requirements.txt)**:
```bash
docker-compose down
docker-compose build  # Rebuilds with boto3
docker-compose up -d
```

### Step 5: Test S3 Integration

**Test Upload**:
```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!@#"
  }'

# Create job
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Job",
    "description": "Test description"
  }'

# Upload resume
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/resume.pdf"

# Check S3 bucket - you should see file at:
# s3://starscreen-resumes-prod/resumes/{uuid}_{filename}.pdf
```

**Verify in AWS Console**:
1. Navigate to S3 → `starscreen-resumes-prod` → `resumes/`
2. You should see uploaded files with UUID prefixes

---

## Database Schema (No Changes Required)

The `candidates.file_path` column now stores:

**Local Storage** (USE_S3=false):
```
uploads/abc123.pdf
```

**S3 Storage** (USE_S3=true):
```
s3://starscreen-resumes-prod/resumes/abc123_resume.pdf
```

No database migration needed - the column is already a VARCHAR that supports both formats.

---

## Code Changes Summary

### Files Modified

1. **app/core/config.py**
   - Added S3 configuration settings (AWS_ACCESS_KEY_ID, AWS_REGION, S3_BUCKET_NAME, USE_S3)

2. **app/core/storage.py** (NEW FILE)
   - Storage abstraction layer
   - `LocalStorage` class: Handles local filesystem
   - `S3Storage` class: Handles AWS S3
   - `get_storage()` factory: Returns correct backend based on USE_S3

3. **app/api/endpoints/candidates.py**
   - Updated `upload_resume()`: Uses `storage.upload_file()` instead of local file writes
   - Updated `bulk_upload_resumes()`: Uses `storage.upload_file()` for ZIP extracts
   - Updated `delete_candidate()`: Uses `storage.delete_file()` instead of `os.remove()`
   - Updated `get_candidate_file()`: Downloads from S3 if USE_S3=true

4. **app/tasks/resume_tasks.py**
   - Updated `parse_resume_task()`: Downloads file from S3 to temp location before parsing
   - Auto-cleanup of temp files after processing

5. **.env**
   - Added AWS S3 configuration variables

6. **requirements.txt**
   - Added `boto3==1.34.34` for S3 SDK

### Backward Compatibility

✅ **100% Backward Compatible**

- If `USE_S3=false`: Works exactly as before (local storage)
- If `USE_S3=true`: Uses S3 storage
- No breaking changes to API responses or database schema

---

## Migration Plan (Existing Data)

If you already have resumes in `uploads/` directory and want to migrate to S3:

### Option 1: Fresh Start (Recommended for MVP)
1. Enable S3: `USE_S3=true`
2. Delete old data: `rm -rf uploads/*`
3. All new uploads go to S3

### Option 2: Migrate Existing Files
Use this Python script to copy existing files to S3:

```python
import os
import boto3
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.candidate import Candidate

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)

db = SessionLocal()
candidates = db.query(Candidate).all()

for candidate in candidates:
    local_path = candidate.file_path

    # Skip if already S3 URI
    if local_path.startswith("s3://"):
        continue

    # Upload to S3
    if os.path.exists(local_path):
        filename = os.path.basename(local_path)
        s3_key = f"resumes/{filename}"

        s3_client.upload_file(
            local_path,
            settings.S3_BUCKET_NAME,
            s3_key
        )

        # Update database
        candidate.file_path = f"s3://{settings.S3_BUCKET_NAME}/{s3_key}"
        print(f"Migrated {local_path} → {candidate.file_path}")

db.commit()
db.close()
print("Migration complete!")
```

---

## Cost Estimation

### S3 Storage Costs (us-east-1)

**Storage**: $0.023 per GB/month
- 1,000 resumes × 500KB average = 500MB = $0.012/month
- 10,000 resumes = 5GB = $0.12/month
- 100,000 resumes = 50GB = $1.15/month

**PUT Requests**: $0.005 per 1,000 requests
- 1,000 uploads = $0.005
- 10,000 uploads = $0.05

**GET Requests**: $0.0004 per 1,000 requests
- Workers download for parsing (1× per resume)
- Users download for viewing (rare)
- 10,000 downloads = $0.004

**Data Transfer OUT**: $0.09 per GB (first 10TB)
- Only charged when downloading to internet (not to EC2/ECS in same region)
- Workers in same region = FREE

**Total Monthly Cost Examples**:
- **Starter tier** (100 candidates/month): ~$0.02/month
- **Professional tier** (1,000 candidates/month): ~$0.15/month
- **Enterprise tier** (10,000 candidates/month): ~$1.50/month

**S3 is negligible compared to OpenAI API costs** ($0.006 per candidate = $60/month for 10K candidates)

---

## Security Best Practices

### 1. Encryption at Rest
✅ Already enabled: All uploads use `ServerSideEncryption: 'AES256'`

### 2. Private Bucket
✅ Block all public access enabled by default

### 3. IAM Least Privilege
✅ IAM policy only grants `PutObject`, `GetObject`, `DeleteObject`, `HeadObject`
❌ No `ListBucket` (can't enumerate all resumes)
❌ No `s3:*` (wildcard permissions)

### 4. Audit Logging (Optional)
Enable S3 Access Logging or CloudTrail for compliance:
```bash
aws s3api put-bucket-logging \
  --bucket starscreen-resumes-prod \
  --bucket-logging-status file://logging.json
```

### 5. Lifecycle Policies (Optional)
Auto-delete resumes after 90 days (if GDPR/compliance requires):
```json
{
  "Rules": [
    {
      "Id": "DeleteOldResumes",
      "Status": "Enabled",
      "Expiration": {
        "Days": 90
      },
      "Filter": {
        "Prefix": "resumes/"
      }
    }
  ]
}
```

---

## Troubleshooting

### Error: "NoSuchBucket"
**Cause**: Bucket name doesn't exist or wrong region
**Fix**:
```bash
# Verify bucket exists
aws s3 ls s3://starscreen-resumes-prod/

# Check region
aws s3api get-bucket-location --bucket starscreen-resumes-prod
```

### Error: "Access Denied"
**Cause**: IAM permissions insufficient
**Fix**:
1. Verify IAM policy includes `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`
2. Check bucket policy doesn't block your IAM user
3. Test credentials:
   ```bash
   aws s3 cp test.txt s3://starscreen-resumes-prod/resumes/test.txt
   ```

### Error: "InvalidAccessKeyId"
**Cause**: Wrong AWS credentials in .env
**Fix**:
1. Regenerate access keys in IAM console
2. Update .env with new keys
3. Restart containers: `docker-compose restart`

### Error: "Failed to download file from S3"
**Cause**: File path in database doesn't match S3 key
**Fix**:
```sql
-- Check candidate file paths
SELECT id, file_path FROM candidates WHERE file_path LIKE 's3://%';

-- If malformed, update manually
UPDATE candidates
SET file_path = 's3://starscreen-resumes-prod/resumes/abc123.pdf'
WHERE id = 1;
```

### Worker Can't Parse Resume
**Cause**: Worker downloaded corrupt file from S3
**Fix**:
1. Check worker logs: `docker-compose logs worker`
2. Verify file exists in S3: `aws s3 ls s3://starscreen-resumes-prod/resumes/`
3. Download file manually to test:
   ```bash
   aws s3 cp s3://starscreen-resumes-prod/resumes/abc123.pdf ./test.pdf
   pdfplumber test.pdf  # Test parsing locally
   ```

---

## Performance Optimization (Phase 3)

### 1. Pre-Signed URLs for Direct Upload
**Current**: Browser → API → S3 (2 network hops)
**Optimized**: Browser → S3 directly using pre-signed URL (1 hop)

```python
# Generate pre-signed URL (valid for 5 minutes)
s3_client.generate_presigned_url(
    'put_object',
    Params={'Bucket': bucket, 'Key': s3_key},
    ExpiresIn=300
)
```

### 2. CloudFront CDN for Downloads
**Current**: Workers download from S3 (Oregon) = high latency from Asia
**Optimized**: CloudFront edge locations cache files globally

### 3. S3 Transfer Acceleration
**Current**: Uploads from Asia to us-east-1 = slow
**Optimized**: S3 Transfer Acceleration routes through AWS edge network

---

## Next Steps

1. ✅ **S3 Code Integration**: Complete
2. ⏳ **Create S3 Bucket**: Follow Step 1 above
3. ⏳ **Update .env**: Set `USE_S3=true` and add credentials
4. ⏳ **Test Upload Flow**: Verify files appear in S3 bucket
5. ⏳ **Deploy to Production**: Once tested, enable for prod environment
6. 🔜 **Phase 3 Optimization**: Pre-signed URLs, CloudFront CDN

---

## FAQs

**Q: Can I use Google Cloud Storage or Azure Blob instead of S3?**
A: Yes! The storage abstraction layer ([app/core/storage.py](app/core/storage.py)) makes it easy to add new backends. Implement a `GCSStorage` or `AzureBlobStorage` class following the same interface.

**Q: What happens if S3 goes down?**
A: S3 has 99.99% uptime SLA. If it's down, uploads will fail. Consider:
- Multi-region replication (advanced)
- Retry logic with exponential backoff (already in Celery)
- Queue uploads and process when S3 recovers

**Q: Should I use S3 for local development?**
A: No, keep `USE_S3=false` locally. Only enable for staging/production. Avoids AWS costs during development.

**Q: How do I backup S3 data?**
A: Enable S3 versioning + cross-region replication to backup bucket in different region.

---

*Last Updated: 2025-12-31*

*Phase 2 Complete: Cloud-native file storage with S3*
