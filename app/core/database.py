from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=10,  # Connection pool size
    max_overflow=20  # Allow up to 20 connections beyond pool_size
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Used in FastAPI endpoints with Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database.

    We rely on Alembic for table creation now, so this is just a placeholder
    to ensure models are imported/registered.

    Note: Base.metadata.create_all() is disabled to avoid conflicts with Alembic.
    Use "alembic upgrade head" to create/update database schema.
    """
    from app.models import job, candidate  # Import models to register them
    # Base.metadata.create_all(bind=engine)  # Disabled - use Alembic instead
