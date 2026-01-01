# Starscreen - AI-Powered Resume Screening Platform

Starscreen is a production-ready SaaS platform that automates resume screening using AI. Upload resumes, define job requirements, and get instant AI-powered candidate rankings with detailed scoring breakdowns.

## Features

- **AI-Powered Scoring**: Intelligent resume analysis using OpenAI GPT-4
- **Multi-Tenant Architecture**: Secure, isolated workspaces for each organization
- **Subscription Tiers**: Free, Starter, Small Business, Professional, and Enterprise plans
- **Cloud-Native Storage**: AWS S3 integration for horizontal scalability
- **Async Processing**: Celery + Redis for background resume parsing and scoring
- **RESTful API**: FastAPI with automatic OpenAPI documentation
- **Production-Ready**: Docker Compose orchestration with PostgreSQL database

## Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Database**: PostgreSQL 15 with Alembic migrations
- **Task Queue**: Celery with Redis broker
- **AI**: OpenAI GPT-4o for resume analysis
- **Storage**: AWS S3 (production) / Local filesystem (development)
- **Payments**: Stripe integration for subscriptions
- **Deployment**: Docker Compose, AWS EC2

## Project Structure

```
Resume-Analyzer/
├── app/
│   ├── api/endpoints/      # API route handlers
│   ├── core/               # Core configuration and utilities
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic validation schemas
│   └── tasks/              # Celery background tasks
├── alembic/                # Database migrations
├── docs/                   # Deployment and implementation guides
├── docker-compose.yml      # Container orchestration
├── Dockerfile              # API container image
├── requirements.txt        # Python dependencies
└── .env                    # Environment configuration (not in git)
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- PostgreSQL 15
- Redis
- OpenAI API key
- (Optional) AWS Account for S3 storage

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Resume-Analyzer.git
   cd Resume-Analyzer
   ```

2. **Create `.env` file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Configure environment variables**
   ```bash
   # Required settings
   OPENAI_API_KEY=sk-your-key-here
   SECRET_KEY=generate-with-openssl-rand-hex-32
   POSTGRES_PASSWORD=your-secure-password

   # Use local storage for development
   USE_S3=false
   ```

4. **Start services**
   ```bash
   docker-compose up -d
   ```

5. **Run database migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

6. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - API: http://localhost:8000/api/v1

### Production Deployment

See [EC2_DEPLOYMENT_GUIDE.md](docs/EC2_DEPLOYMENT_GUIDE.md) for detailed AWS deployment instructions.

**Quick deployment summary:**
1. Launch EC2 instance with IAM role
2. Create S3 bucket for resume storage
3. Clone repository
4. Configure `.env` with production settings (`USE_S3=true`)
5. Run `docker-compose up -d`
6. Run migrations: `docker-compose exec api alembic upgrade head`

## API Documentation

### Authentication

Register a user:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

Response includes `access_token` for authenticated requests.

### Create a Job Posting

```bash
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Software Engineer",
    "description": "Looking for experienced backend developer with Python expertise..."
  }'
```

### Upload Resume

```bash
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@resume.pdf"
```

The resume is automatically:
1. Uploaded to S3 (or local storage)
2. Queued for text extraction
3. Scored by AI against job requirements
4. Returned with detailed evaluation

### Get Candidates

```bash
curl -X GET http://localhost:8000/api/v1/jobs/{job_id}/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

**Key settings:**

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_S3` | Enable S3 storage | `false` |
| `S3_BUCKET_NAME` | S3 bucket for resumes | - |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `SECRET_KEY` | JWT signing key | Generate with `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Database password | `password` |
| `STRIPE_API_KEY` | Stripe API key for payments | - |

### Subscription Tiers

| Plan | Price | Candidate Limit |
|------|-------|----------------|
| Free | $0 | 10 candidates |
| Starter | $19/month | 100 candidates |
| Small Business | $49/month | 500 candidates |
| Professional | $149/month | 2,500 candidates |
| Enterprise | $499/month | 15,000 candidates |

## Documentation

- [EC2 Deployment Guide](docs/EC2_DEPLOYMENT_GUIDE.md) - Complete AWS deployment walkthrough
- [S3 Implementation Summary](docs/S3_IMPLEMENTATION_SUMMARY.md) - S3 storage architecture and setup
- [S3 Migration Guide](docs/s3-migration-guide.md) - Detailed S3 configuration guide
- [Quick Start Guide](docs/QUICK_START_NEXT_STEPS.md) - Fast deployment checklist

## Architecture

### Storage Abstraction

Starscreen uses a storage abstraction layer ([app/core/storage.py](app/core/storage.py)) that supports:
- **Local Storage**: Files stored in `uploads/` directory (development)
- **S3 Storage**: Files stored in AWS S3 bucket (production)

Toggle between modes with `USE_S3` environment variable - no code changes required.

### Async Processing Pipeline

1. **Upload**: Resume uploaded via API → stored in S3/local
2. **Parse**: Celery worker extracts text from PDF/DOCX
3. **Score**: OpenAI GPT-4 evaluates candidate against job requirements
4. **Store**: Results saved to PostgreSQL database

### Multi-Tenancy

- Row-level security with `tenant_id` foreign keys
- JWT authentication with user-scoped access tokens
- Isolated data per organization

## Development

### Running Tests

```bash
# Run all tests
docker-compose exec api pytest

# Run with coverage
docker-compose exec api pytest --cov=app --cov-report=html
```

### Database Migrations

```bash
# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback
docker-compose exec api alembic downgrade -1
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
```

## Cost Analysis

### S3 Storage Costs (us-east-1)
- **Storage**: $0.023/GB/month
- **10,000 resumes** (~5GB): **$0.12/month**
- **Uploads**: $0.005 per 1,000 requests
- **Downloads**: $0.0004 per 1,000 requests

**Total S3 cost**: ~$0.20/month for 10,000 candidates

### OpenAI API Costs
- **GPT-4o scoring**: ~$0.006 per candidate
- **10,000 candidates**: **$60/month**

**S3 adds <0.3% to total infrastructure costs**

## Security

- **Encryption**: AES-256 server-side encryption for S3
- **Private S3 Bucket**: Public access blocked by default
- **IAM Least Privilege**: Minimal S3 permissions required
- **JWT Authentication**: Secure token-based auth with refresh tokens
- **Password Hashing**: bcrypt with configurable rounds
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries

## Troubleshooting

See [EC2_DEPLOYMENT_GUIDE.md - Troubleshooting](docs/EC2_DEPLOYMENT_GUIDE.md#troubleshooting) for common issues and solutions.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For questions or issues:
- Open a GitHub issue
- Email: support@starscreen.com (update with your contact)

---

**Status**: Production-Ready
**Last Updated**: 2026-01-01
