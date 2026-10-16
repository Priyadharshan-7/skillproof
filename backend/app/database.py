"""SkillProof - Database configuration."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".."))
DEFAULT_DB_FILE = os.path.join(PROJECT_ROOT, "skillproof.db").replace("\\", "/")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or DATABASE_URL.startswith("sqlite:///."):
    DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a database session, closing it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    from app.models import Student, Project, Skill, MentorFeedback  # noqa: F401
    Base.metadata.create_all(bind=engine)
