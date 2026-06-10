"""
Database session factory.
DATABASE_URL env var controls which DB is used:
  - Not set  →  SQLite file at ./data/sales_agent.db  (local dev)
  - Set      →  Whatever URL is provided (Postgres on Railway, etc.)

This is the ONLY place that knows about the database URL.
All other code just calls get_db() and gets a session.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/sales_agent.db")

# SQLite needs check_same_thread=False because FastAPI uses threads internally
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they don't exist. Called once at startup."""
    import os
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency injection pattern.
    Usage in a route:  db: Session = Depends(get_db)
    Guarantees the session is always closed after the request, even on error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
