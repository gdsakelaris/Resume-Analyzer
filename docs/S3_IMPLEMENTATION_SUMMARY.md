# AWS S3 Implementation - Quick Reference

**Status**: Fully implemented and deployed to production

---

## Overview

Resume files are stored in AWS S3 bucket `starscreen-resumes-prod` with IAM role-based authentication (no hardcoded credentials).

---

## Key Files

### [app/core/storage.py](../app/core/storage.py)
Storage abstraction layer with S3 and local filesystem support.

**Key Methods**:
- `upload_file(file_obj, original_filename)` → Returns S3 key or local path
- `download_file(file_path)` → Returns BytesIO object
- `delete_file(file_path)` → Deletes from S3 or local
- `file_exists(file_path)` → Checks if file exists

**Implementation**:
```python
# Auto-detects storage backend from settings.USE_S3
storage = S3Storage() if settings.USE_S3 else LocalStorage()

# Usage in candidates.py:
file_path = storage.upload_file(file.file, file.filename)
```

### [app/api/endpoints/candidates.py](../app/api/endpoints/candidates.py)
- **Line 19**: Import storage abstraction
- **Line 119**: Upload file to storage (S3 or local)
- **Line 520-544**: Download file from S3 (streaming response)
- **Line 646**: Delete file from storage

### Environment Variables
```bash
# .env (both local and EC2)
USE_S3=true
AWS_REGION=us-east-1
S3_BUCKET_NAME=starscreen-resumes-prod
AWS_ACCESS_KEY_ID=          # Empty (using IAM role on EC2)
AWS_SECRET_ACCESS_KEY=      # Empty (using IAM role on EC2)
```

---

## S3 Bucket Configuration

**Bucket Name**: `starscreen-resumes-prod`
**Region**: `us-east-1`
**Access**: Private (IAM role only)

**IAM Role**: Attached to EC2 instance with S3 read/write permissions

**File Naming**: UUIDs to prevent collisions (e.g., `abc123-resume.pdf`)

---

## Storage Flow

### Upload
```
User uploads resume
→ FastAPI receives file
→ storage.upload_file(file_obj, "resume.pdf")
→ S3: boto3.upload_fileobj(file_obj, bucket, "uuid-resume.pdf")
→ Returns S3 key: "uuid-resume.pdf"
→ Saved to database: candidate.file_path = "uuid-resume.pdf"
```

### Download
```
User requests resume file
→ API checks: storage.file_exists(candidate.file_path)
→ S3: download_file(candidate.file_path) → BytesIO
→ StreamingResponse(BytesIO, media_type=content_type)
→ User downloads file
```

### Delete
```
User deletes candidate
→ storage.delete_file(candidate.file_path)
→ S3: boto3.delete_object(bucket, file_path)
→ Database record deleted
```

---

## Production Setup

### EC2 Instance
- **Domain**: https://starscreen.net
- **IAM Role**: `StarscreenEC2Role` with S3 permissions
- **Bucket**: `starscreen-resumes-prod` (AES-256 encrypted, private)

### Deployment
```bash
# EC2
USE_S3=true
AWS_REGION=us-east-1
S3_BUCKET_NAME=starscreen-resumes-prod
AWS_ACCESS_KEY_ID=          # Empty - uses IAM role
AWS_SECRET_ACCESS_KEY=      # Empty - uses IAM role
```

---

## Testing S3 Integration

```bash
# EC2
docker-compose logs api | grep -i s3

# Expected logs:
# "Saved resume to storage: uuid-resume.pdf"
# "Downloaded file from S3: uuid-resume.pdf"
# "Deleted resume file from storage: uuid-resume.pdf"
```

---

## Local Development

For local testing without S3:
```bash
# .env (local)
USE_S3=false  # Files stored in ./uploads/ directory
```

---

## Architecture Benefits

### Horizontal Scaling
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ API Server 1 │  │ API Server 2 │  │ API Server N │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
               ┌─────────────────┐
               │   AWS S3 Bucket │
               │   (Shared)      │
               └─────────────────┘
```

**Benefits**:
- Multiple API servers can access same files
- Stateless containers (easy to scale)
- 99.999999999% data durability
- Minimal cost (<$0.20/month for 10K candidates)

---

**Last Updated**: 2026-01-01
